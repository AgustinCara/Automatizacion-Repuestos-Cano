# proveedores/proveedor_bba.py
"""
Proveedor: Cromosol (www.slaweb.com.ar)
Archivo:   cromosol.xlsx
Recorrido: login -> Catálogo -> ícono de descarga junto a "Catálogo"
           -> ventana "Lista de Precios" -> Empresa: BBA -> DESCARGAR

Para instalarlo en la PC del cliente: botón "Agregar proveedor" de la app.
Al importarlo, 'config_inicial' se copia a config.json (sin pisar datos existentes).
"""
import time

from proveedores.base import BaseProveedor, ProveedorError
from proveedores._web import FlujoWebMixin


class ProveedorBba(FlujoWebMixin, BaseProveedor):
    nombre_clave = "cromosol"
    nombre_display = "Cromosol"

    # Se copia a config.json al importar el proveedor
    config_inicial = {
        "_descripcion": "Cromosol — Lista de precios XLSX (slaweb, requiere login)",
        "login_url": "http://www.slaweb.com.ar",
        "download_page": "http://www.slaweb.com.ar/products?page=0&size=36&sort=codeSort,asc",
        "usuario": "000889",
        "password": "Repuestoscano1",
        "empresa": "Cromosol",
        "extension": "csv",
        "nombre_archivo": "cromosol.csv",
    }

    def pasos(self, page, cfg):
        empresa = cfg.get("empresa", "Cromosol")

        # 1. Login (slaweb funciona por http, no https)
        page = self.login(page, cfg, ["http://www.slaweb.com.ar"])

        # 2. Catálogo
        self.ir_a(page, cfg.get("download_page",
                                "http://www.slaweb.com.ar/products?page=0&size=36&sort=codeSort,asc"))

        # 3. Ícono de descarga al lado de "Catálogo" -> abre la ventana "Lista de Precios"
        self._abrir_lista_de_precios(page)

        # 4. En la ventana: Empresa = Cromosol
        self._elegir_empresa(page, empresa)

        # 5. DESCARGAR (el archivo se genera en el servidor: puede tardar)
        boton = self._boton_descargar_de_la_ventana(page)
        self.log("Clic en DESCARGAR, esperando el archivo...")
        tmp = self._descargar_con(page, lambda: boton.click(),
                                  timeout=int(cfg.get("espera_max_ms", 300000)),
                                  extensiones=["xlsx", "xls", "csv", "zip"])
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "cromosol.csv"))

    # ── Pasos de la ventana "Lista de Precios" ──────────────────────────────
    def _ventana_visible(self, page) -> bool:
        return page.evaluate(
            """() => Array.from(document.querySelectorAll('select[multiple]'))
                     .some(s => s.offsetWidth || s.offsetHeight)"""
        )

    def _abrir_lista_de_precios(self, page):
        self.log("Abriendo 'Lista de Precios' (ícono junto a Catálogo)...")
        fin = time.time() + 20
        while time.time() < fin:
            marcado = page.evaluate(
                """() => {
                    const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
                    document.querySelectorAll('[data-cano-icono]').forEach(e => e.removeAttribute('data-cano-icono'));
                    const clic = e => e.closest('a, button, [role=button], [onclick], [data-toggle], [data-bs-toggle]') || e;
                    // a) la "miga de pan": un contenedor chico con "Inicio" y "Catálogo"
                    const norm = s => (s || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
                    const migas = Array.from(document.querySelectorAll('body *')).filter(e => vis(e) &&
                        norm(e.textContent).includes('inicio') && norm(e.textContent).includes('catalogo') &&
                        e.textContent.trim().length < 60);
                    for (const m of migas.reverse()) {
                        const iconos = Array.from(m.querySelectorAll('i, svg, img, span[class*=icon], [class*=download]')).filter(vis);
                        if (iconos.length) { clic(iconos[iconos.length - 1]).setAttribute('data-cano-icono', '1'); return true; }
                    }
                    // b) cualquier ícono de descarga visible
                    const ic = Array.from(document.querySelectorAll(
                        '[class*=fa-download], [class*=glyphicon-download], [class*=icon-download], ' +
                        '[title*=escarg], [title*=ista de precio], [aria-label*=escarg]')).find(vis);
                    if (ic) { clic(ic).setAttribute('data-cano-icono', '1'); return true; }
                    return false;
                }"""
            )
            if marcado:
                page.locator("[data-cano-icono='1']").first.click()
                for _ in range(20):  # esperar que se abra la ventana
                    page.wait_for_timeout(500)
                    if self._ventana_visible(page):
                        self.log("Ventana 'Lista de Precios' abierta.")
                        return
            page.wait_for_timeout(1000)
        raise ProveedorError("No se pudo abrir la ventana 'Lista de Precios' (ícono junto a Catálogo)")

    def _elegir_empresa(self, page, empresa):
        """Elige la empresa en la lista 'Empresa' de la ventana (no en los filtros de la izquierda)."""
        listas = page.locator("select[multiple]")
        for i in range(listas.count()):
            lista = listas.nth(i)
            if not lista.is_visible():
                continue
            opciones = [o.strip() for o in lista.locator("option").all_inner_texts()]
            elegida = next((o for o in opciones if o.lower() == empresa.lower()), None)
            if elegida:
                lista.select_option(label=elegida)  # deja SOLO esta empresa seleccionada
                self.log(f"Empresa seleccionada: {elegida}")
                page.wait_for_timeout(800)
                return
        raise ProveedorError(f"No se encontró la empresa '{empresa}' en la ventana 'Lista de Precios'")

    def _boton_descargar_de_la_ventana(self, page):
        """
        El botón DESCARGAR que está en la misma ventana que las listas.
        Acepta cualquier tipo de elemento (button, link, div, span, input) cuyo
        texto sea "Descargar", aunque tenga espacios, mayúsculas o un ícono.
        """
        marcado = page.evaluate(
            r"""() => {
                const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
                const norm = s => (s || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
                const texto = e => norm(e.tagName === 'INPUT' ? e.value : e.textContent);
                document.querySelectorAll('[data-cano-descargar]').forEach(e => e.removeAttribute('data-cano-descargar'));

                // Todos los elementos visibles que dicen "descargar" (el más interno)
                const cands = Array.from(document.querySelectorAll('body *')).filter(e =>
                    vis(e) && /^descargar\b/.test(texto(e)) && texto(e).length < 30 &&
                    !Array.from(e.children).some(h => /^descargar\b/.test(texto(h))));
                if (!cands.length) return 'sin_candidatos';

                // Quedarse con el que está en la misma ventana que la lista de empresas
                const lista = Array.from(document.querySelectorAll('select[multiple]')).find(vis);
                let elegido = null;
                if (lista) {
                    for (let c = lista.parentElement; c && !elegido; c = c.parentElement)
                        elegido = cands.find(x => c.contains(x));
                }
                elegido = elegido || cands[cands.length - 1];
                const clic = elegido.closest('button, a, [role=button], input, [onclick]') || elegido;
                clic.setAttribute('data-cano-descargar', '1');
                return 'ok';
            }"""
        )
        if marcado != "ok":
            # Último intento con el buscador de Playwright
            loc = page.get_by_text("Descargar", exact=True)
            for i in range(loc.count() - 1, -1, -1):
                if loc.nth(i).is_visible():
                    return loc.nth(i)
            raise ProveedorError("No se encontró el botón DESCARGAR en la ventana 'Lista de Precios'")
        return page.locator("[data-cano-descargar='1']").first
