"""PyInstaller entry point of the windowed app (EngineeringStudio.exe).

Arguments are passed to the GUI (``.m`` files to open). A windowed program has no console,
so a start-up failure is written to ``%LOCALAPPDATA%\\EngineeringStudio\\startup_error.txt``
and shown in a message box instead of disappearing silently.
"""

import multiprocessing
import os
import sys
import traceback


def _report(text: str) -> None:
    folder = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                          "EngineeringStudio")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "startup_error.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None, "Engineering Studio could not start.\n\n" + text[-1500:],
            "Engineering Studio", 0x10)
    except Exception:
        pass


def _run() -> int:
    multiprocessing.freeze_support()
    try:
        from engstudio.gui.app_main import main

        return main(sys.argv)
    except SystemExit:
        raise
    except BaseException:
        _report(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(_run())
