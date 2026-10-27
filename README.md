# Repuestos CANO — Descargador de Listas de Precios

Aplicación de escritorio desarrollada en Python para automatizar la descarga de listas de precios desde los portales web de proveedores de repuestos de automóviles.

---

## 📋 Tabla de contenidos

1. [Requisitos del sistema](#requisitos-del-sistema)
2. [Instalación](#instalación)
3. [Ejecución](#ejecución)
4. [Estructura del proyecto](#estructura-del-proyecto)
5. [Cómo agregar un nuevo proveedor](#cómo-agregar-un-nuevo-proveedor)
6. [Configuración (`config.json`)](#configuración-configjson)
7. [Resolución de problemas](#resolución-de-problemas)

---

## Requisitos del sistema

| Requisito | Versión mínima |
|-----------|----------------|
| Python    | 3.10+          |
| pip       | Incluido con Python |
| Windows   | 10 / 11        |

---

## Instalación

### 1. Clonar o descomprimir el proyecto

Copiá la carpeta `repuestos_downloader/` a tu equipo, por ejemplo en:

```
C:\Repuestos\repuestos_downloader\
```

### 2. Crear un entorno virtual (recomendado)

```powershell
cd C:\Repuestos\repuestos_downloader
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar dependencias Python

```powershell
pip install -r requirements.txt
```

### 4. Instalar los navegadores de Playwright

Este paso descarga Chromium (~150 MB). Solo se realiza **una vez**.

```powershell
playwright install chromium
```

---

## Ejecución

Con el entorno virtual activado:

```powershell
python app.py
```

La aplicación abrirá una ventana gráfica donde podrás:

- ✅ Seleccionar uno o varios proveedores.
- 📁 Elegir la carpeta de destino para los archivos descargados.
- ⬇ Iniciar la descarga con un solo clic.
- 📋 Ver el progreso en tiempo real en la consola de estado.

---

## Estructura del proyecto

```
repuestos_downloader/
├── proveedores/
│   ├── __init__.py          ← Registro de proveedores disponibles
│   ├── base.py              ← Clase abstracta BaseProveedor
│   ├── proveedor_distem.py  ← Proveedor Distem S.R.L.
│   └── proveedor_expoyer.py ← Proveedor Expo Yer
├── config.json              ← URLs, credenciales y configuración global
├── app.py                   ← Interfaz gráfica principal (CustomTkinter)
├── requirements.txt         ← Dependencias Python
└── README.md                ← Este archivo
```

---

## Cómo agregar un nuevo proveedor

### Paso 1 — Crear el módulo del proveedor

Creá el archivo `proveedores/proveedor_nombre.py` siguiendo esta plantilla:

```python
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from proveedores.base import BaseProveedor, ProveedorError

class ProveedorNombre(BaseProveedor):
    """Proveedor: Nombre Comercial del proveedor."""

    nombre_clave = "nombre"   # identificador corto, sin espacios

    def descargar(self, directorio_destino: str | Path, headless: bool = True) -> str:
        destino = Path(directorio_destino)
        destino.mkdir(parents=True, exist_ok=True)

        cfg = self.cfg_proveedor()
        login_url    = cfg.get("login_url",    "https://portal.proveedor.com/login")
        download_url = cfg.get("download_url", "https://portal.proveedor.com/precios")
        usuario      = cfg.get("usuario",      "")
        password     = cfg.get("password",     "")

        self.log("Iniciando navegador...")

        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=headless)
            contexto  = navegador.new_context(accept_downloads=True)
            pagina    = contexto.new_page()
            try:
                # 1. Login
                self.log(f"Abriendo: {login_url}")
                pagina.goto(login_url, timeout=30_000)
                pagina.fill("#email", usuario)           # ← Ajustar selector
                pagina.fill("#password", password)       # ← Ajustar selector
                pagina.click("button[type='submit']")    # ← Ajustar selector
                pagina.wait_for_url("**/dashboard**", timeout=10_000)
                self.log("Login exitoso ✓")

                # 2. Navegar y descargar
                self.log(f"Navegando a: {download_url}")
                pagina.goto(download_url, timeout=30_000)

                with pagina.expect_download(timeout=60_000) as info:
                    pagina.click("a.btn-descargar")      # ← Ajustar selector

                descarga = info.value
                nombre   = self.nombre_archivo("xlsx")  # ← Ajustar extensión
                ruta     = destino / nombre
                descarga.save_as(ruta)
                self.log(f"Archivo guardado: {ruta} ✓")
                return str(ruta)

            except PWTimeout as e:
                raise ProveedorError(f"Timeout: {e}") from e
            except Exception as e:
                raise ProveedorError(f"Error: {e}") from e
            finally:
                navegador.close()
```

### Paso 2 — Agregar la configuración en `config.json`

```json
"proveedores": {
  "nombre": {
    "login_url":    "https://portal.proveedor.com/login",
    "download_url": "https://portal.proveedor.com/precios/lista",
    "usuario":      "mi_usuario",
    "password":     "mi_contraseña"
  }
}
```

### Paso 3 — Registrar el proveedor en `proveedores/__init__.py`

```python
from proveedores.proveedor_nombre import ProveedorNombre

PROVEEDORES = {
    ...,
    "Nombre Comercial del Proveedor": ProveedorNombre,
}
```

Reiniciá la aplicación y el nuevo proveedor aparecerá automáticamente en la lista.

---

## Configuración (`config.json`)

| Campo | Descripción |
|-------|-------------|
| `configuracion_global.headless` | `true` = navegador oculto (producción), `false` = visible (pruebas) |
| `configuracion_global.directorio_descarga_default` | Carpeta donde se guardan los archivos |
| `proveedores.<clave>.login_url` | URL del formulario de login |
| `proveedores.<clave>.download_url` | URL de la página de descarga |
| `proveedores.<clave>.usuario` | Usuario / email de la cuenta |
| `proveedores.<clave>.password` | Contraseña (**no compartir ni subir a Git**) |

---

## Resolución de problemas

### ❌ `ModuleNotFoundError: No module named 'customtkinter'`
```powershell
pip install -r requirements.txt
```

### ❌ `playwright._impl._errors.Error: Executable doesn't exist`
```powershell
playwright install chromium
```

### ❌ El proveedor falla con timeout
- Probá con `headless = false` (desactivar "Modo silencioso") para ver qué pasa en el navegador.
- Verificá que los selectores CSS en el módulo del proveedor coincidan con el HTML actual del portal.
- Aumentá los timeouts en `config.json` (`timeout_navegador_ms`, `timeout_descarga_ms`).

### ❌ No se dispara la descarga con `expect_download()`
- Algunos portales generan el archivo dinámicamente. En ese caso, esperá a que el botón inicie la descarga del lado del servidor usando:
  ```python
  pagina.wait_for_timeout(2000)   # pausa de 2 segundos como máximo
  ```

---

## Seguridad

> ⚠️ **Importante:** El archivo `config.json` puede contener contraseñas en texto plano.  
> No lo compartas, no lo incluyas en repositorios Git, y restringí sus permisos de lectura.
> Para entornos de producción, reemplazá las contraseñas por variables de entorno usando `python-dotenv`.

---

*Desarrollado para Repuestos CANO — 2026*
