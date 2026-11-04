# proveedores/_web.py
"""
Motor común para proveedores que se descargan desde su sitio web con navegador.

Cada proveedor (proveedor_xxx.py) hereda de  FlujoWebMixin + BaseProveedor  y solo
implementa  pasos(page, cfg)  con la receta de su sitio, usando estos helpers:

    page = self.login(page, cfg, urls)            -> ingresa con usuario/contraseña
    page = self.clic_texto(page, ["Descargas"])   -> clic por texto visible (abre menús
                                                     desplegables si hace falta)
    tmp  = self.bajar_archivo(page, ...)          -> dispara la descarga y la guarda
    ruta = self.guardar_final(tmp, "pana.dbf")    -> nombre final en la carpeta destino

Si algo falla se guarda una captura (.png) y el HTML de la página en
<carpeta destino>/_diagnostico/ para ver qué pasó.

Opciones útiles en config.json (bloque del proveedor o "configuracion_global"):
    "mostrar_navegador": true   -> se ve la ventana del navegador (para probar)
    "timeout_ms": 30000         -> espera máxima por paso
"""

from __future__ import annotations

import csv
import re
import time
import unicodedata
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from proveedores.base import ProveedorError

EXT_ARCHIVO = (".xls", ".xlsx", ".csv", ".txt", ".dbf", ".zip")

TEXTOS_ABRIR_LOGIN = [
    "Ingresar", "Iniciar sesión", "Acceso clientes", "Clientes", "Login",
    "Mi cuenta", "Entrar", "Acceder", "Ingreso",
]
TEXTOS_BOTON_LOGIN = ["Ingresar", "Entrar", "Iniciar sesión", "Acceder", "Login", "Aceptar", "Enviar"]

SEL_MENUS = (
    ".dropdown-toggle, [data-toggle='dropdown'], [data-bs-toggle='dropdown'], "
    "[aria-haspopup='true'], [aria-haspopup='menu'], .caret, .fa-caret-down, "
    ".fa-chevron-down, .fa-angle-down, .bi-chevron-down, .user-menu, .user-name, "
    ".navbar-toggler"
)

SEL_BUSQUEDA = (
    "input[type=search], input[name*=busc i], input[id*=busc i], input[placeholder*=busc i], "
    "input[name*=search i], input[id*=search i], input[placeholder*=search i], input[name=q], "
    "input[placeholder*=artic i], input[placeholder*=codig i], input[placeholder*=códig i], "
    "input[name*=codigo i], input[name*=articulo i]"
)


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de texto
# ─────────────────────────────────────────────────────────────────────────────

def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def rx(texto: str) -> re.Pattern:
    """Regex que ignora mayúsculas, acentos y espacios repetidos."""
    mapa = {"a": "[aáà]", "e": "[eéè]", "i": "[iíì]", "o": "[oóò]", "u": "[uúü]", "n": "[nñ]"}
    partes = []
    for c in sin_acentos(texto).lower():
        if c.isspace():
            partes.append(r"\s+")
        else:
            partes.append(mapa.get(c, re.escape(c)))
    return re.compile("".join(partes), re.I)


def _texto_ok(texto: str, excluir: list[str] | None) -> bool:
    if not excluir:
        return True
    return not any(rx(x).search(texto or "") for x in excluir)


def nombre_original(content_disposition: str, url: str) -> str:
    """Nombre con el que el sitio entrega el archivo (encabezado o final de la URL)."""
    m = re.search(r"filename\*?=(?:UTF-8'')?[\"']?([^\"';]+)", content_disposition or "", re.IGNORECASE)
    if m:
        nombre = Path(unquote(m.group(1).strip())).name
        if nombre:
            return nombre
    return Path(unquote(urlparse(url or "").path)).name or "archivo"


# ─────────────────────────────────────────────────────────────────────────────
# Conversión de Excel a CSV (usada por Cedicor)
# ─────────────────────────────────────────────────────────────────────────────

class _TablaHTML(HTMLParser):
    """Extrae filas de la primera tabla HTML (muchos 'xls' de sitios son HTML)."""

    def __init__(self):
        super().__init__()
        self.filas: list[list[str]] = []
        self._fila: list[str] | None = None
        self._celda: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._fila is not None and self._celda is not None:
            self._fila.append(" ".join("".join(self._celda).split()))
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            if self._fila:
                self.filas.append(self._fila)
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def tipo_real(ruta: Path) -> str:
    """Detecta el tipo por contenido: 'xlsx', 'xls', 'zip', 'html' o '' (texto/otro)."""
    with open(ruta, "rb") as f:
        cab = f.read(1024)
    if cab.startswith(b"PK"):
        try:
            with zipfile.ZipFile(ruta) as z:
                if any(n.startswith("xl/") for n in z.namelist()):
                    return "xlsx"
        except zipfile.BadZipFile:
            pass
        return "zip"
    if cab.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    inicio = cab.lstrip().lower()
    if inicio.startswith((b"<!doctype", b"<html", b"<table", b"<?xml")) or b"<html" in inicio[:300]:
        return "html"
    return ""


def excel_a_csv(origen: Path, destino: Path, separador=";", decimal=",", encoding="cp1252") -> int:
    """Convierte xlsx/xls/HTML-tabla a CSV. Devuelve la cantidad de filas."""
    tipo = tipo_real(origen)
    filas: list[list] = []
    if tipo == "xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(origen, read_only=True, data_only=True)
        hoja = wb.worksheets[0]
        filas = [list(f) for f in hoja.iter_rows(values_only=True)]
        wb.close()
    elif tipo == "xls":
        import xlrd
        libro = xlrd.open_workbook(str(origen))
        hoja = libro.sheet_by_index(0)
        filas = [hoja.row_values(i) for i in range(hoja.nrows)]
    elif tipo == "html":
        p = _TablaHTML()
        p.feed(origen.read_text(encoding="utf-8", errors="replace"))
        filas = p.filas
    else:  # ya es texto/CSV: se copia tal cual
        destino.write_bytes(origen.read_bytes())
        return sum(1 for _ in open(destino, "rb"))

    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            if v.is_integer():
                return str(int(v))
            return repr(v).replace(".", decimal)
        if isinstance(v, datetime):
            return v.strftime("%d/%m/%Y")
        return str(v).strip()

    # quitar filas totalmente vacías del final
    while filas and all(fmt(c) == "" for c in filas[-1]):
        filas.pop()
    with open(destino, "w", newline="", encoding=encoding, errors="replace") as f:
        w = csv.writer(f, delimiter=separador)
        for fila in filas:
            w.writerow([fmt(c) for c in fila])
    return len(filas)


# ─────────────────────────────────────────────────────────────────────────────
# Mixin con el flujo web
# ─────────────────────────────────────────────────────────────────────────────

class FlujoWebMixin:
    """Poner ANTES de BaseProveedor:  class ProveedorX(FlujoWebMixin, BaseProveedor)."""

    # False = descarga directa por HTTP, sin abrir navegador (más rápido).
    # En ese caso pasos() recibe page=None y usa bajar_http / buscar_link_http.
    usa_navegador: bool = True

    def pasos(self, page, cfg: dict) -> str:  # pragma: no cover - lo implementa cada proveedor
        raise NotImplementedError

    def al_terminar(self, page) -> None:
        """Se ejecuta siempre al final (haya error o no). Ej.: cerrar sesión."""

    def nombre_descargado(self, tmp) -> str:
        """Nombre original con el que el sitio entregó el archivo."""
        nombre = Path(tmp).name
        prefijo = f"_tmp_{self.nombre_clave}_"
        return nombre[len(prefijo):] if nombre.startswith(prefijo) else nombre

    def texto_en_pagina(self, page, textos) -> str | None:
        """Devuelve el primer texto de la lista que aparezca en la página (o None)."""
        try:
            contenido = sin_acentos(page.inner_text("body", timeout=5000)).lower()
        except Exception:
            return None
        for t in textos:
            if sin_acentos(t).lower() in contenido:
                return t
        return None

    # ── Punto de entrada que llama la app ────────────────────────────────────
    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        destino = Path(directorio_destino)
        destino.mkdir(parents=True, exist_ok=True)
        self._destino = destino
        cfg = self.cfg_proveedor()
        glob = self.cfg.get("configuracion_global", {})
        if cfg.get("mostrar_navegador", glob.get("mostrar_navegador", False)):
            headless = False
        timeout = int(cfg.get("timeout_ms", glob.get("timeout_ms", 30000)))
        self._page = None
        self._http = None

        if not self.usa_navegador:
            self.log("Descarga directa (sin navegador)...")
            try:
                ruta = self.pasos(None, cfg)
                self.log(f"OK -> {ruta}")
                return ruta
            except ProveedorError:
                raise
            except Exception as e:
                raise ProveedorError(f"{type(e).__name__}: {e}") from e

        self.log("Iniciando navegador...")
        with sync_playwright() as p:
            if hasattr(self, "lanzar_navegador"):
                browser = self.lanzar_navegador(p, headless)
            else:
                browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                accept_downloads=True,
                viewport={"width": 1366, "height": 900},
                locale="es-AR",
            )
            context.set_default_timeout(timeout)
            self._descargas = []
            self._usadas = 0
            context.on("page", lambda pg: pg.on("download", lambda d: self._descargas.append(d)))
            page = context.new_page()
            self._page = page
            try:
                ruta = self.pasos(page, cfg)
                self.log(f"OK -> {ruta}")
                return ruta
            except ProveedorError as e:
                self._diagnostico(str(e))
                raise
            except PWTimeout as e:
                msg = f"Tiempo de espera agotado: {str(e).splitlines()[0]}"
                self._diagnostico(msg)
                raise ProveedorError(msg) from e
            except Exception as e:
                msg = f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"
                self._diagnostico(msg)
                raise ProveedorError(msg) from e
            finally:
                try:
                    self.al_terminar(self._page or page)
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass

    # ── Diagnóstico ──────────────────────────────────────────────────────────
    def _diagnostico(self, motivo: str) -> None:
        if self._page is None:
            return
        try:
            carpeta = Path(getattr(self, "carpeta_diagnostico", None) or self._destino / "_diagnostico")
            carpeta.mkdir(parents=True, exist_ok=True)
            base = carpeta / f"{self.nombre_clave}_{datetime.now():%Y%m%d_%H%M%S}"
            pg = self._page
            pg.screenshot(path=str(base) + ".png", full_page=True)
            Path(str(base) + ".html").write_text(pg.content(), encoding="utf-8")
            Path(str(base) + ".txt").write_text(f"URL: {pg.url}\nError: {motivo}\n", encoding="utf-8")
            self.log(f"Captura del error guardada en: {base}.png")
        except Exception as e:  # noqa: BLE001
            self.log(f"(No se pudo guardar el diagnóstico: {e})")

    # ── Esperas ──────────────────────────────────────────────────────────────
    def esperar(self, page, ms: int = 10000) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=ms)
        except Exception:
            pass

    def ir_a(self, page, urls) -> None:
        """Abre la primera URL que cargue (acepta una o varias)."""
        if isinstance(urls, str):
            urls = [urls]
        # Si un sitio no responde por https, probar también por http
        extra = [u.replace("https://", "http://", 1) for u in urls
                 if u and u.startswith("https://")]
        urls = list(urls) + [u for u in extra if u not in urls]
        ultimo = None
        for url in urls:
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://" + url
            try:
                self.log(f"Abriendo {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                self.esperar(page)
                return
            except Exception as e:  # noqa: BLE001
                ultimo = e
                self.log(f"No cargó {url}: {str(e).splitlines()[0]}")
        raise ProveedorError(f"No se pudo abrir el sitio ({ultimo}). Revisar 'login_url' en config.json")

    # ── Login ────────────────────────────────────────────────────────────────
    def _buscar_password(self, page, selector: str | None):
        sel = selector or "input[type=password]"
        for frame in page.frames:
            try:
                loc = frame.locator(sel)
                for i in range(min(loc.count(), 5)):
                    if loc.nth(i).is_visible():
                        return frame, loc.nth(i)
            except Exception:
                continue
        return None, None

    def login(self, page, cfg: dict, urls_por_defecto) -> object:
        usuario = str(cfg.get("usuario", "")).strip()
        password = str(cfg.get("password", "")).strip()
        if not usuario or not password:
            raise ProveedorError(
                f"Faltan 'usuario' y/o 'password' en config.json -> proveedores.{self.nombre_clave}"
            )
        self.ir_a(page, cfg.get("login_url") or urls_por_defecto)

        sel_pwd = cfg.get("selector_password")
        frame, pwd = self._buscar_password(page, sel_pwd)
        if pwd is None:
            self.log("No se ve el formulario de ingreso, buscando el botón para abrirlo...")
            nueva = self.clic_texto(page, cfg.get("textos_abrir_login") or TEXTOS_ABRIR_LOGIN,
                                    obligatorio=False, timeout=8000)
            page = nueva or page
            fin = time.time() + 15
            while pwd is None and time.time() < fin:
                page.wait_for_timeout(500)
                frame, pwd = self._buscar_password(page, sel_pwd)
        if pwd is None:
            raise ProveedorError("No se encontró el campo de contraseña en la página de ingreso")

        # Campo usuario: el indicado en config o el input visible anterior a la contraseña
        if cfg.get("selector_usuario"):
            campo_user = frame.locator(cfg["selector_usuario"]).first
        else:
            ok = pwd.evaluate(
                """(pwd) => {
                    const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
                                    && getComputedStyle(e).visibility !== 'hidden';
                    const malos = ['hidden','password','checkbox','radio','submit','button',
                                   'file','image','reset','search'];
                    const ok = e => (e.tagName === 'SELECT' || !malos.includes((e.type || 'text').toLowerCase()))
                                    && vis(e) && !e.disabled && !e.readOnly;
                    const all = Array.from(document.querySelectorAll('input, select'));
                    const i = all.indexOf(pwd);
                    // primero los campos ANTES de la contraseña, después los que vienen DESPUÉS
                    const e = all.slice(0, i).reverse().concat(all.slice(i + 1)).find(ok);
                    if (e) { e.setAttribute('data-cano-usuario', '1'); return true; }
                    return false;
                }"""
            )
            if not ok:
                raise ProveedorError("No se encontró el campo de usuario (cargar 'selector_usuario' en config.json)")
            campo_user = frame.locator("[data-cano-usuario='1']").first

        self.log("Completando usuario y contraseña...")
        if campo_user.evaluate("e => e.tagName") == "SELECT":
            campo_user.select_option(label=usuario)
        else:
            campo_user.fill(usuario)
        pwd.fill(password)
        if cfg.get("selector_ingresar"):
            frame.locator(cfg["selector_ingresar"]).first.click()
        else:
            pwd.press("Enter")
        page.wait_for_timeout(2500)
        self.esperar(page, 15000)

        # Si el formulario sigue ahí, probar con el botón
        _, pwd2 = self._buscar_password(page, sel_pwd)
        if pwd2 is not None and not cfg.get("selector_ingresar"):
            boton = self._encontrar(page, TEXTOS_BOTON_LOGIN, roles_solo=True)
            if boton is None:
                b = frame.locator("button[type=submit], input[type=submit]")
                boton = b.first if b.count() else None
            if boton is not None:
                self.log("Enviando formulario con el botón de ingreso...")
                try:
                    boton.click()
                except Exception:
                    pass
                page.wait_for_timeout(2500)
                self.esperar(page, 15000)
            _, pwd2 = self._buscar_password(page, sel_pwd)
        if pwd2 is not None:
            self.log("Aviso: el formulario de ingreso sigue visible. Si falla después, revisar usuario/contraseña.")
        else:
            self.log("Ingreso realizado.")
        return page

    # ── Búsqueda y clic por texto ────────────────────────────────────────────
    def _encontrar(self, page, textos, excluir=None, roles_solo=False):
        textos = [textos] if isinstance(textos, str) else list(textos)
        for t in textos:  # primero el texto más específico
            r = rx(t)
            for frame in page.frames:
                candidatos = [
                    frame.get_by_role("link", name=r),
                    frame.get_by_role("button", name=r),
                    frame.get_by_role("menuitem", name=r),
                    frame.get_by_role("tab", name=r),
                ]
                if not roles_solo:
                    candidatos += [frame.get_by_label(r), frame.get_by_text(r)]
                for loc in candidatos:
                    try:
                        n = loc.count()
                    except Exception:
                        continue
                    for i in range(min(n, 15)):
                        el = loc.nth(i)
                        try:
                            if el.is_visible() and _texto_ok(el.inner_text(timeout=1000), excluir):
                                return el
                        except Exception:
                            continue
        return None

    def _abrir_menus(self, page, textos, excluir=None):
        """Abre menús desplegables (flechitas, nombre de usuario...) buscando el texto."""
        for frame in page.frames:
            try:
                toggles = frame.locator(SEL_MENUS)
                n = min(toggles.count(), 12)
            except Exception:
                continue
            for i in range(n):
                t = toggles.nth(i)
                try:
                    if not t.is_visible():
                        continue
                    t.hover(timeout=2000)
                    page.wait_for_timeout(400)
                    el = self._encontrar(page, textos, excluir)
                    if el:
                        return el
                    t.click(timeout=2000)
                    page.wait_for_timeout(700)
                    el = self._encontrar(page, textos, excluir)
                    if el:
                        return el
                except Exception:
                    continue
        return None

    def _href_oculto(self, page, textos, excluir=None):
        for frame in page.frames:
            try:
                links = frame.eval_on_selector_all(
                    "a[href]", "els => els.map(e => [e.textContent.trim(), e.href])"
                )
            except Exception:
                continue
            for t in textos:
                r = rx(t)
                for texto, href in links:
                    if r.search(texto or "") and _texto_ok(texto, excluir) and href \
                            and not href.startswith("javascript") and not href.endswith("#"):
                        return href
        return None

    def _clic_y_seguir(self, page, el):
        n_antes = len(page.context.pages)
        try:
            el.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        el.click()
        page.wait_for_timeout(1500)
        paginas = page.context.pages
        if len(paginas) > n_antes:
            nueva = paginas[-1]
            try:
                nueva.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            self.log("Se abrió una pestaña nueva; se continúa ahí.")
            self._page = nueva
            self.esperar(nueva)
            return nueva
        self.esperar(page)
        return page

    def clic_texto(self, page, textos, obligatorio=True, timeout=15000, excluir=None):
        """
        Hace clic en el primer elemento visible con alguno de los textos.
        Si no aparece, abre los menús desplegables y, como último recurso,
        navega al link aunque esté oculto. Devuelve la página donde seguir.
        """
        textos = [textos] if isinstance(textos, str) else list(textos)
        fin = time.time() + timeout / 1000
        menus_probados = False
        while True:
            el = self._encontrar(page, textos, excluir)
            if el is None and not menus_probados and time.time() > fin - timeout / 2000:
                menus_probados = True
                el = self._abrir_menus(page, textos, excluir)
            if el is not None:
                self.log(f"Clic en '{textos[0]}'")
                return self._clic_y_seguir(page, el)
            if time.time() > fin:
                break
            page.wait_for_timeout(500)
        href = self._href_oculto(page, textos, excluir)
        if href:
            self.log(f"'{textos[0]}' estaba oculto; se abre el link directo: {href}")
            page.goto(href, wait_until="domcontentloaded")
            self.esperar(page)
            return page
        if obligatorio:
            raise ProveedorError(f"No se encontró '{' / '.join(textos)}' en la página")
        return None

    # ── Formularios ──────────────────────────────────────────────────────────
    def buscar_articulo(self, page, cfg: dict, articulo: str):
        sel = cfg.get("selector_busqueda") or SEL_BUSQUEDA
        fin = time.time() + 15
        while time.time() < fin:
            for frame in page.frames:
                try:
                    loc = frame.locator(sel)
                    for i in range(min(loc.count(), 10)):
                        campo = loc.nth(i)
                        if campo.is_visible():
                            self.log(f"Buscando artículo {articulo}...")
                            campo.fill(articulo)
                            campo.press("Enter")
                            page.wait_for_timeout(3000)
                            self.esperar(page)
                            return page
                except Exception:
                    continue
            page.wait_for_timeout(500)
        raise ProveedorError("No se encontró el buscador de artículos (cargar 'selector_busqueda' en config.json)")

    def tildar_todos(self, page, textos=("Seleccionar todos", "Marcar todos", "Marcar todas",
                                         "Tildar todos", "Todos", "Todas")):
        for t in textos:
            r = rx(t)
            for frame in page.frames:
                try:
                    cb = frame.get_by_label(r)
                    for i in range(min(cb.count(), 5)):
                        el = cb.nth(i)
                        if el.is_visible() and el.evaluate("e => e.type === 'checkbox'"):
                            el.check()
                            self.log(f"Tildado '{t}'")
                            page.wait_for_timeout(800)
                            return
                except Exception:
                    continue
        el = self._encontrar(page, list(textos), roles_solo=True)
        if el is not None:
            el.click()
            self.log(f"Clic en '{el.inner_text().strip()[:40]}' para marcar todos")
            page.wait_for_timeout(800)
            return
        # Último recurso: tildar todas las casillas visibles
        n = 0
        for frame in page.frames:
            cajas = frame.locator("input[type=checkbox]")
            for i in range(min(cajas.count(), 1000)):
                c = cajas.nth(i)
                try:
                    if c.is_visible() and not c.is_checked():
                        c.check(timeout=2000)
                        n += 1
                except Exception:
                    continue
        if n == 0:
            self.log("Aviso: no se encontraron casillas para 'tildar todos'.")
        else:
            self.log(f"Se tildaron {n} casillas.")

    def elegir_opcion(self, page, texto: str, obligatorio=True):
        """Elige una opción por texto: en un <select>, una casilla/radio o un clic."""
        r = rx(texto)
        for frame in page.frames:
            selects = frame.locator("select")
            for i in range(min(selects.count(), 10)):
                s = selects.nth(i)
                try:
                    if not s.is_visible():
                        continue
                    opciones = s.locator("option").all_inner_texts()
                    for op in opciones:
                        if r.search(op):
                            s.select_option(label=op)
                            self.log(f"Seleccionado '{op.strip()}'")
                            page.wait_for_timeout(1500)
                            self.esperar(page)
                            return
                except Exception:
                    continue
            try:
                lab = frame.get_by_label(r)
                for i in range(min(lab.count(), 5)):
                    el = lab.nth(i)
                    if el.is_visible() and el.evaluate("e => ['checkbox','radio'].includes(e.type)"):
                        el.check()
                        self.log(f"Marcado '{texto}'")
                        page.wait_for_timeout(1500)
                        self.esperar(page)
                        return
            except Exception:
                pass
        el = self._encontrar(page, [texto])
        if el is not None:
            el.click()
            self.log(f"Clic en '{texto}'")
            page.wait_for_timeout(1500)
            self.esperar(page)
            return
        if obligatorio:
            raise ProveedorError(f"No se encontró la opción '{texto}'")

    # ── Descargas ────────────────────────────────────────────────────────────
    @staticmethod
    def _parece_archivo(url: str) -> bool:
        ruta = unquote(urlparse(url or "").path).lower()
        return ruta.endswith(EXT_ARCHIVO)

    def _bajar_url(self, page, url: str):
        self.log(f"Bajando por link directo: {url}")
        resp = page.context.request.get(url, timeout=180000)
        if not resp.ok:
            raise ProveedorError(f"El servidor respondió {resp.status} al bajar {url}")
        nombre = Path(unquote(urlparse(url).path)).name or "archivo"
        tmp = self._destino / f"_tmp_{self.nombre_clave}_{nombre}"
        tmp.write_bytes(resp.body())
        return tmp

    def _tomar_descarga(self):
        """Devuelve la última descarga del navegador que todavía no se usó."""
        if len(self._descargas) > self._usadas:
            dl = self._descargas[-1]
            self._usadas = len(self._descargas)
            tmp = self._destino / f"_tmp_{self.nombre_clave}_{dl.suggested_filename}"
            dl.save_as(tmp)
            self.log(f"Descarga recibida: {dl.suggested_filename}")
            return tmp
        return None

    def _links_archivo(self, page, extensiones) -> set:
        """URLs de los links de la página que terminan en alguna de las extensiones."""
        urls = set()
        for frame in page.frames:
            try:
                hrefs = frame.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            except Exception:
                continue
            for h in hrefs:
                ruta = unquote(urlparse(h or "").path).lower()
                if any(ruta.endswith("." + e.lower()) for e in extensiones):
                    urls.add(h)
        return urls

    def _descargar_con(self, page, accion, timeout=90000, extensiones=()):
        tmp = self._tomar_descarga()
        if tmp:
            return tmp
        antes = self._links_archivo(page, extensiones) if extensiones else set()
        accion()
        fin = time.time() + timeout / 1000
        while time.time() < fin:
            tmp = self._tomar_descarga()
            if tmp:
                return tmp
            # Algunos sitios generan el archivo y muestran un link nuevo en vez de bajarlo
            if extensiones:
                nuevos = self._links_archivo(page, extensiones) - antes
                if nuevos:
                    return self._bajar_url(page, sorted(nuevos)[0])
            for pg in page.context.pages:
                if self._parece_archivo(pg.url):
                    return self._bajar_url(pg, pg.url)
            page.wait_for_timeout(500)
        raise ProveedorError("Se hizo clic pero la descarga no comenzó")

    def _descargar_elemento(self, page, el, timeout=90000, extensiones=()):
        href = None
        try:
            href = el.get_attribute("href", timeout=2000)
        except Exception:
            pass
        usable = href and not href.startswith(("javascript", "#"))
        try:
            return self._descargar_con(page, lambda: el.click(),
                                       timeout=20000 if usable else timeout, extensiones=extensiones)
        except ProveedorError:
            if usable:
                return self._bajar_url(page, urljoin(page.url, href))
            raise

    def _mejor_link(self, page, extensiones, pistas, excluir=None, minimo=5):
        mejor = (0, None)
        for frame in page.frames:
            try:
                links = frame.eval_on_selector_all(
                    "a[href]", "els => els.map(e => [e.textContent.trim(), e.href])"
                )
            except Exception:
                continue
            for i, (texto, href) in enumerate(links):
                if not _texto_ok(texto, excluir):
                    continue
                ruta = unquote(urlparse(href or "").path).lower()
                punt = 0
                if any(ruta.endswith("." + e.lower()) for e in extensiones):
                    punt += 10
                base = sin_acentos(f"{texto} {unquote(href or '')}").lower()
                punt += sum(5 for p in pistas if sin_acentos(p).lower() in base)
                if "descarg" in base:
                    punt += 2
                if punt > mejor[0]:
                    mejor = (punt, frame.locator("a[href]").nth(i))
        return mejor[1] if mejor[0] >= minimo else None

    def bajar_archivo(self, page, extensiones, pistas=(), textos=(), menus_previos=(),
                      excluir=None, timeout=90000):
        """
        Encuentra y descarga el archivo. Prueba en orden:
          1. un link que termine en la extensión del archivo (.xls, .dbf...)
          2. botones/links con alguno de 'textos' (el más específico primero)
          3. el link que mejor coincide por pistas
          3. si no aparece, hace clic en 'menus_previos' y vuelve a buscar
        """
        pendientes = list(menus_previos)
        fin = time.time() + 20
        while True:
            tmp = self._tomar_descarga()  # un clic anterior ya pudo disparar la descarga
            if tmp:
                return tmp
            # 1) un link que termina en la extensión del archivo gana siempre
            el = self._mejor_link(page, extensiones, pistas, excluir, minimo=10)
            # 2) botones/links con los textos indicados  3) links parecidos
            if el is None and textos:
                el = self._encontrar(page, list(textos), excluir)
            if el is None:
                el = self._mejor_link(page, extensiones, pistas, excluir)
            if el is not None:
                try:
                    etiqueta = el.inner_text(timeout=1000).strip()[:50]
                except Exception:
                    etiqueta = "?"
                self.log(f"Descargando desde '{etiqueta}'...")
                return self._descargar_elemento(page, el, timeout, extensiones)
            if time.time() > fin:
                if not pendientes:
                    break
                menu = pendientes.pop(0)
                page = self.clic_texto(page, [menu], obligatorio=False, timeout=6000) or page
                fin = time.time() + 10
            page.wait_for_timeout(700)
        raise ProveedorError(
            f"No se encontró el archivo para descargar ({', '.join(extensiones)})"
        )

    # ── Descarga directa por HTTP (sin navegador) ───────────────────────────
    def _sesion_http(self):
        if self._http is None:
            import requests
            self._http = requests.Session()
            self._http.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        return self._http

    def buscar_link_http(self, pagina_url: str, extensiones) -> str | None:
        """Lee una página y devuelve el primer link que termine en alguna extensión."""
        try:
            self.log(f"Consultando página: {pagina_url}")
            r = self._sesion_http().get(pagina_url, timeout=20)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            self.log(f"Aviso: no se pudo leer la página ({e})")
            return None
        exts = "|".join(re.escape(e.lstrip(".")) for e in extensiones)
        m = re.search(rf"href=[\"']([^\"']*\.(?:{exts}))[\"']", r.text, re.IGNORECASE)
        if not m:
            self.log("No se encontró el link en la página.")
            return None
        url = urljoin(pagina_url, m.group(1))
        self.log(f"Link encontrado: {url}")
        return url

    def bajar_http(self, url: str, referer: str | None = None):
        """Descarga por HTTP. Devuelve (archivo temporal, nombre original del archivo)."""
        import requests
        self.log(f"Descargando {url}")
        try:
            r = self._sesion_http().get(
                url, timeout=120, stream=True, headers={"Referer": referer} if referer else None
            )
            r.raise_for_status()
        except requests.RequestException as e:
            raise ProveedorError(f"Error HTTP al descargar: {e}") from e
        nombre = nombre_original(r.headers.get("Content-Disposition", ""), r.url)
        tmp = self._destino / f"_tmp_{self.nombre_clave}_{nombre}"
        total = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        self.log(f"Descargado {nombre} ({total / 1024:.1f} KB)")
        return tmp, nombre

    # ── Guardado final ───────────────────────────────────────────────────────
    def guardar_final(self, tmp: Path, nombre_salida: str, acepta_html=False) -> str:
        """Guarda con el nombre final. Descomprime ZIP y valida que no sea una página web."""
        tmp = Path(tmp)
        destino = self._destino / nombre_salida
        ext_esperada = destino.suffix.lower().lstrip(".")
        tipo = tipo_real(tmp)

        if tipo == "zip" and ext_esperada != "zip":
            with zipfile.ZipFile(tmp) as z:
                nombres = [n for n in z.namelist() if not n.endswith("/")]
                elegido = next((n for n in nombres if Path(n).name.lower() == nombre_salida.lower()), None) \
                    or next((n for n in nombres if n.lower().endswith("." + ext_esperada)), None) \
                    or (nombres[0] if nombres else None)
                if not elegido:
                    raise ProveedorError("El ZIP descargado está vacío")
                self.log(f"ZIP descomprimido: {elegido}")
                datos = z.read(elegido)
            tmp.unlink(missing_ok=True)
            tmp = self._destino / f"_tmp_{self.nombre_clave}_{Path(elegido).name}"
            tmp.write_bytes(datos)
            tipo = tipo_real(tmp)

        if tipo == "html" and not (acepta_html or ext_esperada == "xls"):
            diag = Path(getattr(self, "carpeta_diagnostico", None) or self._destino / "_diagnostico")
            diag.mkdir(parents=True, exist_ok=True)
            mal = diag / f"{self.nombre_clave}_descarga_era_pagina.html"
            tmp.replace(mal)
            raise ProveedorError(
                f"Se descargó una página web en vez del archivo (guardada en {mal}). "
                "Probablemente la sesión no inició o el link no es el correcto."
            )

        # Si el contenido real es de otro tipo de Excel, avisar y usar la extensión correcta
        if tipo in ("xlsx", "xls") and ext_esperada in ("xlsx", "xls") and tipo != ext_esperada:
            self.log(f"Aviso: el archivo es .{tipo} (no .{ext_esperada}); se guarda con extensión .{tipo}")
            destino = destino.with_suffix("." + tipo)
        elif ext_esperada in ("xlsx", "xls") and tipo not in ("xlsx", "xls", "html"):
            real = Path(tmp.name).suffix.lower()
            if real in (".csv", ".txt"):
                self.log(f"Aviso: llegó un {real}, se guarda con esa extensión")
                destino = destino.with_suffix(real)

        tmp.replace(destino)
        return str(destino)
