# proveedores/proveedor_expoyer.py
"""
Proveedor REAL — Expo Yer (expoyerweb.com.ar)
-----------------------------------------------
Descarga la lista de precios CSV desde el portal de Expo Yer.

Flujo:
  1. Login con usuario y contraseña via formulario web.
  2. Navegar a /catalogo/descargar.
  3. Hacer clic en el botón "Descargar CSV Precios".
  4. Esperar a que el servidor genere el archivo y aparezca el link de descarga.
  5. Descargar el archivo y guardarlo con nombre normalizado.

Requiere login — las credenciales se configuran en config.json.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from proveedores.base import BaseProveedor, ProveedorError


class ProveedorExpoyer(BaseProveedor):
    """Proveedor Expo Yer — descarga de lista de precios CSV."""

    nombre_clave = "expoyer"
    nombre_display = "Expo Yer"

    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        """Login -> catalogo/descargar -> clic CSV Precios -> guardado."""

        destino = Path(directorio_destino)
        destino.mkdir(parents=True, exist_ok=True)

        # Leer configuracion del proveedor desde config.json
        cfg = self.cfg_proveedor()
        login_url = cfg.get("login_url", "https://expoyerweb.com.ar/login")
        download_page = cfg.get("download_page", "https://expoyerweb.com.ar/catalogo/descargar")
        usuario = cfg.get("usuario", "")
        password = cfg.get("password", "")
        # Selector del boton de descarga CSV (id por defecto)
        selector_btn = cfg.get("selector_boton_csv", "button#csv-precios")
        extension = cfg.get("extension", "csv")

        if not usuario or not password:
            raise ProveedorError(
                "Faltan credenciales de Expo Yer en config.json. "
                "Completar 'usuario' y 'password' en proveedores.expoyer"
            )

        self.log("Iniciando navegador...")

        import requests
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })

        try:
            # == 1. Login ==
            self.log(f"Iniciando sesión en Expo Yer: {login_url}")
            session.get(login_url, timeout=15)
            r_post = session.post("https://expoyerweb.com.ar/j_spring_security_check", data={
                "j_username": usuario,
                "j_password": password,
                "device": "",
            }, allow_redirects=True)

            if "error" in r_post.url or "login" in r_post.url.split("/")[-1]:
                if "conexiones permitidas" in r_post.text or "máximo de conexiones" in r_post.text:
                    raise ProveedorError(
                        "Login fallido en Expo Yer: Se alcanzó el máximo de conexiones permitidas para el usuario. "
                        "Cierre la sesión abierta en su navegador web o aguarde unos minutos e intente de nuevo."
                    )
                raise ProveedorError("Login fallido en Expo Yer. Verificar usuario y contraseña.")

            self.log("Login exitoso en Expo Yer.")

            # == 2. Generar lista de precios ==
            marcas = ['CD', 'CH', 'CI', 'FI', 'FO', 'JE', 'PG', 'RN', 'TY', 'UN', 'VW']
            self.log(f"Solicitando archivo de precios CSV para marcas: {', '.join(marcas)}...")
            
            ajax_url = "https://expoyerweb.com.ar/catalogo/descargar/lista-precios"
            params = [('cod_marca[]', m) for m in marcas]

            res = session.get(ajax_url, params=params, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=90)
            
            if res.status_code != 200:
                raise ProveedorError(f"Error en servidor al generar archivo: HTTP {res.status_code}")

            data = res.json()
            filename = data.get("data")
            if not filename:
                mensaje = data.get("message", "Respuesta desconocida del servidor")
                raise ProveedorError(f"Error del servidor Expo Yer: {mensaje}")

            # == 3. Descargar archivo ==
            download_url = f"https://expoyerweb.com.ar/catalogo/descargar/{filename}"
            self.log(f"Descargando {filename} desde: {download_url}")

            file_res = session.get(download_url, stream=True, timeout=120)
            
            ext_sugerida = Path(filename).suffix.lstrip(".") or extension
            nombre_final = self.nombre_archivo(ext_sugerida)
            ruta_final = destino / nombre_final

            with open(ruta_final, "wb") as f:
                for chunk in file_res.iter_content(chunk_size=16384):
                    f.write(chunk)

            tamano_kb = ruta_final.stat().st_size / 1024
            self.log(f"Archivo guardado exitosamente: {ruta_final} ({tamano_kb:.1f} KB)")
            return self.descomprimir_si_es_zip(ruta_final)

        except ProveedorError:
            raise
        except Exception as e:
            raise ProveedorError(f"Error inesperado al descargar de Expo Yer: {e}") from e
        finally:
            try:
                session.get("https://expoyerweb.com.ar/logout", timeout=10)
                self.log("Logout realizado.")
            except Exception:
                pass

    def _hacer_logout(self, pagina) -> None:
        """Intenta hacer logout para liberar la sesion en Expo Yer."""
        try:
            pagina.goto("https://expoyerweb.com.ar/logout", timeout=10_000)
            self.log("Logout realizado (sesion liberada)")
        except Exception:
            self.log("Aviso: no se pudo hacer logout")
