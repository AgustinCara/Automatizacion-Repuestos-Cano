# proveedores/proveedor_rodpar.py
"""
Proveedor: RODPAR (Rodamientos Particulares)
Archivo:   rodpar.csv
Login:     el formulario se abre con el ícono de llave (selector_abrir_login).
           Después de ingresar se cierra el pop-up (Escape / clic afuera).
Descarga:  link directo del CSV (figura en la página Configuración -> "Resumido")
"""
import base64
import tempfile
from pathlib import Path

from proveedores.base import BaseProveedor, ProveedorError
from proveedores._web import FlujoWebMixin

URL_CSV = "https://www.rodamientosparticulares.com/Tapice/Minorista/TapicePreciosResumido.csv"


class ProveedorRodpar(FlujoWebMixin, BaseProveedor):
    nombre_clave = "rodpar"
    nombre_display = "Rodpar"

    def cerrar_popup_login(self, page):
        """Cierra el pop-up de ingreso: Escape y, si sigue, clic afuera."""
        self.log("Cerrando el pop-up de ingreso...")
        page.keyboard.press("Escape")
        page.wait_for_timeout(1000)
        for x, y in [(10, 10), (10, 400), (600, 880)]:
            _, pwd = self._buscar_password(page, None)
            if pwd is None:
                break
            page.mouse.click(x, y)  # clic fuera del pop-up
            page.wait_for_timeout(1000)
        _, pwd = self._buscar_password(page, None)
        if pwd is None:
            self.log("Pop-up cerrado.")
        else:
            self.log("Aviso: el pop-up de ingreso sigue abierto.")

    def bajar_csv_directo(self, page, url, usuario="aa", clave="aa"):
        """Baja el CSV con la sesión del navegador; si pide autenticación, usa la de TapiCe."""
        req = page.context.request
        self.log(f"Descargando {url}...")
        r = req.get(url, timeout=90000)
        if r.status in (401, 403):
            self.log("El servidor pidió autenticación, reintentando con la clave de TapiCe...")
            token = base64.b64encode(f"{usuario}:{clave}".encode()).decode()
            r = req.get(url, headers={"Authorization": f"Basic {token}"}, timeout=90000)
        if not r.ok:
            raise ProveedorError(f"No se pudo bajar el CSV (HTTP {r.status})")

        datos = r.body()
        inicio = datos[:300].lstrip().lower()
        if inicio.startswith(b"<!doctype") or inicio.startswith(b"<html"):
            raise ProveedorError("El servidor devolvió una página web en lugar del CSV")

        tmp = Path(tempfile.mkdtemp()) / "rodpar.csv"
        tmp.write_bytes(datos)
        self.log(f"CSV descargado ({len(datos):,} bytes).")
        return tmp

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.rodamientosparticulares.com/"])
        self.cerrar_popup_login(page)

        url = cfg.get("download_url") or URL_CSV
        tmp = self.bajar_csv_directo(
            page, url,
            usuario=cfg.get("usuario_tapice", "aa"),
            clave=cfg.get("clave_tapice", "aa"),
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "rodpar.csv"))