# proveedores/base.py
"""
Clase base abstracta que deben implementar todos los módulos de proveedor.

Contrato que debe cumplir cada proveedor:
  - Heredar de BaseProveedor.
  - Implementar el método  descargar(directorio_destino, headless) -> str
    que retorna la ruta absoluta del archivo descargado.
  - En caso de error lanzar ProveedorError (o cualquier Exception) con un
    mensaje descriptivo.  La GUI capturará la excepción y la mostrará en el log.

Variables de entorno / config disponibles vía self.cfg (dict leído de config.json).
"""

from __future__ import annotations

import json
import logging
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime

# Ruta al config.json ubicado un nivel arriba de /proveedores
_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def _cargar_config() -> dict:
    """Carga config.json una sola vez y lo retorna como dict."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class ProveedorError(Exception):
    """Excepción específica para errores de proveedor."""
    pass


class BaseProveedor(ABC):
    """
    Interfaz común para todos los módulos de descarga de proveedores.

    Atributos de clase que cada subclase DEBE definir:
        nombre_clave (str): Identificador corto sin espacios (ej: 'demo1').
                            Se usa para construir el nombre del archivo descargado.
    """

    nombre_clave: str = "proveedor"
    nombre_display: str = ""

    @classmethod
    def get_nombre_display(cls) -> str:
        """Retorna el nombre para mostrar en la interfaz de usuario."""
        if cls.nombre_display:
            return cls.nombre_display
        return cls.nombre_clave.replace("_", " ").title()

    def __init__(self, log_callback=None):
        """
        Args:
            log_callback: Función opcional que acepta un str para enviar mensajes
                          de log a la GUI en tiempo real. Si es None se usa logging.
        """
        self.cfg: dict = _cargar_config()
        self._log_cb = log_callback
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Método principal — implementar en cada subclase
    # ------------------------------------------------------------------

    @abstractmethod
    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        """
        Ejecuta el flujo completo: login → navegación → descarga → guardado.

        Args:
            directorio_destino: Carpeta donde se guardará el archivo descargado.
            headless: Si True, el navegador corre en segundo plano (producción).
                      Si False, el navegador es visible (útil para depuración).

        Returns:
            Ruta absoluta (str) del archivo guardado exitosamente.

        Raises:
            ProveedorError: Si cualquier paso del flujo falla.
        """
        ...

    # ------------------------------------------------------------------
    # Helpers disponibles para todas las subclases
    # ------------------------------------------------------------------

    def log(self, mensaje: str) -> None:
        """Envía un mensaje al log de la GUI o a la consola si no hay GUI."""
        linea = f"[{self.nombre_clave.upper()}] {mensaje}"
        if self._log_cb:
            self._log_cb(linea)
        self.logger.info(linea)

    def nombre_archivo(self, extension: str) -> str:
        """
        Genera un nombre normalizado para el archivo descargado.

        Formato: {nombre_clave}_{YYYYMMDD_HHMM}.{extension}
        Ejemplo: demo1_20241115_1430.xlsx
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        ext = extension.lstrip(".")
        return f"{self.nombre_clave}_{ts}.{ext}"

    def cfg_proveedor(self) -> dict:
        """
        Retorna el bloque de configuración específico de este proveedor
        desde config.json (clave == self.nombre_clave).
        """
        return self.cfg.get("proveedores", {}).get(self.nombre_clave, {})

    def descomprimir_si_es_zip(self, ruta_archivo: str | Path, borrar_zip: bool = True) -> str:
        """
        Si 'ruta_archivo' es un archivo ZIP, lo descomprime automáticamente en la misma carpeta.
        Renombra el archivo extraído relevante usando 'nombre_archivo()' para conservar
        la convención de nombres del proveedor.

        Args:
            ruta_archivo: Ruta al archivo descargado.
            borrar_zip: Si True (por defecto), borra el archivo .zip original luego de descomprimir.

        Returns:
            Ruta (str) del archivo final descomprimido (o la misma ruta si no era un ZIP).
        """
        ruta_p = Path(ruta_archivo)
        if not ruta_p.exists():
            return str(ruta_archivo)

        es_zip = ruta_p.suffix.lower() == ".zip" or zipfile.is_zipfile(ruta_p)
        if not es_zip:
            return str(ruta_p)

        self.log(f"Detectado archivo ZIP: '{ruta_p.name}'. Descomprimiendo automáticamente...")
        destino = ruta_p.parent

        try:
            with zipfile.ZipFile(ruta_p, "r") as zip_ref:
                nombres = [n for n in zip_ref.namelist() if not n.endswith("/")]
                if not nombres:
                    self.log("Aviso: El archivo ZIP está vacío.")
                    return str(ruta_p)

                zip_ref.extractall(destino)
                self.log(f"Contenido extraído del ZIP: {', '.join(nombres)}")

            if borrar_zip:
                try:
                    ruta_p.unlink()
                    self.log(f"Archivo ZIP original eliminado: '{ruta_p.name}'")
                except Exception as e:
                    self.log(f"Aviso: No se pudo eliminar el ZIP original ({e})")

            # Buscar el archivo extraído más relevante
            exts_interes = {".csv", ".xlsx", ".xls", ".dbf", ".txt"}
            archivo_candidato = None

            for nombre in nombres:
                sub_p = destino / nombre
                if sub_p.is_file():
                    if sub_p.suffix.lower() in exts_interes:
                        archivo_candidato = sub_p
                        break
                    elif archivo_candidato is None:
                        archivo_candidato = sub_p

            if archivo_candidato and archivo_candidato.exists():
                ext = archivo_candidato.suffix.lstrip(".")
                nuevo_nombre = self.nombre_archivo(ext)
                ruta_definitiva = destino / nuevo_nombre

                if archivo_candidato != ruta_definitiva:
                    archivo_candidato.replace(ruta_definitiva)

                tamano_kb = ruta_definitiva.stat().st_size / 1024
                self.log(f"Archivo descomprimido y guardado como: '{ruta_definitiva.name}' ({tamano_kb:.1f} KB) ✓")
                return str(ruta_definitiva)

            return str(ruta_p)

        except Exception as e:
            self.log(f"Error al descomprimir el ZIP: {e}")
            raise ProveedorError(f"No se pudo descomprimir el archivo ZIP ({e})") from e

