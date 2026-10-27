"""
Script de PRUEBA para automatizar login + descarga de archivo de un portal.

Usa un sitio de demostración público (the-internet.herokuapp.com) que simula
un login y una página de descargas, solo para validar que el flujo funciona
de punta a punta. Cuando tengas el portal real de un proveedor, hay que
cambiar:
    - Las URLs (LOGIN_URL, DOWNLOAD_URL)
    - Los selectores (los "#usuario", "#password", etc. dependen de cada
      página, hay que inspeccionar el HTML del portal real)
    - El usuario/contraseña reales

Requisitos (correr una sola vez en tu máquina):
    pip install playwright
    playwright install chromium

Cómo correr este script:
    python script_descarga_proveedor_demo.py
"""

from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime
import sys

# ------------------------------------------------------------------
# CONFIGURACIÓN — esto es lo que cambia por cada proveedor
# ------------------------------------------------------------------
PROVEEDOR_NOMBRE = "demo"
LOGIN_URL = "https://the-internet.herokuapp.com/login"
DOWNLOAD_URL = "https://the-internet.herokuapp.com/download"

USUARIO = "tomsmith"
PASSWORD = "SuperSecretPassword!"

# Carpeta donde se van a guardar los archivos descargados
CARPETA_DESTINO = Path("descargas_raw") / PROVEEDOR_NOMBRE
CARPETA_DESTINO.mkdir(parents=True, exist_ok=True)


def descargar_lista_precios():
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    with sync_playwright() as p:
        # headless=False para ver el navegador mientras probás.
        # Cuando ya confirmes que funciona, cambiar a headless=True.
        navegador = p.chromium.launch(headless=False)
        contexto = navegador.new_context(accept_downloads=True)
        pagina = contexto.new_page()

        try:
            # 1. Ir a la página de login
            print(f"[{PROVEEDOR_NOMBRE}] Abriendo página de login...")
            pagina.goto(LOGIN_URL)

            # 2. Completar usuario y contraseña
            # OJO: estos selectores son específicos del sitio demo.
            # En un portal real hay que inspeccionar el HTML (botón derecho
            # -> Inspeccionar) para encontrar el id/name correcto de cada campo.
            pagina.fill("#username", USUARIO)
            pagina.fill("#password", PASSWORD)
            pagina.click("button[type='submit']")

            # 3. Confirmar que el login funcionó
            pagina.wait_for_selector(".flash.success", timeout=5000)
            print(f"[{PROVEEDOR_NOMBRE}] Login exitoso.")

            # 4. Ir a la sección de descargas
            pagina.goto(DOWNLOAD_URL)

            # 5. Descargar el primer archivo de la lista
            # expect_download espera a que se dispare la descarga al hacer clic
            with pagina.expect_download() as descarga_info:
                pagina.click("a[href$='.txt']")  # primer link .txt de la página

            descarga = descarga_info.value

            # 6. Guardar el archivo con nombre + fecha, en la carpeta destino
            nombre_archivo = f"{PROVEEDOR_NOMBRE}_{fecha_hoy}.txt"
            ruta_final = CARPETA_DESTINO / nombre_archivo
            descarga.save_as(ruta_final)

            print(f"[{PROVEEDOR_NOMBRE}] Archivo guardado en: {ruta_final}")
            return True

        except Exception as error:
            print(f"[{PROVEEDOR_NOMBRE}] ERROR: {error}", file=sys.stderr)
            return False

        finally:
            navegador.close()


if __name__ == "__main__":
    exito = descargar_lista_precios()
    if exito:
        print("Proceso terminado correctamente.")
    else:
        print("Proceso terminado con errores.")
        sys.exit(1)
