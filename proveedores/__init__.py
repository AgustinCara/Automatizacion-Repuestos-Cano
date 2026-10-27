# proveedores/__init__.py
"""
Registro centralizado y dinámico de todos los proveedores disponibles.

Soporta carga dinámica (Plug & Play):
Cualquier archivo Python (*.py) guardado en esta carpeta que herede de `BaseProveedor`
será descubierto y registrado automáticamente en la interfaz del sistema.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Type

from proveedores.base import BaseProveedor

_logger = logging.getLogger("proveedores")

# Ubicación física de la carpeta de proveedores
PROVEEDORES_DIR = Path(__file__).resolve().parent


def cargar_proveedores() -> dict[str, Type[BaseProveedor]]:
    """
    Escanea la carpeta proveedores/ y registra dinámicamente todas las clases
    que heredan de BaseProveedor.

    Returns:
        dict: { nombre_display: ClaseProveedor }
    """
    proveedores_encontrados: dict[str, Type[BaseProveedor]] = {}

    if not PROVEEDORES_DIR.exists():
        return proveedores_encontrados

    for filepath in sorted(PROVEEDORES_DIR.glob("*.py")):
        # Ignorar base.py, __init__.py y archivos temporales/ocultos
        if filepath.name in ("base.py", "__init__.py") or filepath.name.startswith("_"):
            continue

        module_name = f"proveedores.{filepath.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Buscar clases que hereden de BaseProveedor
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseProveedor) and obj is not BaseProveedor:
                    display_name = obj.get_nombre_display()
                    proveedores_encontrados[display_name] = obj
                    _logger.info(f"Proveedor registrado dinámicamente: '{display_name}' ({filepath.name})")

        except Exception as e:
            _logger.error(f"Error al cargar módulo de proveedor '{filepath.name}': {e}")

    return proveedores_encontrados


# Cargar los proveedores inicialmente al importar el paquete
PROVEEDORES: dict[str, Type[BaseProveedor]] = cargar_proveedores()
