# proveedores/proveedor_rejovot.py
"""
Proveedor: REJOVOT
Archivo:   rejovot.csv
Login:     'Ingresar' (arriba a la derecha) abre el panel de inicio de sesión
Descarga:  /lista-de-precios -> botón 'Descargar' -> 'CSV'
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorRejovot(FlujoWebMixin, BaseProveedor):
    nombre_clave = "rejovot"
    nombre_display = "Rejovot"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.rejovot.com.ar/productos?vista=cuadricula"])

        destino = cfg.get("download_page") or "https://www.rejovot.com.ar/lista-de-precios"
        self.ir_a(page, destino)
        self.log(f"Página actual: {page.url}")

        self.log("Abriendo menú Descargar...")
        page = self.clic_texto(page, ["Descargar"], timeout=15000) or page
        page.wait_for_timeout(1000)

        tmp = self.bajar_archivo(
            page, ["csv"],
            pistas=["CSV", "lista", "precios"],
            textos=["CSV"],
            menus_previos=["Descargar"],  # si el menú se cerró, lo vuelve a abrir
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "rejovot.csv"))