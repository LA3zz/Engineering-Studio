"""Top-level window showing one figure (``FigureView`` + status line for render warnings).

Menus: File (Save As, Close), Edit (Axes Properties, Figure Title, Grid, Legend, Undo All
Changes) and View (Reset Zoom, Equal Axis Scaling). Double-clicking a title or an axis opens
the properties dialog at that field. Edits change the window's copy of the figure (saved by
Save As); when the script draws the same figure again, the script's version replaces them.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from engstudio.app.figure_export import (
    EXPORT_FORMATS,
    MATPLOTLIB_LOCK,
    load_matplotlib,
    save_figure,
)
from engstudio.core.errors import EngStudioError
from engstudio.gui.figure_edit import AxesPropertiesDialog, edit_figure_title, set_all_axes
from engstudio.gui.plot_params import series_color
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
        self.view.edit_requested.connect(self.edit_part)
        self.setCentralWidget(self.view)
        self.setWindowTitle(f"Figure {number}")
        self.resize(720, 480)
        self.spec: FigureSpec | None = None  # what the window shows (with the user's edits)
        self.script_spec: FigureSpec | None = None  # as the script drew it
        self.dialog: AxesPropertiesDialog | None = None
        self._create_menu()

    # -- figure ----------------------------------------------------------------
    def set_figure(self, spec: FigureSpec) -> None:
        """A new drawing from the script (replaces any edits made in the window)."""
        self.script_spec = spec
        self._show(spec)

    def _show(self, spec: FigureSpec) -> None:
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
            self.view.edit_requested.connect(self.edit_part)
            self.setCentralWidget(self.view)
            old.deleteLater()
        self.view.set_figure(spec)
        label = spec.name or spec.title
        self.setWindowTitle(f"Figure {self.number}: {label}" if label
                            else f"Figure {self.number}")
        self._show_warnings()
        self.undo_action.setEnabled(spec is not self.script_spec)

    def set_theme(self, name: str) -> None:
        self.view.set_theme(name)
        self._show_warnings()

    # -- menus -----------------------------------------------------------------
    def _action(self, text: str, slot, shortcut: str | None = None, tip: str = "") -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setStatusTip(tip)
        a.triggered.connect(lambda _checked=False: slot())
        return a

    def _create_menu(self) -> None:
        self.save_action = self._action("&Save As...", self.save_as, "Ctrl+S",
                                        "Save the figure as PNG, SVG or PDF")
        close_action = self._action("&Close", self.close, "Ctrl+W")
        menu = self.menuBar().addMenu("&File")
        menu.addActions([self.save_action, close_action])

        self.properties_action = self._action(
            "&Axes Properties...", lambda: self.edit_part(0, ""), "Ctrl+E",
            "Titles, axis labels, limits, scales, grid, legend and line styles")
        self.title_action = self._action("Figure &Title...", self.edit_figure_title,
                                         tip="Title above all subplots")
        self.grid_action = self._action("&Grid On/Off", self.toggle_grid, "Ctrl+G")
        self.legend_action = self._action("&Legend On/Off", self.toggle_legend, "Ctrl+L")
        self.undo_action = self._action("&Undo All Changes", self.undo_changes,
                                        tip="Show the figure as the script drew it")
        self.undo_action.setEnabled(False)
        edit = self.menuBar().addMenu("&Edit")
        edit.addActions([self.properties_action, self.title_action])
        edit.addSeparator()
        edit.addActions([self.grid_action, self.legend_action])
        edit.addSeparator()
        edit.addAction(self.undo_action)

        self.reset_zoom_action = self._action("&Reset Zoom", self.reset_zoom, "Ctrl+0",
                                              "Show all the data again after zooming")
        self.equal_action = self._action("&Equal Axis Scaling On/Off", self.toggle_equal)
        view = self.menuBar().addMenu("&View")
        view.addActions([self.reset_zoom_action, self.equal_action])

    # -- editing ---------------------------------------------------------------
    def apply_edit(self, spec: FigureSpec) -> None:
        self._show(spec)
        self.statusBar().showMessage("Changed in this window only; Save As keeps the changes",
                                     5000)

    def edit_part(self, index: int, part: str) -> None:
        """Open the properties dialog for axes ``index`` with ``part`` ('title', 'xlabel',
        'ylabel', 'zlabel', 'figure' or '') ready to edit."""
        if self.spec is None or not self.spec.axes:
            if self.spec is not None and index == -1:
                self.edit_figure_title()
            return
        index = max(0, min(index, len(self.spec.axes) - 1))
        colors = tuple(series_color(self.view.theme, i, None) for i in range(8))
        dialog = AxesPropertiesDialog(self.spec, index, part if index >= 0 else "figure",
                                      self, colors)
        dialog.applied = self.apply_edit  # Apply shows the change at once
        self.dialog = dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_edit(dialog.result_spec())
        self.dialog = None

    def edit_figure_title(self, text: str | None = None) -> None:
        if self.spec is None:
            return
        if text is None:
            text, ok = QInputDialog.getText(self, "Figure title", "Title above all subplots:",
                                            QLineEdit.EchoMode.Normal, self.spec.title)
            if not ok:
                return
        self.apply_edit(edit_figure_title(self.spec, text))

    def toggle_grid(self) -> None:
        if self.spec is not None and self.spec.axes:
            on = not all(a.grid for a in self.spec.axes)
            self.apply_edit(set_all_axes(self.spec, grid=on))

    def toggle_legend(self) -> None:
        if self.spec is not None and self.spec.axes:
            on = not all(a.legend for a in self.spec.axes)
            self.apply_edit(set_all_axes(self.spec, legend=on))

    def toggle_equal(self) -> None:
        if self.spec is not None and self.spec.axes:
            on = not all(a.equal_aspect for a in self.spec.axes)
            self.apply_edit(set_all_axes(self.spec, equal_aspect=on))

    def reset_zoom(self) -> None:
        if self.spec is not None:
            self.view.set_figure(self.spec)

    def undo_changes(self) -> None:
        if self.script_spec is not None:
            self._show(self.script_spec)
            self.statusBar().showMessage("Back to the figure as the script drew it", 4000)

    # -- saving ----------------------------------------------------------------
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
