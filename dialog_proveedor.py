# dialog_proveedor.py
"""
Diálogo modal interactivo para agregar y configurar nuevos proveedores
directamente desde la interfaz gráfica sin escribir código manualmente.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

# Constantes de diseño (coincidentes con app.py)
C_BG = "#d0d0d0"
C_PANEL = "#f5f5f5"
C_SURFACE = "#ffffff"
C_ACCENT = "#4f8ef7"
C_ACCENT2 = "#6c63ff"
C_SUCCESS = "#22c55e"
C_TEXT = "#0f1117"
C_TEXT_DIM = "#555555"
C_BORDER = "#d1d1d1"


import unicodedata

def normalizar_clave(texto: str) -> str:
    """Convierte 'Distem S.R.L.' en 'distem_s_r_l' o 'distem' removiendo tildes."""
    s = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s or "nuevo_proveedor"



def generar_codigo_proveedor(
    nombre_clave: str,
    nombre_display: str,
    tipo: str,
    extension: str,
    url_principal: str,
    download_url: str = "",
    selector_descarga: str = "",
    selector_previo: str = "",
    user_sel: str = "",
    pass_sel: str = "",
    submit_sel: str = "",
) -> str:
    """Genera el código Python para un módulo de proveedor que hereda de BaseProveedor."""
    
    clase_nombre = f"Proveedor{''.join(word.capitalize() for word in nombre_clave.split('_'))}"
    ext = extension.lower().lstrip(".")

    doc_header = f'"""\nProveedor: {nombre_display}\nTipo: {tipo.upper()}\nGenerado automáticamente desde el Asistente de la App.\n"""'

    if tipo == "directa":
        codigo = f'''# proveedores/proveedor_{nombre_clave}.py
{doc_header}

from __future__ import annotations
import requests
from pathlib import Path
from proveedores.base import BaseProveedor, ProveedorError


class {clase_nombre}(BaseProveedor):
    """Proveedor {nombre_display} — Descarga Directa HTTP."""

    nombre_clave = "{nombre_clave}"
    nombre_display = "{nombre_display}"

    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        destino = Path(directorio_destino)
        destino.mkdir(parents=True, exist_ok=True)

        cfg = self.cfg_proveedor()
        url_descarga = cfg.get("url_descarga", "{url_principal}")
        extension = cfg.get("extension", "{ext}")

        self.log(f"Iniciando descarga directa desde: {{url_descarga}}")

        try:
            resp = requests.get(
                url_descarga,
                timeout=90,
                headers={{
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }},
                stream=True
            )
            resp.raise_for_status()

            nombre = self.nombre_archivo(extension)
            ruta_final = destino / nombre

            with open(ruta_final, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            tamano_kb = ruta_final.stat().st_size / 1024
            self.log(f"Archivo guardado: {{ruta_final.name}} ({{tamano_kb:.1f}} KB) ✓")
            return self.descomprimir_si_es_zip(ruta_final)

        except Exception as e:
            raise ProveedorError(f"Error al descargar de {nombre_display}: {{e}}") from e
'''

    else:
        # Tipo login Playwright
        u_sel = user_sel or "input[name='usuario'], input[name='username'], #usuario, #username, input[type='text']"
        p_sel = pass_sel or "input[type='password']"
        sub_sel = submit_sel or "button[type='submit'], input[type='submit'], #btn-login, #login"
        d_url = download_url or url_principal

        codigo = f'''# proveedores/proveedor_{nombre_clave}.py
{doc_header}

from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from proveedores.base import BaseProveedor, ProveedorError


class {clase_nombre}(BaseProveedor):
    """Proveedor {nombre_display} — Descarga mediante Web / Login."""

    nombre_clave = "{nombre_clave}"
    nombre_display = "{nombre_display}"

    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        destino = Path(directorio_destino)
        destino.mkdir(parents=True, exist_ok=True)

        cfg = self.cfg_proveedor()
        login_url = cfg.get("login_url", "{url_principal}")
        download_page = cfg.get("download_page", "{d_url}")
        usuario = cfg.get("usuario", "")
        password = cfg.get("password", "")
        extension = cfg.get("extension", "{ext}")
        sel_prev = cfg.get("selector_previo", "{selector_previo}")
        sel_btn = cfg.get("selector_boton_csv", "{selector_descarga}")

        if not usuario or not password:
            raise ProveedorError("Faltan usuario y/or contraseña en config.json para {nombre_display}")

        self.log("Iniciando navegador Playwright...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                # 1. Login
                self.log(f"Navegando a formulario de login: {{login_url}}")
                page.goto(login_url, wait_until="domcontentloaded", timeout=45000)

                # Rellenar formulario
                page.fill("{u_sel}", usuario)
                page.fill("{p_sel}", password)
                page.click("{sub_sel}")
                page.wait_for_timeout(3000)

                # 2. Navegar a página o link de descarga
                if download_page and download_page != login_url:
                    self.log(f"Navegando a página de descarga: {{download_page}}")
                    page.goto(download_page, wait_until="domcontentloaded", timeout=45000)

                # 3. Acción previa (ej: clic en 'MARCAR TODAS' o filtros)
                if sel_prev:
                    self.log(f"Ejecutando clic previo en: {{sel_prev}}")
                    if sel_prev.startswith(("#", ".", "[", "xpath=", "text=")):
                        selectores_candidatos = [sel_prev]
                    else:
                        selectores_candidatos = [
                            f"label:has-text('{{sel_prev}}')",
                            f"text={{sel_prev}}",
                            f"span:has-text('{{sel_prev}}')",
                        ]
                    clic_ok = False
                    for sel_candidato in selectores_candidatos:
                        try:
                            page.click(sel_candidato, timeout=5000)
                            page.wait_for_timeout(1000)
                            clic_ok = True
                            self.log(f"Clic previo exitoso: {{sel_candidato}}")
                            break
                        except Exception:
                            continue
                    if not clic_ok:
                        self.log(f"Aviso: no se encontró '{{sel_prev}}', se continúa sin ese clic.")

                # 4. Disparar descarga
                self.log("Iniciando descarga de archivo...")
                if sel_btn:
                    # Determinar el tipo de selector (si es CSS/ID/XPath o texto visible)
                    if sel_btn.startswith(("#", ".", "[", "a", "button", "input", "div", "xpath=", "text=")) or ":" in sel_btn or "=" in sel_btn:
                        target_sel = sel_btn
                    else:
                        target_sel = f"text={{sel_btn}}"

                    with page.expect_download(timeout=60000) as download_info:
                        page.click(target_sel)
                    download = download_info.value
                else:
                    # Si no hay selector especificado, intentar esperar descarga por clic o link
                    try:
                        with page.expect_download(timeout=60000) as download_info:
                            # Hacer clic en el primer enlace o botón con texto de descarga o extensión
                            page.click(f"a[href*='{{extension}}'], button:has-text('Descargar'), a:has-text('Descargar')", timeout=15000)
                        download = download_info.value
                    except Exception:
                        # Si no hay descarga directa, navegar directamente a la URL de descarga
                        with page.expect_download(timeout=60000) as download_info:
                            page.goto(download_page)
                        download = download_info.value

                nombre = self.nombre_archivo(extension)
                ruta_final = destino / nombre
                download.save_as(ruta_final)

                tamano_kb = ruta_final.stat().st_size / 1024
                self.log(f"Archivo guardado con éxito: {{ruta_final.name}} ({{tamano_kb:.1f}} KB) ✓")
                
                browser.close()
                return self.descomprimir_si_es_zip(ruta_final)

        except PWTimeout as e:
            raise ProveedorError(f"Tiempo de espera agotado al descargar de {nombre_display}: {{e}}") from e
        except Exception as e:
            raise ProveedorError(f"Error en flujo de {nombre_display}: {{e}}") from e
'''

    return codigo


class VentanaAgregarProveedor(ctk.CTkToplevel):
    """Ventana modal de diálogo para agregar un nuevo proveedor."""

    def __init__(self, master, base_dir: Path, config_path: Path, on_success_callback=None):
        super().__init__(master)

        self.base_dir = base_dir
        self.config_path = config_path
        self.on_success_callback = on_success_callback

        self.title("➕ Agregar Nuevo Proveedor")
        self.geometry("640x700")
        self.resizable(False, False)
        self.configure(fg_color=C_BG)

        # Hacer la ventana modal sobre la app principal
        self.transient(master)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # Frame contenedor
        container = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=12)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            header,
            text="✨ Configuración de Nuevo Proveedor",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=C_TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Completá los datos del proveedor. Se guardará en config.json y se creará el script automáticamente.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C_TEXT_DIM,
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # Scrollable form
        form = ctk.CTkScrollableFrame(container, fg_color=C_SURFACE, corner_radius=10)
        form.pack(fill="both", expand=True, padx=20, pady=(8, 12))

        # 1. Nombre del Proveedor
        ctk.CTkLabel(form, text="Nombre del Proveedor *", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(10, 2))
        self.var_nombre = ctk.StringVar()
        entry_nombre = ctk.CTkEntry(form, textvariable=self.var_nombre, placeholder_text="Ej: Repuestos Sur S.A.", height=35)
        entry_nombre.pack(fill="x", padx=10, pady=(0, 10))

        # 2. Tipo de descarga
        ctk.CTkLabel(form, text="Tipo de descarga *", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        self.var_tipo = ctk.StringVar(value="directa")

        segmented = ctk.CTkSegmentedButton(
            form,
            values=["Directa (HTTP)", "Web con Login"],
            command=self._on_tipo_changed,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACCENT2,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        segmented.set("Directa (HTTP)")
        segmented.pack(fill="x", padx=10, pady=(0, 12))

        # 3. URL principal
        self.lbl_url_principal = ctk.CTkLabel(form, text="URL del archivo o página de descarga *", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT)
        self.lbl_url_principal.pack(anchor="w", padx=10, pady=(5, 2))
        self.var_url_principal = ctk.StringVar()
        ctk.CTkEntry(form, textvariable=self.var_url_principal, placeholder_text="https://proveedor.com/downloads/lista.xlsx", height=35).pack(fill="x", padx=10, pady=(0, 10))

        # 4. Extensión esperada
        ctk.CTkLabel(form, text="Extensión del archivo descargado", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        self.var_extension = ctk.StringVar(value="xlsx")
        ctk.CTkOptionMenu(
            form,
            values=["xlsx", "csv", "dbf", "zip", "xls", "txt"],
            variable=self.var_extension,
            button_color=C_ACCENT,
            fg_color=C_PANEL,
            text_color=C_TEXT,
            height=32,
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # Frame de campos dinámicos para LOGIN
        self.login_frame = ctk.CTkFrame(form, fg_color="transparent")
        
        # Credenciales
        ctk.CTkLabel(self.login_frame, text="Usuario *", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        self.var_usuario = ctk.StringVar()
        ctk.CTkEntry(self.login_frame, textvariable=self.var_usuario, placeholder_text="Nombre de usuario o código", height=35).pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.login_frame, text="Contraseña *", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        self.var_password = ctk.StringVar()
        ctk.CTkEntry(self.login_frame, textvariable=self.var_password, show="•", placeholder_text="Contraseña", height=35).pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.login_frame, text="URL de descarga post-login (opcional)", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        self.var_download_page = ctk.StringVar()
        ctk.CTkEntry(self.login_frame, textvariable=self.var_download_page, placeholder_text="Dejar vacío si es la misma URL", height=35).pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.login_frame, text="Acción o clic previo antes de descargar (Opcional)", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        ctk.CTkLabel(
            self.login_frame,
            text="Útil si hay que hacer un clic previo antes de descargar (ej: 'MARCAR TODAS' o filtros).",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C_TEXT_DIM,
            justify="left",
            wraplength=540,
        ).pack(anchor="w", padx=10, pady=(0, 4))
        self.var_selector_previo = ctk.StringVar()
        ctk.CTkEntry(
            self.login_frame,
            textvariable=self.var_selector_previo,
            placeholder_text="Ej: MARCAR TODAS, o dejar vacío",
            height=35
        ).pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.login_frame, text="Botón o enlace de descarga (Opcional)", font=ctk.CTkFont(weight="bold"), text_color=C_TEXT).pack(anchor="w", padx=10, pady=(5, 2))
        ctk.CTkLabel(
            self.login_frame,
            text="Podés indicar el texto visible del botón (ej: Descargar CSV Precios), un selector CSS (#btn-descargar), o dejarlo vacío para detección automática.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C_TEXT_DIM,
            justify="left",
            wraplength=540,
        ).pack(anchor="w", padx=10, pady=(0, 4))
        self.var_selector_descarga = ctk.StringVar()
        ctk.CTkEntry(
            self.login_frame,
            textvariable=self.var_selector_descarga,
            placeholder_text="Ej: Descargar CSV Precios, #btn-descargar, o dejar vacío",
            height=35
        ).pack(fill="x", padx=10, pady=(0, 10))

        # Botones de acción al final
        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 16))
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions,
            text="Cancelar",
            command=self.destroy,
            fg_color=C_PANEL,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            height=38,
            corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            actions,
            text="💾 Guardar Proveedor",
            command=self._guardar_proveedor,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            text_color="#ffffff",
            font=ctk.CTkFont(weight="bold"),
            height=38,
            corner_radius=8,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _on_tipo_changed(self, val: str):
        if val == "Directa (HTTP)":
            self.var_tipo.set("directa")
            self.lbl_url_principal.configure(text="URL del archivo o página de descarga *")
            self.login_frame.pack_forget()
        else:
            self.var_tipo.set("login")
            self.lbl_url_principal.configure(text="URL del formulario de Iniciar Sesión (Login) *")
            self.login_frame.pack(fill="x", pady=5)

    def _guardar_proveedor(self):
        nombre_display = self.var_nombre.get().strip()
        if not nombre_display:
            messagebox.showerror("Campo requerido", "Por favor ingresá el nombre del proveedor.", parent=self)
            return

        url_principal = self.var_url_principal.get().strip()
        if not url_principal:
            messagebox.showerror("Campo requerido", "Por favor ingresá la URL del proveedor.", parent=self)
            return

        tipo = self.var_tipo.get()
        usuario = self.var_usuario.get().strip()
        password = self.var_password.get().strip()

        if tipo == "login" and (not usuario or not password):
            messagebox.showerror("Campo requerido", "Para proveedores con login debés ingresar Usuario y Contraseña.", parent=self)
            return

        nombre_clave = normalizar_clave(nombre_display)
        extension = self.var_extension.get().strip().lstrip(".") or "xlsx"

        # 1. Actualizar config.json
        try:
            config_data = {}
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

            if "proveedores" not in config_data:
                config_data["proveedores"] = {}

            nuevo_entry = {
                "_descripcion": f"{nombre_display} (Agregado desde GUI)",
                "extension": extension,
            }

            if tipo == "directa":
                nuevo_entry["url_descarga"] = url_principal
            else:
                nuevo_entry["login_url"] = url_principal
                nuevo_entry["download_page"] = self.var_download_page.get().strip() or url_principal
                nuevo_entry["usuario"] = usuario
                nuevo_entry["password"] = password
                if self.var_selector_previo.get().strip():
                    nuevo_entry["selector_previo"] = self.var_selector_previo.get().strip()
                if self.var_selector_descarga.get().strip():
                    nuevo_entry["selector_boton_csv"] = self.var_selector_descarga.get().strip()

            config_data["proveedores"][nombre_clave] = nuevo_entry

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            messagebox.showerror("Error de guardado", f"No se pudo actualizar config.json: {e}", parent=self)
            return

        # 2. Generar archivo Python en /proveedores/proveedor_<clave>.py
        dir_proveedores = self.base_dir / "proveedores"
        dir_proveedores.mkdir(exist_ok=True)
        archivo_py = dir_proveedores / f"proveedor_{nombre_clave}.py"

        try:
            codigo_py = generar_codigo_proveedor(
                nombre_clave=nombre_clave,
                nombre_display=nombre_display,
                tipo=tipo,
                extension=extension,
                url_principal=url_principal,
                download_url=self.var_download_page.get().strip(),
                selector_descarga=self.var_selector_descarga.get().strip(),
                selector_previo=self.var_selector_previo.get().strip(),
            )
            with open(archivo_py, "w", encoding="utf-8") as f:
                f.write(codigo_py)

        except Exception as e:
            messagebox.showerror("Error al generar script", f"No se pudo crear el archivo {archivo_py.name}: {e}", parent=self)
            return

        # 3. Notificar éxito y cerrar modal
        messagebox.showinfo(
            "¡Proveedor guardado!",
            f"El proveedor '{nombre_display}' se agregó correctamente.\nScript creado: {archivo_py.name}",
            parent=self,
        )

        if self.on_success_callback:
            self.on_success_callback(nombre_display, nombre_clave)

        self.destroy()
