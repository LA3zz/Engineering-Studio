"""Top-level window showing one figure (``FigureView`` + status line for render warnings)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QWidget

from engstudio.app.figure_export import (
    EXPORT_FORMATS,
    MATPLOTLIB_LOCK,
    load_matplotlib,
    save_figure,
)
from engstudio.core.errors import EngStudioError
from engstudio.gui.plots import FigureView
from engstudio.plotting.model import FigureSpec

if TYPE_CHECKING:
    from engstudio.gui.mpl_view import MplFigureView

__all__ = ["FigureWindow"]


class FigureWindow(QMainWindow):
    closed = Signal(int)  # the figure number, emitted when the window closes

    def __init__(self, number: int, theme: str = "light", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.number = number
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.view: FigureView | MplFigureView = FigureView(theme, self)  # noqa: F821
        self.setCentralWidget(self.view)
        self.setWindowTitle(f"Figure {number}")
        self.resize(720, 480)
        self.spec: FigureSpec | None = None
        self._create_menu()

    def set_figure(self, spec: FigureSpec) -> None:
        self.spec = spec
        want_mpl = spec.needs_matplotlib
        if want_mpl != (not isinstance(self.view, FigureView)):  # swap the renderer
            theme = self.view.theme
            old = self.view
            if want_mpl:
                load_matplotlib()  # on demand, and never at the same time as the kernel thread
                with MATPLOTLIB_LOCK:
                    from engstudio.gui.mpl_view import MplFigureView
                self.view = MplFigureView(theme, self)
            else:
                self.view = FigureView(theme, self)
            self.setCentralWidget(self.view)
            old.deleteLater()
        self.view.set_figure(spec)
        label = spec.name or spec.title
        self.setWindowTitle(f"Figure {self.number}: {label}" if label
                            else f"Figure {self.number}")
        self._show_warnings()

    def set_theme(self, name: str) -> None:
        self.view.set_theme(name)
        self._show_warnings()

    def _create_menu(self) -> None:
        self.save_action = QAction("&Save As...", self)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.setStatusTip("Save the figure as PNG, SVG or PDF")
        self.save_action.triggered.connect(lambda _checked=False: self.save_as())
        close_action = QAction("&Close", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(lambda _checked=False: self.close())
        menu = self.menuBar().addMenu("&File")
        menu.addActions([self.save_action, close_action])

    def save_as(self) -> bool:
        """Ask for a file name and save the figure there. False if cancelled or failed."""
        if self.spec is None:
            return False
        filters = ";;".join(f"{label} (*.{ext})" for ext, label in EXPORT_FORMATS.items())
        name, _ = QFileDialog.getSaveFileName(
            self, "Save figure", str(Path.cwd() / f"figure{self.number}.png"), filters)
        return bool(name) and self.save_to(name)

    def save_to(self, path: Path | str) -> bool:
        """Save the figure to ``path`` (``.png`` is added if there is no extension)."""
        if self.spec is None:
            return False
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".png")
        try:
            saved = save_figure(self.spec, target)
        except EngStudioError as exc:
            QMessageBox.warning(self, "Save figure failed", str(exc))
            return False
        self.statusBar().showMessage(f"Saved {saved}")
        return True

    def _show_warnings(self) -> None:
        self.statusBar().showMessage("; ".join(self.view.warnings))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        self.closed.emit(self.number)
        super().closeEvent(event)
