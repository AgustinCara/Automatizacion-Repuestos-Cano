"""
build_exe.py — Script de construccion del ejecutable para Repuestos CANO
========================================================================
Genera un .exe listo para distribuir al cliente.
Incluye automaticamente los binarios de Playwright (Chromium).

Uso:
    python build_exe.py

El ejecutable queda en:  dist/RepuestosCano/RepuestosCano.exe
"""

import os
import subprocess
import sys
from pathlib import Path


# Configuracion
APP_NAME      = "RepuestosCano"
ENTRY_SCRIPT  = "app.py"
ICON_FILE     = None   # Cambiar a "icono.ico" si se tiene uno


def run(cmd, **kwargs):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"ERROR: El comando fallo con codigo {result.returncode}")
        sys.exit(result.returncode)
    return result


def find_playwright_browsers():
    """Localiza el directorio de browsers de Playwright."""
    try:
        import playwright
        playwright_path = Path(playwright.__file__).parent
        possible_paths = [
            playwright_path / "driver" / "package" / ".local-browsers",
            playwright_path / "driver" / ".local-browsers",
            Path.home() / "AppData" / "Local" / "ms-playwright",
        ]
        for p in possible_paths:
            if p.exists():
                print(f"  OK Browsers de Playwright encontrados en: {p}")
                return p
        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if env_path and Path(env_path).exists():
            return Path(env_path)
    except ImportError:
        pass
    return None


def build():
    base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)

    print("=" * 65)
    print("  Repuestos CANO -- Generador de ejecutable (.exe)")
    print("=" * 65)

    print("\n[1/5] Verificando dependencias...")
    run([sys.executable, "-m", "pip", "install", "--quiet", "-r", "requirements.txt"])
    run([sys.executable, "-m", "pip", "install", "--quiet", "pyinstaller"])

    print("\n[2/5] Instalando browsers de Playwright (Chromium)...")
    run([sys.executable, "-m", "playwright", "install", "chromium"])

    print("\n[3/5] Localizando archivos de Playwright...")
    browsers_path = find_playwright_browsers()
    if not browsers_path:
        print("  AVISO: No se encontraron browsers. Instalando en carpeta local...")
        local_browsers = base_dir / "playwright_browsers"
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(local_browsers)
        run([sys.executable, "-m", "playwright", "install", "chromium"], env=env)
        browsers_path = local_browsers

    print("\n[4/5] Generando configuracion de PyInstaller...")

    add_data_entries = [
        f"proveedores{os.pathsep}proveedores",
        f"config.json{os.pathsep}.",
        f"{browsers_path}{os.pathsep}playwright_browsers",
    ]

    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--name={APP_NAME}",
        "--windowed",
        "--onedir",
    ]

    for entry in add_data_entries:
        pyinstaller_args += ["--add-data", entry]

    hidden_imports = [
        "customtkinter",
        "playwright",
        "playwright.sync_api",
        "nest_asyncio",
        "dotenv",
        "proveedores",
        "proveedores.proveedor_distem",
        "proveedores.proveedor_expoyer",
        "proveedores.base",
        "dialog_proveedor",
    ]
    for imp in hidden_imports:
        pyinstaller_args += ["--hidden-import", imp]

    if ICON_FILE and Path(ICON_FILE).exists():
        pyinstaller_args += [f"--icon={ICON_FILE}"]

    pyinstaller_args.append(ENTRY_SCRIPT)

    print("\n[5/5] Compilando ejecutable (puede tardar varios minutos)...")
    run(pyinstaller_args)

    dist_dir = base_dir / "dist" / APP_NAME
    launcher = dist_dir / f"Abrir {APP_NAME}.bat"
    launcher.write_text(
        "@echo off\n"
        "set PLAYWRIGHT_BROWSERS_PATH=%~dp0playwright_browsers\n"
        f'start "" "%~dp0{APP_NAME}.exe"\n',
        encoding="utf-8"
    )

    print("\n" + "=" * 65)
    print(f"  LISTO! Ejecutable generado en:")
    print(f"     {dist_dir}")
    print(f"\n  Entregale al cliente TODA la carpeta: dist/{APP_NAME}/")
    print(f"\n  El cliente hace doble clic en: Abrir {APP_NAME}.bat")
    print("=" * 65)


if __name__ == "__main__":
    build()
