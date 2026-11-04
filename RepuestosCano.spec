# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('proveedores', 'proveedores'), ('config.json', '.'), ('C:/Users/agusc/AppData/Local/ms-playwright', 'playwright_browsers')],
    hiddenimports=['customtkinter', 'playwright', 'playwright.sync_api', 'nest_asyncio', 'dotenv', 'proveedores', 'proveedores.proveedor_distem', 'proveedores.proveedor_expoyer', 'proveedores.base', 'proveedores._web', 'proveedores._slaweb', 'openpyxl', 'xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RepuestosCano',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RepuestosCano',
)
