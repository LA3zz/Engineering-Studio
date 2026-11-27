"""Renders a ``FigureSpec`` with PyQtGraph. The GUI only ever sees the spec (plain data)."""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from engstudio.gui.plot_params import (
    bar_width,
    plot_colors,
    series_color,
    symbol_for,
    symbol_size,
    tick_values,
    view_range,
)
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec
from engstudio.plotting.text import tex_to_html, tex_to_unicode

__all__ = ["FigureView"]

_PEN_QT = {
    "-": Qt.PenStyle.SolidLine,
    "--": Qt.PenStyle.DashLine,
    ":": Qt.PenStyle.DotLine,
    "-.": Qt.PenStyle.DashDotLine,
}


class FigureView(pg.GraphicsLayoutWidget):
    """Axes laid out on the figure's rows x cols grid (``FigureSpec.placements``), with the
    figure title (sgtitle) in a row above. ``warnings`` lists anything in the last spec that
    could not be drawn faithfully."""

    def __init__(self, theme: str = "light", parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        colors = plot_colors(theme)  # validates the theme name
        self.theme = theme
        self.setBackground(colors[0])
        self.warnings: list[str] = []
        self._spec: FigureSpec | None = None
        self._plots: list[pg.PlotItem] = []
        self.title_label: pg.LabelItem | None = None

    # -- public API ---------------------------------------------------------
    def plot_items(self) -> list[pg.PlotItem]:
        return list(self._plots)

    def set_theme(self, name: str) -> None:
        colors = plot_colors(name)  # raises ValueError before any change
        self.theme = name
        self.setBackground(colors[0])
        if self._spec is not None:
            self.set_figure(self._spec)

    def set_figure(self, spec: FigureSpec) -> None:
        self._spec = spec
        self.warnings = []
        self.clear()
        self._plots = []
        self.title_label = None
        top = 0
        if spec.title:
            _bg, fg = plot_colors(self.theme)
            self.title_label = self.addLabel(
                tex_to_html(spec.title), row=0, col=0, colspan=spec.cols, color=fg, size="12pt")
            top = 1
        for i, (axes, (r, c, rs, cs)) in enumerate(
                zip(spec.axes, spec.placements(), strict=True)):
            self._plots.append(self._add_axes(r + top, c, rs, cs, axes, i + 1))

    # -- internals ----------------------------------------------------------
    def _add_axes(self, row: int, col: int, rowspan: int, colspan: int, ax: AxesSpec,
                  number: int) -> pg.PlotItem:
        _bg, fg = plot_colors(self.theme)
        mode = ax.interpreter
        plot = self.addPlot(row=row, col=col, rowspan=rowspan, colspan=colspan)
        for name in ("left", "bottom"):
            axis = plot.getAxis(name)
            axis.setPen(fg)
            axis.setTextPen(fg)
            axis.enableAutoSIPrefix(False)  # MATLAB shows plain numbers, never "(x0.001)"
        if ax.title:
            plot.setTitle(tex_to_html(ax.title, mode).replace("\n", "<br>"), color=fg)
        if ax.xlabel:
            plot.setLabel("bottom", tex_to_html(ax.xlabel, mode).replace("\n", "<br>"),
                          color=fg)
        if ax.ylabel:
            plot.setLabel("left", tex_to_html(ax.ylabel, mode).replace("\n", "<br>"), color=fg)
        log_x, log_y = ax.xscale == "log", ax.yscale == "log"
        plot.setLogMode(x=log_x, y=log_y)
        plot.showGrid(x=ax.grid, y=ax.grid, alpha=0.3)
        if ax.legend:
            plot.addLegend(offset=(-10, 10), labelTextColor=fg)
        for i, series in enumerate(ax.series):
            color = series_color(self.theme, i, series.color)
            if series.kind in ("bar", "area", "stem") and (log_x or log_y):
                self.warnings.append(
                    f"axes {number}: {series.kind} series are not drawn on logarithmic axes")
                continue
            self._add_series(plot, series, color, ax.legend, mode, log_x, log_y)
        for t in ax.texts:
            item = pg.TextItem(html=f'<span style="color:{t.color or fg}">'
                               f"{tex_to_html(t.text, mode)}</span>", anchor=(0, 0.5))
            item.setPos(t.x, t.y)
            plot.addItem(item)
        for which, scale in (("x", ax.xscale), ("y", ax.yscale)):
            pairs = ax.tick_pairs(which)
            if pairs is not None:
                plot.getAxis("bottom" if which == "x" else "left").setTicks(
                    [[(v, tex_to_unicode(lbl, mode)) for v, lbl in tick_values(pairs, scale)]])
        if ax.equal_aspect:
            plot.setAspectLocked(True)
        xr = view_range(ax.xlim, ax.xscale)
        if xr is not None:
            plot.setXRange(*xr, padding=0)
        yr = view_range(ax.ylim, ax.yscale)
        if yr is not None:
            plot.setYRange(*yr, padding=0)
        return plot

    @staticmethod
    def _add_series(plot: pg.PlotItem, s: SeriesSpec, color: str, legend: bool,
                    mode: str, log_x: bool = False, log_y: bool = False) -> None:
        name = tex_to_html(s.label, mode) if (legend and s.label) else None
        edge = s.edge_color or color
        if s.kind in ("xline", "yline"):
            log = log_x if s.kind == "xline" else log_y
            for v in s.x:
                if log and v <= 0:
                    continue  # not on a logarithmic axis
                plot.addItem(pg.InfiniteLine(  # log axes work in log10 view units
                    pos=math.log10(v) if log else float(v), angle=90 if s.kind == "xline" else 0,
                    pen=pg.mkPen(color=s.color or "#262626", width=s.line_width,
                                 style=_PEN_QT[s.line_style])))
            return
        if s.kind == "errorbar":
            plot.addItem(pg.ErrorBarItem(x=s.x, y=s.y, top=s.err_high, bottom=s.err_low,
                                         beam=0.3 * bar_width(s.x),  # caps, as in MATLAB
                                         pen=pg.mkPen(color=color, width=s.line_width)))
        if s.kind == "bar":
            width = s.bar_width if s.bar_width is not None else bar_width(s.x)
            item = pg.BarGraphItem(x=s.x, y0=s.base_value, height=s.y - s.base_value,
                                   width=width, brush=color, pen=edge)
            plot.addItem(item)
            if name:
                plot.legend.addItem(item, name)  # type: ignore[union-attr]
            return
        pen = None if s.kind == "scatter" else pg.mkPen(
            color=color if s.kind != "area" else edge, width=s.line_width,
            style=_PEN_QT[s.line_style])
        kwargs: dict[str, object] = {}
        symbol = symbol_for(s.marker, s.kind)
        if symbol is not None:
            kwargs.update(symbol=symbol, symbolSize=symbol_size(s.marker, s.marker_size),
                          symbolBrush=color, symbolPen=color)
        if s.kind == "stem":
            n = s.x.size
            xs = np.column_stack([s.x, s.x, np.full(n, np.nan)]).reshape(-1)
            ys = np.column_stack([np.full(n, s.base_value), s.y, np.full(n, np.nan)]).reshape(-1)
            plot.plot(xs, ys, pen=pen, connect="finite")
            plot.plot(s.x, s.y, pen=None, name=name, **kwargs)
            return
        if s.kind == "area":
            kwargs.update(fillLevel=s.base_value, brush=color)
        plot.plot(s.x, s.y, pen=pen, name=name, connect="finite", **kwargs)
