# proveedores/proveedor_distem.py
"""
Proveedor REAL — Distem S.R.L. (distemsrl.com.ar)
---------------------------------------------------
Descarga la lista de precios en formato DBF desde la página pública
de descargas del sitio de Distem.

URL directa del archivo: https://www.distemsrl.com.ar/downloads/precios/LISTA.DBF
Página de referencia:    https://www.distemsrl.com.ar/descargas.php

Flujo:
  1. (Opcional) Parsear la página para descubrir links dinámicamente.
  2. Descargar el archivo via HTTP directo (requests).
  3. Guardar con nombre normalizado en la carpeta destino.

No requiere login — los archivos son de acceso público.
"""

from __future__ import annotations

import requests
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from proveedores.base import BaseProveedor, ProveedorError


class ProveedorDistem(BaseProveedor):
    """Proveedor Distem S.R.L. — descarga de lista de precios DBF."""

    nombre_clave = "distem"
    nombre_display = "Distem S.R.L."

    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        """Descarga LISTA.DBF desde Distem usando HTTP directo."""

        destino = Path(directorio_destino)
        destino.mkdir(parents=True, exist_ok=True)

        # Leer configuración del proveedor desde config.json
        cfg = self.cfg_proveedor()
        pagina_descargas = cfg.get(
            "pagina_descargas",
            "https://www.distemsrl.com.ar/descargas.php",
        )
        # URL directa al archivo (descubierta del HTML de la página)
        url_archivo = cfg.get(
            "url_archivo",
            "https://www.distemsrl.com.ar/downloads/precios/LISTA.DBF",
        )
        extension = cfg.get("extension", "dbf")

        self.log("Iniciando descarga directa via HTTP...")
        self.log(f"URL del archivo: {url_archivo}")

        try:
            # ── 1. Intentar descubrir la URL desde la página (scraping) ────
            #    Si falla, usar la URL fija configurada.
            url_final = self._descubrir_url(pagina_descargas, extension) or url_archivo
            self.log(f"URL final de descarga: {url_final}")

            # ── 2. Descargar via HTTP directo ──────────────────────────────
            self.log("Descargando archivo...")
            response = requests.get(
                url_final,
                timeout=60,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36",
                    "Referer": pagina_descargas,
                },
                stream=True,
            )
            response.raise_for_status()

            # ── 3. Guardar con nombre normalizado ──────────────────────────
            nombre = self.nombre_archivo(extension)
            ruta_final = destino / nombre

            total_bytes = 0
            with open(ruta_final, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)

            tamano_kb = total_bytes / 1024
            self.log(f"Archivo guardado: {ruta_final} ({tamano_kb:.1f} KB) ✓")
            return self.descomprimir_si_es_zip(ruta_final)

        except requests.RequestException as e:
            raise ProveedorError(f"Error HTTP al descargar: {e}") from e

        except Exception as e:
            raise ProveedorError(f"Error inesperado: {e}") from e

    def _descubrir_url(self, pagina_url: str, extension: str) -> str | None:
        """
        Intenta parsear la página de descargas para encontrar el link
        dinámicamente. Retorna la URL absoluta o None si falla.
        """
        try:
            self.log(f"Consultando página de descargas: {pagina_url}")
            resp = requests.get(
                pagina_url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36",
                },
            )
            resp.raise_for_status()

            # Buscar el href que termine en .DBF o .dbf (case insensitive)
            import re
            patron = rf'href=["\']([^"\']*\.{re.escape(extension)})["\']'
            match = re.search(patron, resp.text, re.IGNORECASE)
            if match:
                href = match.group(1)
                url_absoluta = urljoin(pagina_url, href)
                self.log(f"Link encontrado en página: {href}")
                return url_absoluta
            else:
                self.log("No se encontró el link en la página, usando URL fija.")
                return None

        except Exception as e:
            self.log(f"Aviso: no se pudo parsear la página ({e}), usando URL fija.")
            return None
