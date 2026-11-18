# proveedores/proveedor_positivo.py
"""
Proveedor: POSITIVO
Archivo:   positivo.dbf
Login:     solo contraseña (config: "solo_password": true)
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorPositivo(FlujoWebMixin, BaseProveedor):
    nombre_clave = "positivo"
    nombre_display = "Positivo"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.elpositivo.com.ar/clientes/"])

        destino = cfg.get("download_page")
        if destino and page.url.rstrip("/") != destino.rstrip("/"):
            self.ir_a(page, destino)

        tmp = self.bajar_archivo(
            page, ["dbf", "zip"],
            pistas=["Lista ITEMS", "ITEMS"],
            textos=["ITEMS"],
            menus_previos=["AREA DE CLIENTES"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "positivo.dbf"))