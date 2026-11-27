"""Embedded Matplotlib canvas for figures PyQtGraph cannot draw (3-D, polar, surface and
contour axes; design pick 1). The figure is drawn by the same code as file export, so the
window and a saved PNG/PDF look the same. A toolbar gives pan, zoom and (3-D) rotation.
Double-clicking a title, an axis label or an axes emits `edit_requested` (as `FigureView`)."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from engstudio.app.figure_export import draw_into
from engstudio.gui.plot_params import plot_colors
from engstudio.plotting.model import FigureSpec

__all__ = ["MplFigureView"]


class MplFigureView(QWidget):
    edit_requested = Signal(int, str)  # axes index (-1: figure title), part

    def __init__(self, theme: str = "light", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        plot_colors(theme)  # validates the theme name
        self.theme = theme
        self.warnings: list[str] = []
        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self._spec: FigureSpec | None = None
        self.canvas.mpl_connect("button_press_event", self._on_press)

    def main_axes(self) -> list:
        """The figure's axes in spec order (colour bars left out)."""
        return [a for a in self.figure.axes if a.get_label() != "<colorbar>"]

    def part_at(self, event) -> tuple[int, str] | None:
        suptitle = getattr(self.figure, "_suptitle", None)
        if suptitle is not None and suptitle.contains(event)[0]:
            return -1, "figure"
        for i, ax in enumerate(self.main_axes()):
            labels = [("title", ax.title), ("xlabel", ax.xaxis.label),
                      ("ylabel", ax.yaxis.label)]
            if hasattr(ax, "zaxis"):
                labels.append(("zlabel", ax.zaxis.label))
            for part, artist in labels:
                if artist.get_text() and artist.contains(event)[0]:
                    return i, part
            if event.inaxes is ax:
                return i, ""
        return None

    def _on_press(self, event) -> None:
        if event.dblclick:
            hit = self.part_at(event)
            if hit is not None:
                self.edit_requested.emit(*hit)

    def set_theme(self, name: str) -> None:
        plot_colors(name)
        self.theme = name  # Matplotlib figures keep MATLAB's white background in both themes
        if self._spec is not None:
            self.set_figure(self._spec)

    def set_figure(self, spec: FigureSpec) -> None:
        self._spec = spec
        self.warnings = []
        self.figure.clear()
        draw_into(self.figure, spec)
        self.canvas.draw_idle()
