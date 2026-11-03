# proveedores/_slaweb.py
"""
Recorrido común de www.slaweb.com.ar (lo usan BBA y Cromosol con el mismo usuario):
login -> Catálogo -> Descarga -> marcar la empresa -> descargar.
"""
from __future__ import annotations

from proveedores._web import FlujoWebMixin


class SlawebMixin(FlujoWebMixin):
    empresa = ""            # texto de la empresa a marcar (ej. "BBA")
    extension = ""          # extensión esperada (xlsx / csv)
    nombre_salida = ""      # nombre final del archivo

    def pasos(self, page, cfg: dict) -> str:
        empresa = cfg.get("empresa", self.empresa)
        ext = cfg.get("extension", self.extension)
        page = self.login(page, cfg, ["https://www.slaweb.com.ar"])
        page = self.clic_texto(page, ["Catálogo", "Catalogo"])
        page = self.clic_texto(page, ["Descargas", "Descarga"])
        self.elegir_opcion(page, empresa)
        tmp = self.bajar_archivo(
            page, [ext, "zip"], pistas=[empresa, ext],
            textos=["Descargar", "Generar", "Exportar", "Bajar"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", self.nombre_salida))
