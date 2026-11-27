"""Shared Qt lifecycle for GUI tests.

One QApplication for the whole session, created before any test fixture. At the end of the run
every remaining widget is deleted while Qt is still running (see ``_delete_all_widgets``), so
the process exits normally with pytest's status.
"""

from __future__ import annotations

import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# Module-level reference: the QApplication must outlive every widget, so it is never released
# before interpreter exit.
_APP: QApplication | None = None


@pytest.fixture(scope="session", autouse=True)
def _qt_session():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    app = _APP
    yield app
    _delete_all_widgets(app)


def _delete_all_widgets(app: QApplication) -> None:
    """Root cause of the old exit crash (found 2026-11-27): top-level widgets that tests closed
    but never deleted stayed alive in Python and were destroyed during interpreter shutdown, in
    random order; one destroyed after the QApplication aborts the process (Windows 0xC0000409 /
    "Fatal Python error: Aborted"). Delete every remaining widget while Qt is still running."""
    app.closeAllWindows()
    for _ in range(3):
        for w in app.topLevelWidgets():
            w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        gc.collect()
