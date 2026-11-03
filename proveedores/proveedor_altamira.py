# proveedores/proveedor_altamira.py
"""
Proveedor: ALTAMIRA
Archivo:   altamira.xlsx (la planilla no indica nombre; se usa este)
Recorrido: login -> en la página aparece el archivo XLS -> descargar
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorAltamira(FlujoWebMixin, BaseProveedor):
    nombre_clave = "altamira"
    nombre_display = "Altamira"

    def pasos(self, page, cfg):
        # En la planilla figura "www.alatmiragroup.com.ar": se prueban las dos variantes
        page = self.login(page, cfg, ["https://www.altamiragroup.com.ar"])
        if cfg.get("download_page"):
            # URL directa de la búsqueda (más confiable que usar el buscador)
            self.ir_a(page, cfg["download_page"])
        tmp = self.bajar_archivo(
            page, ["xlsx", "xls", "zip"], pistas=["xls", "excel"],
            textos=["Descargar XLS", "Descargar Excel", "XLS", "Excel", "Descargar"],
            excluir=["Lista de precios"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "altamira.xlsx"))
