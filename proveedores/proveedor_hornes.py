# proveedores/proveedor_hornes.py
"""
Proveedor: HORNES (VTM - vtm-lista.pages.dev)
Archivo:   hornes.txt
Login:     no requiere
Descarga:  (cerrar tutorial "Saltar") -> botón "Exportar" -> "Archivo TXT"
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorHornes(FlujoWebMixin, BaseProveedor):
    nombre_clave = "hornes"
    nombre_display = "Hornes"

    def cerrar_tutorial(self, page):
        """Cierra el cartel 'Paso 1 de 4' que aparece al entrar."""
        nueva = self.clic_texto(page, ["Saltar"], obligatorio=False, timeout=10000)
        page = nueva or page
        page.wait_for_timeout(800)
        # Por si quedó abierto: Escape como respaldo
        if page.locator("text=/PASO \\d+ DE \\d+/i >> visible=true").count():
            self.log("El tutorial sigue abierto, cerrando con Escape...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)
        return page

    def pasos(self, page, cfg):
        self.ir_a(page, cfg.get("download_page") or "https://vtm-lista.pages.dev/")

        self.log("Cerrando tutorial de bienvenida...")
        page = self.cerrar_tutorial(page)

        self.log("Abriendo menú Exportar...")
        page = self.clic_texto(page, ["Exportar"], timeout=20000) or page
        page.wait_for_timeout(1000)

        tmp = self.bajar_archivo(
            page, ["txt"],
            pistas=["TXT", "LISPRO2"],
            textos=["Archivo TXT", "Descargar catálogo completo LISPRO2"],
            menus_previos=["Exportar"],
        )
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "hornes.txt"))