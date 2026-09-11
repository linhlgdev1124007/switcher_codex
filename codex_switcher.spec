# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


python_root = Path(r'D:\AppsTaive_Main\python')
tk_binaries = [
    (str(python_root / 'DLLs' / '_tkinter.pyd'), '.'),
    (str(python_root / 'DLLs' / 'tcl86t.dll'), '.'),
    (str(python_root / 'DLLs' / 'tk86t.dll'), '.'),
]
tk_datas = [
    (str(python_root / 'tcl'), 'tcl'),
    (str(python_root / 'Lib' / 'tkinter'), 'tkinter'),
]


a = Analysis(
    ['codex_switcher.py'],
    pathex=[],
    binaries=tk_binaries,
    datas=tk_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_tkinter_bundle.py'],
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
    name='codex_switcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo-b6.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='codex_switcher',
)
