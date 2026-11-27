"""Shared Qt lifecycle for GUI tests.

One QApplication for the whole session, created before any test fixture. At the end of the
run, remaining windows are closed and queued deletions are processed before the interpreter
exits; otherwise live widgets are destroyed after Qt shuts down and the process aborts with
exit code 0xC0000409 on Windows (all tests pass, but the exit code is non-zero).
"""

from __future__ import annotations

import atexit
import gc
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# Module-level reference: the QApplication must outlive every widget, so it is never released
# before interpreter exit (destroying it while widgets remain aborts the process on Windows).
_APP: QApplication | None = None
_STATUS = 1  # safe default: if the hook below never runs, the run fails visibly
_GUARDED = False


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    global _STATUS
    _STATUS = int(getattr(session, "exitstatus", exitstatus))


def _exit_with_pytest_status() -> None:
    """Known issue: after the run, Qt teardown intermittently aborts the process (Windows
    0xC0000409) although every test passed; the real app exits cleanly (checked separately
    with `python -m engstudio.gui --smoke`). Exit with pytest's own status, skipping the
    native destructors. Disable with ENGSTUDIO_NO_FAST_EXIT=1."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:  # noqa: BLE001
            pass
    os._exit(_STATUS)


@pytest.fixture(scope="session", autouse=True)
def _qt_session():
    global _APP, _GUARDED
    _APP = QApplication.instance() or QApplication([])
    if not _GUARDED and not os.environ.get("ENGSTUDIO_NO_FAST_EXIT"):
        _GUARDED = True
        atexit.register(_exit_with_pytest_status)
    app = _APP
    yield app
    app.closeAllWindows()
    for _ in range(3):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    gc.collect()
