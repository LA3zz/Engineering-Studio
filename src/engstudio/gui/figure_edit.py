"""Editing a figure in its window: titles, axis labels, limits, scales, grid, legend and the
look of each line (name, colour, style, width, marker).

Edits produce a new ``FigureSpec`` (specs are immutable); the window shows and saves the edited
copy. Like MATLAB's property editor, edits belong to the window: if the script draws the same
figure again, the script's version replaces them. ``Undo All Changes`` restores the figure as
the script drew it.
"""

from __future__ import annotations

import dataclasses
import math

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from engstudio.plotting.model import (
    LINE_STYLES,
    MARKERS,
    AxesSpec,
    FigureSpec,
    SeriesSpec,
)

__all__ = ["AxesPropertiesDialog", "edit_axes", "edit_figure_title", "edit_series",
           "set_all_axes"]

STYLE_NAMES = {"-": "solid", "--": "dashed", ":": "dotted", "-.": "dash-dot"}
MARKER_NAMES = {None: "none", "o": "circle", "s": "square", "^": "triangle up", "x": "cross",
                "+": "plus", "*": "star", ".": "point", "d": "diamond", "v": "triangle down",
                "<": "triangle left", ">": "triangle right", "p": "pentagon", "h": "hexagon"}
_LINE_KINDS = ("line", "scatter", "errorbar", "stem", "area", "xline", "yline")


# ----------------------------------------------------------------- pure spec editing
def edit_axes(spec: FigureSpec, index: int, **changes) -> FigureSpec:
    """A copy of ``spec`` with fields of axes ``index`` changed (AxesSpec field names)."""
    axes = list(spec.axes)
    axes[index] = dataclasses.replace(axes[index], **changes)
    return dataclasses.replace(spec, axes=tuple(axes))


def edit_series(spec: FigureSpec, index: int, series: int, **changes) -> FigureSpec:
    """A copy with fields of one series of axes ``index`` changed (SeriesSpec field names)."""
    ax = spec.axes[index]
    items = list(ax.series)
    items[series] = dataclasses.replace(items[series], **changes)
    return edit_axes(spec, index, series=tuple(items))


def edit_figure_title(spec: FigureSpec, title: str) -> FigureSpec:
    return dataclasses.replace(spec, title=title)


def set_all_axes(spec: FigureSpec, **changes) -> FigureSpec:
    """The same change (e.g. ``grid=True``) on every axes of the figure."""
    return dataclasses.replace(
        spec, axes=tuple(dataclasses.replace(a, **changes) for a in spec.axes))


def _limits(auto: bool, lo: float, hi: float) -> tuple[float, float] | None:
    if auto or not (math.isfinite(lo) and math.isfinite(hi)) or lo >= hi:
        return None
    return (lo, hi)


# ------------------------------------------------------------------------- dialog
class _LimitRow(QWidget):
    def __init__(self, limits: tuple[float, float] | None) -> None:
        super().__init__()
        self.auto = QCheckBox("Auto")
        self.lo, self.hi = QDoubleSpinBox(), QDoubleSpinBox()
        for box in (self.lo, self.hi):
            box.setRange(-1e300, 1e300)
            box.setDecimals(6)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.auto)
        row.addWidget(QLabel("from"))
        row.addWidget(self.lo, 1)
        row.addWidget(QLabel("to"))
        row.addWidget(self.hi, 1)
        self.auto.toggled.connect(lambda on: (self.lo.setEnabled(not on),
                                              self.hi.setEnabled(not on)))
        self.set(limits)

    def set(self, limits: tuple[float, float] | None, data: tuple[float, float] = (0, 1)) -> None:
        lo, hi = limits if limits is not None else data
        self.lo.setValue(lo)
        self.hi.setValue(hi)
        self.auto.setChecked(limits is None)
        self.lo.setEnabled(limits is not None)
        self.hi.setEnabled(limits is not None)

    def value(self) -> tuple[float, float] | None:
        return _limits(self.auto.isChecked(), self.lo.value(), self.hi.value())


class _SeriesEditor(QWidget):
    """Name, colour, line style, width and marker of one series."""

    def __init__(self, s: SeriesSpec, default_color: str) -> None:
        super().__init__()
        self.name = QLineEdit(s.label)
        self.name.setPlaceholderText("name shown in the legend")
        self._color = s.color
        self._default = default_color
        self.color_button = QPushButton()
        self.color_button.clicked.connect(lambda _c=False: self._pick_color())
        self.reset_color = QPushButton("Use automatic colour")
        self.reset_color.clicked.connect(lambda _c=False: self._set_color(None))
        self.style = QComboBox()
        for code in LINE_STYLES:
            self.style.addItem(STYLE_NAMES[code], code)
        self.style.setCurrentIndex(LINE_STYLES.index(s.line_style))
        self.width = QDoubleSpinBox()
        self.width.setRange(0.1, 20)
        self.width.setSingleStep(0.5)
        self.width.setValue(s.line_width)
        self.marker = QComboBox()
        for code in (None, *MARKERS):
            self.marker.addItem(MARKER_NAMES[code], code)
        self.marker.setCurrentIndex(([None, *MARKERS]).index(s.marker))
        colors = QHBoxLayout()
        colors.addWidget(self.color_button, 1)
        colors.addWidget(self.reset_color)
        form = QFormLayout(self)
        form.addRow("Name", self.name)
        form.addRow("Colour", colors)
        form.addRow("Line style", self.style)
        form.addRow("Line width", self.width)
        form.addRow("Marker", self.marker)
        self._set_color(s.color)

    def _set_color(self, color: str | None) -> None:
        self._color = color
        shown = color or self._default
        self.color_button.setText(color or "automatic")
        self.color_button.setStyleSheet(
            f"QPushButton {{ background: {shown}; color: "
            f"{'black' if QColor(shown).lightness() > 128 else 'white'}; }}")

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color or self._default), self,
                                       "Line colour")
        if chosen.isValid():
            self._set_color(chosen.name())

    def changes(self) -> dict[str, object]:
        return {"label": self.name.text(), "color": self._color,
                "line_style": self.style.currentData(), "line_width": self.width.value(),
                "marker": self.marker.currentData()}


class AxesPropertiesDialog(QDialog):
    """Edit one axes (choose which with the subplot selector when there are several) and the
    figure title. ``focus``: 'title', 'xlabel', 'ylabel', 'zlabel' or '' puts the cursor there.
    After ``exec()`` returns Accepted, ``result_spec()`` is the edited figure."""

    def __init__(self, spec: FigureSpec, index: int = 0, focus: str = "",
                 parent: QWidget | None = None,
                 default_colors: tuple[str, ...] = ("#0072BD",)) -> None:
        super().__init__(parent)
        self.setWindowTitle("Axes properties")
        self._spec = spec
        self._index = index
        self._colors = default_colors
        self.subplot = QComboBox()
        for i, ax in enumerate(spec.axes):
            self.subplot.addItem(f"Subplot {i + 1}" + (f": {ax.title}" if ax.title else ""), i)
        self.subplot.setCurrentIndex(index)
        self.subplot.setVisible(len(spec.axes) > 1)
        self.figure_title = QLineEdit(spec.title)
        self.figure_title.setPlaceholderText("title above all subplots (sgtitle)")
        self.title, self.xlabel = QLineEdit(), QLineEdit()
        self.ylabel, self.zlabel = QLineEdit(), QLineEdit()
        for box, hint in ((self.title, "e.g. Free vibration"), (self.xlabel, "e.g. t (s)"),
                          (self.ylabel, "e.g. \\theta (rad)"), (self.zlabel, "z axis")):
            box.setPlaceholderText(hint)
        self.xlim, self.ylim = _LimitRow(None), _LimitRow(None)
        self.xscale, self.yscale = QComboBox(), QComboBox()
        for box in (self.xscale, self.yscale):
            box.addItems(["linear", "log"])
        self.grid, self.legend = QCheckBox("Grid lines"), QCheckBox("Legend")
        self.equal = QCheckBox("Equal scaling (axis equal)")

        text = QGroupBox("Text (TeX works: \\theta, x^2, v_1)")
        tf = QFormLayout(text)
        tf.addRow("Figure title", self.figure_title)
        tf.addRow("Title", self.title)
        tf.addRow("X label", self.xlabel)
        tf.addRow("Y label", self.ylabel)
        self._z_row = QLabel("Z label")
        tf.addRow(self._z_row, self.zlabel)
        axes_box = QGroupBox("Axes")
        af = QFormLayout(axes_box)
        af.addRow("X limits", self.xlim)
        af.addRow("Y limits", self.ylim)
        af.addRow("X scale", self.xscale)
        af.addRow("Y scale", self.yscale)
        checks = QHBoxLayout()
        for c in (self.grid, self.legend, self.equal):
            checks.addWidget(c)
        af.addRow(checks)
        self.lines = QTabWidget()
        self.lines_box = QGroupBox("Lines")
        QVBoxLayout(self.lines_box).addWidget(self.lines)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.Apply)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.clicked.connect(lambda _c=False: self._store())
        layout = QVBoxLayout(self)
        layout.addWidget(self.subplot)
        layout.addWidget(text)
        layout.addWidget(axes_box)
        layout.addWidget(self.lines_box, 1)
        layout.addWidget(buttons)
        self._editors: list[_SeriesEditor | None] = []
        self.subplot.currentIndexChanged.connect(self._switch)
        self._load(index)
        target = {"title": self.title, "xlabel": self.xlabel, "ylabel": self.ylabel,
                  "zlabel": self.zlabel, "figure": self.figure_title}.get(focus)
        if target is not None:
            target.setFocus()
            target.selectAll()
        self.resize(520, 640)

    # -- state ---------------------------------------------------------------
    def _load(self, index: int) -> None:
        self._index = index
        ax = self._spec.axes[index]
        self.title.setText(ax.title)
        self.xlabel.setText(ax.xlabel)
        self.ylabel.setText(ax.ylabel)
        self.zlabel.setText(ax.zlabel)
        three_d = ax.projection == "3d"
        self.zlabel.setVisible(three_d)
        self._z_row.setVisible(three_d)
        self.xlim.set(ax.xlim, _data_range(ax, "x"))
        self.ylim.set(ax.ylim, _data_range(ax, "y"))
        self.xscale.setCurrentText(ax.xscale)
        self.yscale.setCurrentText(ax.yscale)
        self.grid.setChecked(ax.grid)
        self.legend.setChecked(ax.legend)
        self.equal.setChecked(ax.equal_aspect)
        self.lines.clear()
        self._editors = []
        for i, s in enumerate(ax.series):
            if s.kind not in _LINE_KINDS:
                self._editors.append(None)
                continue
            ed = _SeriesEditor(s, self._colors[i % len(self._colors)])
            self._editors.append(ed)
            self.lines.addTab(ed, s.label or f"Line {i + 1}")
        self.lines_box.setVisible(self.lines.count() > 0)

    def _store(self) -> None:
        """Write the fields of the current subplot into ``self._spec``."""
        spec = edit_figure_title(self._spec, self.figure_title.text())
        spec = edit_axes(
            spec, self._index, title=self.title.text(), xlabel=self.xlabel.text(),
            ylabel=self.ylabel.text(), zlabel=self.zlabel.text(), xlim=self.xlim.value(),
            ylim=self.ylim.value(), xscale=self.xscale.currentText(),
            yscale=self.yscale.currentText(), grid=self.grid.isChecked(),
            legend=self.legend.isChecked(), equal_aspect=self.equal.isChecked())
        for i, ed in enumerate(self._editors):
            if ed is not None:
                spec = edit_series(spec, self._index, i, **ed.changes())
        self._spec = spec
        self.applied(spec)

    def applied(self, spec: FigureSpec) -> None:
        """Hook: the window replaces this to show each Apply at once."""

    def _switch(self, _pos: int) -> None:
        self._store()
        self._load(self.subplot.currentData())

    def _accept(self) -> None:
        self._store()
        self.accept()

    def result_spec(self) -> FigureSpec:
        return self._spec


def _data_range(ax: AxesSpec, which: str) -> tuple[float, float]:
    """Smallest and largest data value along x or y (default limits shown when Auto)."""
    import numpy as np

    values = [getattr(s, which) for s in ax.series if s.kind not in ("xline", "yline")]
    values += [getattr(sf, which) for sf in ax.surfaces]
    finite = [v[np.isfinite(v)] for v in values if v.size]
    finite = [v for v in finite if v.size]
    if not finite:
        return (0.0, 1.0)
    lo = float(min(v.min() for v in finite))
    hi = float(max(v.max() for v in finite))
    return (lo, hi) if hi > lo else (lo - 1, hi + 1)
