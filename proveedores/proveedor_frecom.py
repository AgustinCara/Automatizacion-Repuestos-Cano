# proveedores/proveedor_frecom.py
"""
Proveedor: FRECOM
Archivo:   frecom.xls
Recorrido: login (entrar.htm) -> link "Descargar Catálogo" (arriba a la derecha)
           -> ventana "Catálogos" -> sección "Catálogo Excel" -> botón "Descargar"
"""
import re
import tempfile
from pathlib import Path

from proveedores.base import BaseProveedor, ProveedorError
from proveedores._web import FlujoWebMixin

LOGIN_URL = "https://www.frecom.com.ar/entrar.htm"


class ProveedorFrecom(FlujoWebMixin, BaseProveedor):
    nombre_clave = "frecom"
    nombre_display = "Frecom"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, [cfg.get("login_url", LOGIN_URL)])

        if cfg.get("download_page"):
            self.ir_a(page, cfg["download_page"])

        tmp = self._descargar_catalogo_excel(page)
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "frecom.xls"))

    def _descargar_catalogo_excel(self, page):
        page.wait_for_load_state("networkidle")

        # 1) Link "Descargar Catálogo" del menú superior
        #    (no confundir con "CATALOGO" de la barra azul)
        link = (
            page.locator("a:visible, button:visible")
            .filter(has_text=re.compile(r"Descargar\s+Cat[aá]logo", re.I))
            .first
        )
        try:
            link.wait_for(state="visible", timeout=30_000)
        except Exception as e:
            raise ProveedorError(f"Frecom: no apareció 'Descargar Catálogo' en {page.url}") from e
        link.click()

        # 2) Se abre la ventana "Catálogos". El primer bloque es "Catálogo Excel";
        #    tomamos el botón "Descargar" que viene después de ese título
        #    (los otros dos son de PDF).
        boton = page.locator(
            "xpath=//*[normalize-space()='Catálogo Excel' or normalize-space()='Catalogo Excel']"
            "/following::*[self::button or self::a][contains(normalize-space(.), 'Descargar')][1]"
        ).first
        try:
            boton.wait_for(state="visible", timeout=15_000)
        except Exception as e:
            raise ProveedorError("Frecom: no apareció el botón Descargar de 'Catálogo Excel'") from e

        # 3) Sin categorías marcadas -> catálogo completo. Puede tardar porque lo genera en el momento.
        with page.expect_download(timeout=300_000) as info:
            boton.click()
        descarga = info.value

        destino = Path(tempfile.mkdtemp()) / (descarga.suggested_filename or "frecom.xls")
        descarga.save_as(destino)
        return destino
