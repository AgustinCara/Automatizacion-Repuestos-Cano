# proveedores/proveedor_bba.py
"""
Proveedor: BBA (www.slaweb.com.ar)
Archivo:   bba.xlsx
Recorrido: login -> Catálogo -> Descarga -> marcar empresa BBA -> descargar
"""
from proveedores.base import BaseProveedor
from proveedores._slaweb import SlawebMixin


class ProveedorBba(SlawebMixin, BaseProveedor):
    nombre_clave = "bba"
    nombre_display = "BBA"
    empresa = "BBA"
    extension = "xlsx"
    nombre_salida = "bba.xlsx"
