# proveedores/proveedor_pana.py
"""
Proveedor: PANA (www.pana.com.ar)
Archivo:   panliscr.dbf
Recorrido: Pana Nitro -> login -> flecha en el nombre -> Descargas -> "DBF con rubros"
Nota: Pana solo deja ingresar desde la PC del cliente.
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin, TEXTOS_ABRIR_LOGIN


class ProveedorPana(FlujoWebMixin, BaseProveedor):
    nombre_clave = "pana"
    nombre_display = "Pana"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://nitro.pana.com.ar/login?from=/"])
        if cfg.get("download_page"):
            # URL directa de la búsqueda (más confiable que usar el buscador)
            self.ir_a(page, cfg["download_page"])
        else:
            # Si después del ingreso todavía se ofrece "Pana Nitro", entrar
            page = self.clic_texto(page, ["Pana Nitro"], obligatorio=False, timeout=4000) or page
            page = self.clic_texto(page, ["Descargas", "Descarga"])
        tmp = self.bajar_archivo(
            page, ["dbf", "zip"], pistas=["rubro", "panliscr"],
            textos=["DBF con rubros", "con rubros"], excluir=["sin rubro"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "panliscr.dbf"))

# 1ER VERSION

    # def pasos(self, page, cfg):
    #     cfg = {"textos_abrir_login": ["Pana Nitro", "Nitro"] + TEXTOS_ABRIR_LOGIN, **cfg}
    #     page = self.login(page, cfg, ["https://www.pana.com.ar"])
    #     # Si después del ingreso todavía se ofrece "Pana Nitro", entrar
    #     page = self.clic_texto(page, ["Pana Nitro"], obligatorio=False, timeout=4000) or page
    #     page = self.clic_texto(page, ["Descargas", "Descarga"])
    #     tmp = self.bajar_archivo(
    #         page, ["dbf", "zip"], pistas=["rubro", "panliscr"],
    #         textos=["DBF con rubros", "con rubros"], excluir=["sin rubro"],
    #     )
    #     return self.guardar_final(tmp, cfg.get("nombre_archivo", "panliscr.dbf"))




