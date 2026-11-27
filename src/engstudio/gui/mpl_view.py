"""Embedded Matplotlib canvas for figures PyQtGraph cannot draw (3-D, polar, surface and
contour axes; design pick 1). The figure is drawn by the same code as file export, so the
window and a saved PNG/PDF look the same. A toolbar gives pan, zoom and (3-D) rotation."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget

from engstudio.app.figure_export import draw_into
from engstudio.gui.plot_params import plot_colors
from engstudio.plotting.model import FigureSpec

__all__ = ["MplFigureView"]


class MplFigureView(QWidget):
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
