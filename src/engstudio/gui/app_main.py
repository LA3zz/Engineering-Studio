"""GUI entry point: ``python -m engstudio.gui [--smoke] [--stub] [file.m ...]``.

``--smoke`` opens the window, quits after ~0.8 s, and does not read or write user settings.
``--stub`` uses the stub kernel instead of the interpreter (GUI development).
File arguments (``.m`` scripts) open in the editor. If Engineering Studio is already running,
the files are handed to that window and this process exits at once (single instance; the
desktop shortcut and "Open with" both rely on it). A splash screen shows while the numerical
libraries load.
"""

from __future__ import annotations

import sys
from pathlib import Path

from engstudio.gui.settings import UiSettings, default_settings_path

ICON_PATH = Path(__file__).with_name("engstudio.ico")


def _files(args: list[str]) -> list[str]:
    return [str(Path(a).resolve()) for a in args[1:]
            if not a.startswith("--") and Path(a).is_file()]


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen

    from engstudio.gui.single_instance import SingleInstance

    args = list(sys.argv if argv is None else argv)
    smoke = "--smoke" in args
    use_stub = "--stub" in args
    files = _files(args)
    args = [a for a in args if a not in ("--smoke", "--stub")]
    app = QApplication.instance() or QApplication(args)
    instance = None
    waiting: list[str] = list(files)  # files to open once the window exists
    opener: list = []  # set to the real opener when the window is ready
    if not smoke:
        instance = SingleInstance()
        if instance.try_forward(files):
            return 0  # the running window opens the files
        # Listen at once: a second launch during the slow start-up queues its files here.
        instance.listen(lambda paths: opener[0](paths) if opener else waiting.extend(paths))
    icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QIcon()
    app.setWindowIcon(icon)
    splash = None
    if not smoke and ICON_PATH.exists():
        splash = QSplashScreen(QPixmap(str(ICON_PATH)).scaled(
            256, 256, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        splash.showMessage("Loading Engineering Studio...",
                           Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        splash.show()
        app.processEvents()

    from engstudio.app.kernel.inprocess import InProcessKernelClient  # slow: SciPy, SymPy
    from engstudio.app.kernel.stub import StubKernelClient
    from engstudio.gui.main_window import APP_NAME, MainWindow

    app.setApplicationName(APP_NAME)
    client = StubKernelClient() if use_stub else InProcessKernelClient()
    window = MainWindow(
        UiSettings(None if smoke else default_settings_path()), client
    )
    window.show()
    if splash is not None:
        splash.finish(window)

    def open_files(paths: list[str]) -> None:
        for p in paths:
            window.tabs.open_path(p)
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
        window.raise_()
        window.activateWindow()

    opener.append(open_files)
    open_files(waiting)
    if window.folder_panel is not None and not smoke:  # working folder = Current Folder
        window.sync_working_folder(str(window.folder_panel.folder))
    if smoke:
        QTimer.singleShot(800, app.quit)
    code = app.exec()
    if instance is not None:
        instance.close()
    return code
