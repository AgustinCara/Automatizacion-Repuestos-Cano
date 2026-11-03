# proveedores/proveedor_kavigo.py
"""
Proveedor: KAVIGO (www.kavigo.com)
Archivo:   lispre.dbf
Recorrido: login -> Lista de precios -> descargar archivo "lispre"
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorKavigo(FlujoWebMixin, BaseProveedor):
    nombre_clave = "kavigo"
    nombre_display = "Kavigo"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.kavigo.com", "https://www.kavigo.com.ar"])
        page = self.clic_texto(page, ["Lista de precios", "Listas de precios", "Lista precios", "Precios"])
        tmp = self.bajar_archivo(
            page, ["dbf", "zip"], pistas=["lispre"],
            textos=["lispre", "Descargar archivo", "DBF"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "lispre.dbf"))
