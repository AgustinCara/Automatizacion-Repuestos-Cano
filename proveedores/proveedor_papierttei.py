# proveedores/proveedor_papierttei.py
"""
Proveedor: PAPIERTTEI
Archivo:   papierttei.xls
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorPapierttei(FlujoWebMixin, BaseProveedor):
    nombre_clave = "papierttei"
    nombre_display = "Papierttei"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://magnum.papierttei.com/login/"])
        if cfg.get("download_page"):
            # URL directa de la búsqueda (más confiable que usar el buscador)
            self.ir_a(page, cfg["download_page"])
        else:
            page = self.buscar_articulo(page, cfg, cfg.get("Lista Completas"))
        tmp = self.bajar_archivo(
            page, ["xls", "xlsx", "zip"], pistas=["xls", "excel", "lista precios"],
            textos=[ "XLS"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "papierttei.xls"))