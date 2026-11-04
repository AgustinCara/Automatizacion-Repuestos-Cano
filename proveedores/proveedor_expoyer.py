# proveedores/proveedor_expoyer.py
"""
Proveedor: EXPO YER (expoyerweb.com.ar)
Archivo:   TXT, se guarda con el nombre con el que lo entrega el sitio
           (o el de "nombre_archivo" en config.json, si está)
Recorrido: login -> Catálogo / Descargar -> activar "MARCAR TODAS" -> "Descargar TXT"
           -> "Continuar" en la confirmación -> esperar a que el servidor genere el archivo
           -> al final cierra la sesión (Expo Yer limita las conexiones abiertas)
"""
import time

from proveedores.base import BaseProveedor, ProveedorError
from proveedores._web import FlujoWebMixin

LOGOUT_URL = "https://expoyerweb.com.ar/logout"


class ProveedorExpoyer(FlujoWebMixin, BaseProveedor):
    nombre_clave = "expoyer"
    nombre_display = "Expo Yer"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://expoyerweb.com.ar/login"])
        if self.texto_en_pagina(page, ["conexiones permitidas", "maximo de conexiones"]):
            raise ProveedorError(
                "Expo Yer: se alcanzó el máximo de conexiones del usuario. Cerrar la sesión "
                "abierta en el navegador o esperar unos minutos y volver a intentar."
            )

        self.ir_a(page, cfg.get("download_page", "https://expoyerweb.com.ar/catalogo/descargar"))
        self.marcar_todas(page)

        texto = cfg.get("texto_boton", "Descargar TXT")
        boton = self._boton_exacto(page, texto)
        if boton is None:
            raise ProveedorError(f"No se encontró el botón '{texto}'")

        def apretar_y_confirmar():
            self.log(f"Clic en '{texto}'")
            boton.click()
            # Ventana "Confirmación requerida ... ¿Desea continuar?" -> Continuar
            fin = time.time() + 15
            while time.time() < fin:
                continuar = self._encontrar(page, ["Continuar"], roles_solo=True)
                if continuar is not None:
                    continuar.click()
                    self.log("Confirmado. El servidor está generando el archivo (puede tardar varios minutos)...")
                    return
                page.wait_for_timeout(500)
            self.log("No apareció la confirmación; se espera la descarga igual.")

        # Hasta 10 minutos: el sitio avisa que "puede tardar varios minutos"
        tmp = self._descargar_con(page, apretar_y_confirmar,
                                  timeout=int(cfg.get("espera_max_ms", 600000)),
                                  extensiones=["txt", "zip"])
        nombre = cfg.get("nombre_archivo") or self.nombre_descargado(tmp)
        return self.guardar_final(tmp, nombre)

    def _boton_exacto(self, page, texto):
        """Botón con ese texto EXACTO (para no confundir 'Descargar TXT' con
        'Descargar TXT con Marca' o 'Descargar TXT Completo')."""
        for frame in page.frames:
            for rol in ("button", "link"):
                loc = frame.get_by_role(rol, name=texto, exact=True)
                for i in range(min(loc.count(), 5)):
                    if loc.nth(i).is_visible():
                        return loc.nth(i)
        return None

    def marcar_todas(self, page):
        """Activa el interruptor 'MARCAR TODAS' y verifica que quedó activado."""
        self.log("Activando 'MARCAR TODAS'...")
        estado = page.evaluate(
            """() => {
                const txt = e => (e.textContent || '').trim().toUpperCase();
                // elemento cuyo texto propio es 'MARCAR TODAS'
                const rotulo = Array.from(document.querySelectorAll('body *'))
                    .find(e => txt(e) === 'MARCAR TODAS' && e.children.length === 0);
                if (!rotulo) return 'sin_rotulo';
                // buscar el checkbox del interruptor en los contenedores cercanos
                let cont = rotulo.parentElement, cb = null;
                for (let n = 0; n < 4 && cont && !cb; n++, cont = cont.parentElement)
                    cb = cont.querySelector('input[type=checkbox]');
                if (!cb) {  // sin checkbox: hacer clic en el elemento siguiente (el switch)
                    const sig = rotulo.nextElementSibling || rotulo.parentElement.nextElementSibling;
                    if (!sig) return 'sin_switch';
                    sig.click(); return 'clic_switch';
                }
                if (cb.checked) return 'ya_marcado';
                const vis = cb.offsetWidth || cb.offsetHeight;
                const lbl = cb.id && document.querySelector('label[for="' + cb.id + '"]');
                (vis ? cb : (lbl || cb.parentElement.querySelector('.toggle, .slider, span') || cb)).click();
                if (!cb.checked) cb.click();  // por si el clic visual no lo cambió
                return cb.checked ? 'marcado' : 'no_cambio';
            }"""
        )
        page.wait_for_timeout(1500)
        if estado in ("marcado", "ya_marcado", "clic_switch"):
            self.log("'MARCAR TODAS' activado.")
        else:
            raise ProveedorError(f"No se pudo activar 'MARCAR TODAS' ({estado})")

    def al_terminar(self, page):
        try:
            page.goto(self.cfg_proveedor().get("logout_url", LOGOUT_URL), timeout=10000)
            self.log("Sesión cerrada en Expo Yer.")
        except Exception:
            self.log("Aviso: no se pudo cerrar la sesión de Expo Yer.")