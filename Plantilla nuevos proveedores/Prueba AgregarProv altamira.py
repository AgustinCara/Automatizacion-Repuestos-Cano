# proveedores/proveedor_altamira.py
"""
Proveedor: ALTAMIRA
Archivo:   altamira.xlsx (la planilla no indica nombre; se usa este)
Recorrido: login -> página de precios -> descargar el XLS

Para instalarlo en la PC del cliente: botón "Agregar proveedor" de la app.
Al importarlo, 'config_inicial' se copia a config.json (sin pisar datos existentes).
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorAltamira(FlujoWebMixin, BaseProveedor):
    nombre_clave = "altamira"
    nombre_display = "Altamira"

    # Se copia a config.json al importar el proveedor
    config_inicial = {
        "_descripcion": "Altamira — Lista de precios XLS (requiere login)",
        "login_url": "https://www.altamiragroup.com.ar",
        "selector_usuario": "input[name='usuario']",
        "download_page": "https://webapp.altamiragroup.com.ar/precios/",
        "usuario": "ramon",
        "password": "56",
        "extension": "xlsx",
        "nombre_archivo": "altamira.xlsx",
    }

    def pasos(self, page, cfg):
        # Login en el sitio principal
        page = self.login(page, cfg, ["https://www.altamiragroup.com.ar"])
        if cfg.get("download_page"):
            # Ir directo a la página donde está el archivo XLS
            self.ir_a(page, cfg["download_page"])
        tmp = self.bajar_archivo(
            page, ["xlsx", "xls", "zip"], pistas=["xls", "excel"],
            # Sin "Lista de precios": así se llama el menú, no el archivo
            textos=["Descargar XLS", "Descargar Excel", "XLS", "Excel", "Descargar"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "altamira.xlsx"))
