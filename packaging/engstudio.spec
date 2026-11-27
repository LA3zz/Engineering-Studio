# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Engineering Studio (Phase 10). Build with packaging\build.ps1.
# Produces dist\EngineeringStudio\ with two programs sharing one runtime:
#   EngineeringStudio.exe   windowed GUI (desktop shortcut, Open with .m files)
#   engstudio-console.exe   console: --version, --selftest, --selftest-gui
# SPECPATH is provided by PyInstaller (directory containing this file).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "src" / "engstudio" / "gui" / "engstudio.ico")

def _keep(name):
    """Leave out PyQtGraph's examples, OpenGL and Jupyter parts (not used, large)."""
    return not name.startswith(("pyqtgraph.examples", "pyqtgraph.opengl", "pyqtgraph.jupyter"))


# engstudio and the libraries that import modules by name at run time.
# openpyxl: pandas imports it by name for Excel files (readmatrix/readtable/writematrix).
hiddenimports = (collect_submodules("engstudio") + collect_submodules("control")
                 + collect_submodules("pyqtgraph", filter=_keep) + collect_submodules("openpyxl"))

datas = [
    (str(ROOT / "src" / "engstudio" / "app" / "docs_pages"), "engstudio/app/docs_pages"),
    (ICON, "engstudio/gui"),
    (str(ROOT / "examples"), "examples"),
] + collect_data_files("control") + collect_data_files(
    "pyqtgraph", excludes=["examples/**", "opengl/**", "jupyter/**"])

excludes = [
    "tkinter", "pytest", "_pytest", "IPython", "jupyter",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech", "PySide6.QtHttpServer", "PySide6.QtDesigner",
    "matplotlib.backends.backend_tkagg", "matplotlib.backends._backend_tk",
    "pyqtgraph.examples", "pyqtgraph.opengl", "pyqtgraph.jupyter",
]


def analysis(script):
    return Analysis(
        [str(ROOT / "packaging" / script)],
        pathex=[str(ROOT / "src")],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        runtime_hooks=[],
        excludes=excludes,
        noarchive=False,
    )


gui = analysis("entry_gui.py")
cli = analysis("entry.py")

gui_exe = EXE(
    PYZ(gui.pure), gui.scripts, [],
    exclude_binaries=True, name="EngineeringStudio", icon=ICON,
    debug=False, strip=False, upx=False, console=False,
)
cli_exe = EXE(
    PYZ(cli.pure), cli.scripts, [],
    exclude_binaries=True, name="engstudio-console", icon=ICON,
    debug=False, strip=False, upx=False, console=True,
)
coll = COLLECT(
    gui_exe, gui.binaries, gui.datas,
    cli_exe, cli.binaries, cli.datas,
    strip=False, upx=False, name="EngineeringStudio",
)
