# proveedores/proveedor_4wd.py
"""
Proveedor: 4WD
Archivo:   4wd.xls
Recorrido: login -> buscar un artículo (AN1067) -> link del Excel debajo de los resultados
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class Proveedor4wd(FlujoWebMixin, BaseProveedor):
    nombre_clave = "4wd"
    nombre_display = "4WD"

    def pasos(self, page, cfg):
        # En la planilla figura "www.4wdcom.ar": se prueban las dos variantes
        page = self.login(page, cfg, ["https://www.4wd.com.ar", "https://www.4wdcom.ar"])
        if cfg.get("download_page"):
            # URL directa de la búsqueda (más confiable que usar el buscador)
            self.ir_a(page, cfg["download_page"])
        else:
            page = self.buscar_articulo(page, cfg, cfg.get("articulo_busqueda", "AN1067"))
        tmp = self.bajar_archivo(
            page, ["xls", "xlsx", "zip"], pistas=["xls", "excel", "lista precios"],
            textos=["Lista precios completa", "Lista de precios completa",
                    "Descargar Excel", "Exportar a Excel", "Excel", "XLS"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "4wd.xls"))
