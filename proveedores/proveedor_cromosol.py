# proveedores/proveedor_cromosol.py
"""
Proveedor: CROMOSOL (www.slaweb.com.ar, mismo recorrido que BBA)
Archivo:   cromosol.csv
Recorrido: login -> Catálogo -> Descarga -> marcar empresa CROMOSOL -> descargar
"""
from proveedores.base import BaseProveedor
from proveedores._slaweb import SlawebMixin


class ProveedorCromosol(SlawebMixin, BaseProveedor):
    nombre_clave = "cromosol"
    nombre_display = "Cromosol"
    empresa = "Cromosol"
    extension = "csv"
    nombre_salida = "cromosol.csv"
