# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Engineering Studio (Phase 2 spike). Build with packaging\build.ps1.
# SPECPATH is provided by PyInstaller (directory containing this file).
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent

# Every engstudio module is listed explicitly so toolboxes and lazily imported modules
# (e.g. engstudio.selftest, imported inside functions) are always bundled.
hiddenimports = collect_submodules("engstudio")

excludes = [
    "tkinter", "pytest", "_pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "src" / "engstudio" / "app" / "docs_pages"),
            "engstudio/app/docs_pages")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EngineeringStudio",
    debug=False,
    strip=False,
    upx=False,
    console=True,   # spike: keep a console so --selftest output is visible
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="EngineeringStudio",
)
