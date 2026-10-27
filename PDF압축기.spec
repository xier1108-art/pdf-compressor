# -*- mode: python ; coding: utf-8 -*-
# One-dir build (instant startup). Run via build.bat.
import glob
import os

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Ghostscript: bundle only what the engine needs (bin/lib/Resource/iccprofiles),
# not docs/examples. Newest installed version wins.
gs_dirs = sorted(glob.glob(r"C:\Program Files\gs\gs*"))
if gs_dirs:
    for sub in ("bin", "lib", "Resource", "iccprofiles"):
        src = os.path.join(gs_dirs[-1], sub)
        if os.path.isdir(src):
            datas.append((src, os.path.join("gs", sub)))
else:
    print("[warning] Ghostscript not found - building with the PyMuPDF fallback engine only")

for pkg in ("pymupdf", "pikepdf"):
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# PyQt6 is handled by PyInstaller's own hook (only QtCore/QtGui/QtWidgets are used).
# collect_all('PyQt6') used to drag in all of Qt (~3.6 GB) and big packages that
# happen to be installed (pandas/pyarrow/pytz...) - none of which the app imports.
excludes = [
    "tkinter", "numpy", "pandas", "pyarrow", "pytz", "scipy", "matplotlib", "IPython",
    "notebook", "jupyter", "sklearn", "torch", "tensorflow", "cv2", "numba", "sympy", "lxml",
    "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtQuickWidgets", "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets", "PyQt6.QtMultimedia", "PyQt6.QtNetwork", "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets", "PyQt6.QtDesigner", "PyQt6.QtSql", "PyQt6.QtTest", "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets", "PyQt6.Qt3DCore", "PyQt6.QtCharts", "PyQt6.QtBluetooth",
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDF압축기',
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
    icon=['assets\\icon.ico'],
    contents_directory='_internal',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PDF압축기',
)
