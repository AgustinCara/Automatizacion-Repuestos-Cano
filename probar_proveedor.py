# probar_proveedor.py
"""
Prueba UN proveedor desde la consola, viendo el navegador.

    python probar_proveedor.py pana
    python probar_proveedor.py cedicor C:\\Descargas\\prueba

Si falla, mirar la carpeta _diagnostico dentro de la carpeta de descarga.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proveedores import PROVEEDORES  # noqa: E402

if len(sys.argv) < 2:
    print("Uso: python probar_proveedor.py <clave> [carpeta]")
    print("Claves:", ", ".join(sorted(c.nombre_clave for c in PROVEEDORES.values())))
    sys.exit(1)

clave = sys.argv[1].lower()
carpeta = sys.argv[2] if len(sys.argv) > 2 else "descargas_prueba"
clase = next((c for c in PROVEEDORES.values() if c.nombre_clave == clave), None)
if not clase:
    sys.exit(f"No existe el proveedor '{clave}'")
ruta = clase(log_callback=print).descargar(carpeta, headless=False)
print("\nLISTO:", ruta)
