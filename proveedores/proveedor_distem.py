# proveedores/proveedor_distem.py
"""
Proveedor: DISTEM S.R.L. (www.distemsrl.com.ar)
Archivo:   se guarda con el MISMO nombre con el que lo entrega el sitio (ej. LISTA.DBF)
Recorrido: página pública de descargas -> link al .DBF -> descarga directa
No requiere login ni navegador (descarga directa por HTTP).
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorDistem(FlujoWebMixin, BaseProveedor):
    nombre_clave = "distem"
    nombre_display = "Distem S.R.L."
    usa_navegador = False

    def pasos(self, page, cfg):
        pagina = cfg.get("pagina_descargas", "https://www.distemsrl.com.ar/descargas.php")
        extension = cfg.get("extension", "dbf")
        # Buscar el link en la página; si no aparece, usar la URL fija
        url = self.buscar_link_http(pagina, [extension]) or cfg.get(
            "url_archivo", "https://www.distemsrl.com.ar/downloads/precios/LISTA.DBF"
        )
        tmp, nombre = self.bajar_http(url, referer=pagina)
        # "nombre_archivo" en config.json lo fuerza; si no, queda el nombre original
        return self.guardar_final(tmp, cfg.get("nombre_archivo") or nombre)
