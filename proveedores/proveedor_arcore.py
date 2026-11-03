# proveedores/proveedor_arcore.py
"""
Proveedor: ARCORE (www.arcore.com)
Archivo:   arcore.txt
Recorrido: login -> en la página se ve el TXT -> descargar
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorArcore(FlujoWebMixin, BaseProveedor):
    nombre_clave = "arcore"
    nombre_display = "Arcore"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.arcore.com", "https://www.arcore.com.ar"])
        tmp = self.bajar_archivo(
            page, ["txt", "zip"], pistas=["txt", "arcore", "lista", "precio"],
            textos=["Descargar TXT", "TXT"],
            menus_previos=["Descargas", "Lista de precios", "Precios"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "arcore.txt"))
