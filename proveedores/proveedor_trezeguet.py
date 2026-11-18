# proveedores/proveedor_trezeguet.py
"""
Proveedor: TREZEGUET (Retenes)
Archivo:   trezeguet.xls / .xlsx / .csv (según lo que entregue el sitio)
Login:     'Iniciar sesión' abre un pop-up con Usuario / Contraseña -> 'Ingresar'
Descarga:  botón 'Lista exel general' (NO 'Lista exel motor' ni 'Catalogo PDF')
"""
from pathlib import Path

from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorTrezeguet(FlujoWebMixin, BaseProveedor):
    nombre_clave = "trezeguet"
    nombre_display = "Trezeguet"

    def cerrar_ventana(self, page):
        """Cierra el cartel."""
        nueva = self.clic_texto(page, ["Cerrar"], obligatorio=False, timeout=10000)
        page = nueva or page
        page.wait_for_timeout(800)
        # Por si quedó abierto: Escape como respaldo
        if page.locator("text=/PASO \\d+ DE \\d+/i >> visible=true").count():
            self.log("El tutorial sigue abierto, cerrando con Escape...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)
        return page

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["http://45.71.155.11:8800/web1/webform1.aspx"])

        self.log("Cerrando ventana...")
        page = self.cerrar_ventana(page)

        tmp = self.bajar_archivo(
            page, ["xls", "xlsx", "csv"],
            pistas=["general"],
            textos=["Lista exel general", "Lista exel general"],
            excluir=["motor", "PDF"],
        )

        return self.guardar_final(tmp, cfg.get("nombre_archivo", "trezeguet.csv"))