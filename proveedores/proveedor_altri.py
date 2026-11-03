# proveedores/proveedor_altri.py
"""
Proveedor: ALTRI (www.altri.com.ar)
Archivo:   altri.txt
Recorrido: login -> Descargas -> ahí aparece el archivo
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorAltri(FlujoWebMixin, BaseProveedor):
    nombre_clave = "altri"
    nombre_display = "Altri"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.altri.com.ar/serviceLogin.cgi"])
        page = self.clic_texto(page, ["Descargas", "Descarga"])
        if cfg.get("download_page"):
            # URL directa de la búsqueda (más confiable que usar el buscador)
            self.ir_a(page, cfg["download_page"])
        tmp = self.bajar_archivo(
            page, ["txt", "zip"], pistas=["txt", "lista", "precio"],
            textos=["Descargar TXT", "TXT"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "altri.txt"))
