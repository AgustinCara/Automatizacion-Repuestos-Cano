# proveedores/proveedor_distrigo.py
"""
Proveedor: DISTRIGO
Archivo:   distrigo.xlsx
Recorrido: login -> catálogo -> botón "Exportar" -> opción "Exportar Precios XLS"
"""
import re
import tempfile
from pathlib import Path

from proveedores.base import BaseProveedor, ProveedorError
from proveedores._web import FlujoWebMixin

LOGIN_URL = "https://pedidos.distrigom.com/#/login/cliente"
CATALOGO_URL = "https://pedidos.distrigom.com/#/catalogo"


class ProveedorDistrigo(FlujoWebMixin, BaseProveedor):
    nombre_clave = "distrigo"
    nombre_display = "Distrigo"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, [LOGIN_URL])

        # Después del login cae en el catálogo; si no, lo forzamos
        if "#/catalogo" not in page.url:
            self.ir_a(page, cfg.get("download_page", CATALOGO_URL))

        tmp = self._exportar_xls(page)
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "distrigo.xlsx"))

    def _exportar_xls(self, page):
        # Sitio Angular: el botón aparece recién cuando termina de cargar el catálogo
        page.wait_for_load_state("networkidle")

        # Botón desplegable que dice solo "Exportar" (con flechita). Filtramos por texto
        # exacto para no agarrar las opciones del menú ("Exportar precio venta", etc.)
        boton = (
            page.locator("button:visible, a:visible, [role='button']:visible")
            .filter(has_text=re.compile(r"^\s*Exportar\s*$", re.I))
            .first
        )
        try:
            boton.wait_for(state="visible", timeout=30_000)
        except Exception as e:
            raise ProveedorError(f"Distrigo: no apareció el botón Exportar en {page.url}") from e
        boton.click()

        # Se despliegan dos opciones: elegimos "Exportar Precios XLS"
        opcion = page.get_by_text(re.compile(r"Exportar\s+Precios\s+XLS", re.I)).first
        try:
            opcion.wait_for(state="visible", timeout=10_000)
        except Exception as e:
            raise ProveedorError("Distrigo: no apareció la opción 'Exportar Precios XLS'") from e

        with page.expect_download(timeout=120_000) as info:
            opcion.click()
        descarga = info.value

        destino = Path(tempfile.mkdtemp()) / (descarga.suggested_filename or "distrigo.xlsx")
        descarga.save_as(destino)
        return destino
