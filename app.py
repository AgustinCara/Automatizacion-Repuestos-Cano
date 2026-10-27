# app.py — Interfaz Gráfica Principal
# Repuestos CANO — Descargador de Listas de Precios
# =====================================================================
# Requisitos previos:
#   pip install -r requirements.txt
#   playwright install chromium
# =====================================================================

from __future__ import annotations

import json
import os
import platform
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

# ── Importar el registro de proveedores ────────────────────────────────────────
# Ajustamos sys.path para que los imports relativos funcionen si se ejecuta
# directamente desde cualquier directorio.
_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from proveedores import PROVEEDORES, PROVEEDORES_DIR, cargar_proveedores
from dialog_proveedor import VentanaAgregarProveedor
from tkinter import messagebox


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE DISEÑO
# ══════════════════════════════════════════════════════════════════════════════

APP_TITLE   = "Repuestos CANO · Descargador de Listas de Precios"
APP_VERSION = "v1.0.0"

# Paleta de colores personalizada
# C_BG        = "#E2E8F0"   # Fondo principal (casi negro azulado)
# C_BG        = "#808080"   # Fondo principal (gris)
C_BG        = "#d0d0d0"   # Fondo principal (gris medio)
C_PANEL     = "#f5f5f5"   # Paneles y sidebar
C_SURFACE   = "#f5f5f5"   # Superficie de tarjetas
C_ACCENT    = "#4f8ef7"   # Azul acento principal
C_ACCENT2   = "#6c63ff"   # Violeta secundario
C_SUCCESS   = "#22c55e"   # Verde éxito
C_WARNING   = "#f59e0b"   # Amarillo advertencia
C_ERROR     = "#ef4444"   # Rojo error
C_TEXT      = "#0f1117"   # Texto principal
C_TEXT_DIM  = "#0f1117"   # Texto secundario/opaco
C_BORDER    = "#d1d1d1"   # Bordes sutiles


# Directorio de descarga por defecto según SO
if platform.system() == "Windows":
    _DEFAULT_DIR = "C:\\Repuestos\\Descargas_Precios"
else:
    _DEFAULT_DIR = str(Path.home() / "Repuestos" / "Descargas_Precios")

_CONFIG_PATH = _BASE_DIR / "config.json"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _leer_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _guardar_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    """Ventana raíz de la aplicación."""

    def __init__(self):
        super().__init__()

        # ── Tema y apariencia ──────────────────────────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=C_BG)

        self.title(f"{APP_TITLE}  {APP_VERSION}")
        self.geometry("1100x720")
        self.minsize(900, 600)

        # ── Cola de mensajes de log (thread-safe) ─────────────────────────
        self._log_queue: queue.Queue[str | None] = queue.Queue()

        # ── Estado interno ────────────────────────────────────────────────
        self._descargando = False
        self._thread: threading.Thread | None = None
        self._cfg = _leer_config()
        self._check_vars: dict[str, ctk.BooleanVar] = {}

        # ── Construir UI ──────────────────────────────────────────────────
        self._build_layout()
        self._start_log_poller()

    # ──────────────────────────────────────────────────────────────────────────
    # CONSTRUCCIÓN DEL LAYOUT
    # ──────────────────────────────────────────────────────────────────────────

    def _build_layout(self):
        """Construye el layout de dos columnas: sidebar izquierdo + área principal."""

        self.grid_columnconfigure(0, weight=0)   # sidebar fijo
        self.grid_columnconfigure(1, weight=1)   # área principal crece
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0, width=300)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(4, weight=1)

        # Logo / título
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(28, 8), sticky="ew")

        ctk.CTkLabel(
            logo_frame,
            text="🔧",
            font=ctk.CTkFont(size=38),
            text_color=C_ACCENT,
        ).pack(side="left", padx=(0, 10))

        title_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_frame.pack(side="left", fill="x")
        ctk.CTkLabel(
            title_frame, text="Repuestos CANO",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=C_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame, text="Descargador de Precios",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C_TEXT_DIM,
        ).pack(anchor="w")

        # Separador
        ctk.CTkFrame(sidebar, fg_color=C_BORDER, height=1).grid(
            row=1, column=0, padx=16, pady=4, sticky="ew"
        )

        # ── Panel de proveedores ───────────────────────────────────────────
        prov_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        prov_frame.grid(row=2, column=0, padx=16, pady=(10, 0), sticky="ew")

        ctk.CTkLabel(
            prov_frame,
            text="PROVEEDORES",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C_TEXT_DIM,
        ).pack(anchor="w", pady=(0, 8))

        # Checkboxes por proveedor
        self._scroll_prov = ctk.CTkScrollableFrame(
            sidebar, fg_color=C_SURFACE, corner_radius=10, height=220
        )
        self._scroll_prov.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")

        # Renderizar checkboxes inicialmente
        self._render_provider_checkboxes()

        # Botones seleccionar / desmarcar todos e importar proveedor
        btn_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=16, pady=4, sticky="new")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame,
            text="✔ Todos",
            command=lambda: self._toggle_all(True),
            height=30,
            fg_color=C_SURFACE,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=ctk.CTkFont(size=11),
            corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            btn_frame,
            text="✖ Ninguno",
            command=lambda: self._toggle_all(False),
            height=30,
            fg_color=C_SURFACE,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            font=ctk.CTkFont(size=11),
            corner_radius=8,
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        ctk.CTkButton(
            btn_frame,
            text="➕ Agregar Proveedor",
            command=self._abrir_asistente_proveedor,
            height=34,
            fg_color=C_ACCENT2,
            hover_color=C_ACCENT,
            text_color="#ffffff",
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=8,
        ).grid(row=1, column=0, columnspan=2, padx=0, pady=(6, 0), sticky="ew")

        ctk.CTkButton(
            btn_frame,
            text="📥 Importar módulo .py",
            command=self._importar_proveedor,
            height=28,
            fg_color="transparent",
            hover_color=C_BORDER,
            text_color=C_TEXT_DIM,
            font=ctk.CTkFont(size=10),
            corner_radius=6,
        ).grid(row=2, column=0, columnspan=2, padx=0, pady=(4, 0), sticky="ew")




        # ── Versión ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            sidebar,
            text=APP_VERSION,
            font=ctk.CTkFont(size=10),
            text_color=C_TEXT_DIM,
        ).grid(row=7, column=0, pady=(0, 12))

    # ── Área principal ─────────────────────────────────────────────────────────

    def _build_main_area(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # ── Header con selector de carpeta ────────────────────────────────
        header = ctk.CTkFrame(main, fg_color=C_PANEL, corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="📁  Carpeta de destino:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=C_TEXT,
        ).grid(row=0, column=0, padx=(20, 10), pady=24, sticky="w")

        saved_dir = self._cfg.get("configuracion_global", {}).get(
            "directorio_descarga_default", _DEFAULT_DIR
        )
        self._dir_var = ctk.StringVar(value=saved_dir)

        dir_entry = ctk.CTkEntry(
            header,
            textvariable=self._dir_var,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=C_SURFACE,
            border_color=C_BORDER,
            text_color=C_TEXT,
            height=38,
            corner_radius=8,
        )
        dir_entry.grid(row=0, column=1, padx=(0, 8), pady=21, sticky="ew")

        ctk.CTkButton(
            header,
            text="Examinar…",
            command=self._elegir_directorio,
            fg_color=C_SURFACE,
            hover_color=C_BORDER,
            text_color=C_TEXT,
            height=38,
            width=100,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=2, padx=(0, 20), pady=21)

        # ── Área de log ────────────────────────────────────────────────────
        log_container = ctk.CTkFrame(main, fg_color=C_SURFACE, corner_radius=12)
        log_container.grid(row=1, column=0, padx=20, pady=(16, 8), sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        log_container.grid_rowconfigure(1, weight=1)
        log_container.grid_columnconfigure(0, weight=1)

        # Header del log
        log_header = ctk.CTkFrame(log_container, fg_color="transparent")
        log_header.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        log_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            log_header,
            text="📋  Consola de estado",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=C_TEXT,
        ).grid(row=0, column=0, sticky="w")

        self._limpiar_btn = ctk.CTkButton(
            log_header,
            text="Limpiar",
            command=self._limpiar_log,
            width=80,
            height=26,
            fg_color=C_PANEL,
            hover_color=C_BORDER,
            text_color=C_TEXT_DIM,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
        )
        self._limpiar_btn.grid(row=0, column=1, sticky="e")

        # Textbox de log (scrollable, monospace)
        self._log_box = ctk.CTkTextbox(
            log_container,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=C_PANEL,
            text_color=C_TEXT,
            corner_radius=8,
            wrap="word",
            state="disabled",
        )
        self._log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        # Configurar tags de color para el log
        self._log_box.tag_config("success",  foreground=C_SUCCESS)
        self._log_box.tag_config("error",    foreground=C_ERROR)
        self._log_box.tag_config("warning",  foreground=C_WARNING)
        self._log_box.tag_config("accent",   foreground=C_ACCENT)
        self._log_box.tag_config("dim",      foreground=C_TEXT_DIM)

        # ── Barra de progreso + botón principal ───────────────────────────
        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        # Barra de progreso
        self._progress = ctk.CTkProgressBar(
            footer,
            fg_color=C_SURFACE,
            progress_color=C_ACCENT,
            height=8,
            corner_radius=4,
        )
        self._progress.grid(row=0, column=0, columnspan=2, pady=(0, 12), sticky="ew")
        self._progress.set(0)

        # Etiqueta de estado de la barra de progreso
        self._progress_label = ctk.CTkLabel(
            footer,
            text="Listo para descargar.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C_TEXT_DIM,
        )
        self._progress_label.grid(row=1, column=0, sticky="w")

        # Botón principal de descarga
        self._btn_descargar = ctk.CTkButton(
            footer,
            text="Descargar Listas de Precios",
            command=self._iniciar_descarga,
            height=46,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            corner_radius=12,
            text_color="#ffffff",
        )
        self._btn_descargar.grid(row=1, column=1, padx=(16, 0))

        # Mensaje inicial en el log
        self._log_append(
            f"  Repuestos CANO — Descargador de Listas de Precios  {APP_VERSION}\n",
            tag="accent",
        )
        self._log_append(
            "  Seleccioná los proveedores, elegí la carpeta y presioná 'Descargar'.\n",
            tag="dim",
        )
        self._log_append("─" * 72 + "\n", tag="dim")

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA DE DESCARGA (THREAD)
    # ══════════════════════════════════════════════════════════════════════════

    def _iniciar_descarga(self):
        """Valida la selección y lanza el hilo de descarga."""

        if self._descargando:
            return

        seleccionados = [n for n, v in self._check_vars.items() if v.get()]
        if not seleccionados:
            self._log_append("⚠ No hay ningún proveedor seleccionado.\n", tag="warning")
            return

        directorio = self._dir_var.get().strip()
        if not directorio:
            self._log_append("⚠ Especificá una carpeta de destino.\n", tag="warning")
            return

        # Guardar directorio en config releyendo de disco primero
        self._cfg = _leer_config()
        if "configuracion_global" not in self._cfg:
            self._cfg["configuracion_global"] = {}
        self._cfg["configuracion_global"]["directorio_descarga_default"] = directorio
        _guardar_config(self._cfg)


        self._descargando = True
        self._btn_descargar.configure(
            state="disabled",
            text="⏳  Descargando...",
            fg_color=C_TEXT_DIM,
        )
        self._progress.set(0)

        self._thread = threading.Thread(
            target=self._worker_descarga,
            args=(seleccionados, directorio),
            daemon=True,
        )
        self._thread.start()

    def _worker_descarga(
        self,
        seleccionados: list[str],
        directorio: str,
    ):
        """
        Hilo en background: itera por cada proveedor seleccionado,
        ejecuta la descarga y pone mensajes en la cola.

        Usa _log_queue para comunicarse con el hilo principal de la GUI.
        """
        # nest_asyncio permite que Playwright sync_api funcione dentro de un
        # thread que ya tiene un event loop activo (necesario en Windows con tkinter).
        import asyncio, nest_asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        nest_asyncio.apply(loop)

        total = len(seleccionados)
        exitosos = 0
        fallidos = 0

        ts_inicio = datetime.now().strftime("%H:%M:%S")
        self._encolar(f"\n[{ts_inicio}]  Iniciando descarga de {total} proveedor(es)...\n", "accent")
        self._encolar("─" * 72 + "\n", "dim")

        proveedores = cargar_proveedores()
        for i, nombre_display in enumerate(seleccionados, start=1):
            ClaseProveedor = proveedores.get(nombre_display)
            if not ClaseProveedor:
                self._encolar(f"   ✗ Error: Proveedor '{nombre_display}' no encontrado en el sistema.\n", "error")
                fallidos += 1
                continue
            self._encolar(f"\n▶  [{i}/{total}]  {nombre_display}\n", "accent")

            # Actualizar progreso
            self._encolar(("__PROGRESS__", (i - 1) / total, f"Procesando: {nombre_display}"))

            try:
                instancia = ClaseProveedor(
                    log_callback=lambda msg: self._encolar(f"   {msg}\n", "")
                )
                ruta = instancia.descargar(directorio)
                exitosos += 1
                self._encolar(f"   ✓ Completado: {ruta}\n", "success")

            except Exception as exc:
                fallidos += 1
                self._encolar(f"   ✗ Error: {exc}\n", "error")

            self._encolar("─" * 72 + "\n", "dim")

        # Resumen final
        ts_fin = datetime.now().strftime("%H:%M:%S")
        self._encolar(f"\n[{ts_fin}]  Proceso finalizado.\n", "accent")
        self._encolar(
            f"   ✓ Exitosos: {exitosos}   ✗ Fallidos: {fallidos}   Total: {total}\n",
            "success" if fallidos == 0 else "warning",
        )

        # Señal de finalización
        self._encolar(("__DONE__", exitosos, fallidos))

    def _encolar(self, msg, tag=""):
        """Encola un mensaje o una tupla de control para el hilo principal."""
        self._log_queue.put((msg, tag))

    # ══════════════════════════════════════════════════════════════════════════
    # POLLING DEL LOG (hilo de la GUI)
    # ══════════════════════════════════════════════════════════════════════════

    def _start_log_poller(self):
        """Registra el polling periódico del log en el event loop de Tk."""
        self.after(100, self._poll_log_queue)

    def _poll_log_queue(self):
        """Lee todos los mensajes pendientes en la cola y los procesa."""
        try:
            while True:
                item = self._log_queue.get_nowait()

                if isinstance(item, tuple):
                    msg, tag = item
                else:
                    msg, tag = item, ""

                # Mensajes de control especiales
                if isinstance(msg, tuple):
                    self._procesar_control(msg)
                else:
                    self._log_append(msg, tag=tag)

        except queue.Empty:
            pass
        finally:
            # Re-registrar para el próximo tick
            self.after(100, self._poll_log_queue)

    def _procesar_control(self, control: tuple):
        """Procesa mensajes de control enviados por el worker."""
        tipo = control[0]

        if tipo == "__PROGRESS__":
            _, valor, etiqueta = control
            self._progress.set(valor)
            self._progress_label.configure(text=etiqueta)

        elif tipo == "__DONE__":
            _, exitosos, fallidos = control
            self._progress.set(1.0)
            self._descargando = False
            color = C_SUCCESS if fallidos == 0 else C_WARNING
            self._progress_label.configure(
                text=f"Finalizado — {exitosos} ok, {fallidos} fallido(s)",
                text_color=color,
            )
            self._btn_descargar.configure(
                state="normal",
                text="Descargar Listas de Precios",
                fg_color=C_ACCENT,
            )

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS DE UI
    # ══════════════════════════════════════════════════════════════════════════

    def _log_append(self, texto: str, tag: str = ""):
        """Agrega texto al log con color opcional."""
        self._log_box.configure(state="normal")
        if tag:
            self._log_box.insert("end", texto, tag)
        else:
            self._log_box.insert("end", texto)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _limpiar_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._progress.set(0)
        self._progress_label.configure(text="Log limpiado.", text_color=C_TEXT_DIM)

    def _elegir_directorio(self):
        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta de destino",
            initialdir=self._dir_var.get() or os.path.expanduser("~"),
        )
        if carpeta:
            self._dir_var.set(carpeta)

    def _toggle_all(self, estado: bool):
        for var in self._check_vars.values():
            var.set(estado)



    def _render_provider_checkboxes(self):
        """Limpia y vuelve a generar la lista de checkboxes de proveedores en la GUI."""
        for widget in self._scroll_prov.winfo_children():
            widget.destroy()

        proveedores = cargar_proveedores()
        nuevas_vars = {}

        for nombre_display, ClaseProveedor in proveedores.items():
            estado_previo = self._check_vars.get(nombre_display, ctk.BooleanVar(value=True)).get()
            var = ctk.BooleanVar(value=estado_previo)
            nuevas_vars[nombre_display] = var

            row_frame = ctk.CTkFrame(self._scroll_prov, fg_color="transparent")
            row_frame.pack(fill="x", padx=4, pady=3)
            row_frame.grid_columnconfigure(0, weight=1)

            cb = ctk.CTkCheckBox(
                row_frame,
                text=nombre_display,
                variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=C_TEXT,
                fg_color=C_ACCENT,
                hover_color=C_ACCENT2,
                checkmark_color="#ffffff",
                border_color=C_BORDER,
                corner_radius=6,
            )
            cb.grid(row=0, column=0, sticky="w", padx=(6, 0))

            nombre_clave = getattr(ClaseProveedor, "nombre_clave", "")
            btn_del = ctk.CTkButton(
                row_frame,
                text="🗑",
                width=24,
                height=24,
                fg_color="transparent",
                hover_color="#fee2e2",
                text_color="#ef4444",
                font=ctk.CTkFont(size=12),
                corner_radius=4,
                command=lambda disp=nombre_display, k=nombre_clave: self._eliminar_proveedor(disp, k),
            )
            btn_del.grid(row=0, column=1, sticky="e", padx=(4, 6))

        self._check_vars = nuevas_vars

    def _abrir_asistente_proveedor(self):
        """Abre la ventana modal del asistente para configurar un nuevo proveedor."""
        VentanaAgregarProveedor(
            master=self,
            base_dir=_BASE_DIR,
            config_path=_CONFIG_PATH,
            on_success_callback=self._on_proveedor_agregado,
        )

    def _on_proveedor_agregado(self, nombre_display: str, nombre_clave: str):
        """Callback invocado cuando el asistente agrega exitosamente un nuevo proveedor."""
        self._cfg = _leer_config()
        self._render_provider_checkboxes()
        self._log_append(f"✨ Proveedor '{nombre_display}' configurado y agregado al sistema.\n", tag="success")


    def _eliminar_proveedor(self, nombre_display: str, nombre_clave: str):
        """Confirma y elimina la configuración y el archivo de un proveedor."""
        confirm = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Estás seguro de que querés eliminar el proveedor '{nombre_display}'?",
            parent=self,
        )
        if not confirm:
            return

        # 1. Eliminar de config.json
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                if "proveedores" in cfg_data and nombre_clave in cfg_data["proveedores"]:
                    del cfg_data["proveedores"][nombre_clave]
                    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                        json.dump(cfg_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self._log_append(f"⚠ No se pudo eliminar la config de '{nombre_display}': {e}\n", tag="warning")

        # 2. Eliminar archivo Python de proveedores/
        if nombre_clave:
            archivo_py = PROVEEDORES_DIR / f"proveedor_{nombre_clave}.py"
            if archivo_py.exists():
                try:
                    archivo_py.unlink()
                except Exception as e:
                    self._log_append(f"⚠ No se pudo borrar el archivo {archivo_py.name}: {e}\n", tag="warning")

        # 3. Refrescar UI
        self._render_provider_checkboxes()
        self._log_append(f"🗑 Proveedor '{nombre_display}' eliminado.\n", tag="dim")

    def _importar_proveedor(self):
        """Abre un cuadro de diálogo para importar y registrar un nuevo módulo .py de proveedor."""
        archivo = filedialog.askopenfilename(
            title="Seleccionar módulo de proveedor (.py)",
            filetypes=[("Archivos Python", "*.py"), ("Todos los archivos", "*.*")]
        )
        if not archivo:
            return

        origen = Path(archivo)
        if not origen.exists():
            return

        destino = PROVEEDORES_DIR / origen.name

        try:
            import shutil
            shutil.copy2(origen, destino)

            proveedores = cargar_proveedores()
            self._render_provider_checkboxes()

            self._log_append(f"📦 Módulo de proveedor '{origen.name}' importado con éxito.\n", tag="success")
            self._log_append(f"   Total de proveedores disponibles: {len(proveedores)}\n", tag="accent")

        except Exception as e:
            self._log_append(f"❌ Error al importar el proveedor '{origen.name}': {e}\n", tag="error")



# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
