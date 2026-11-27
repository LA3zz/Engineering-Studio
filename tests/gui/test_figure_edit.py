"""Editing figures in their window: properties dialog, menus, undo, double-click targets."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from engstudio.gui import figure_edit  # noqa: E402
from engstudio.gui.figure_edit import (  # noqa: E402
    AxesPropertiesDialog,
    edit_axes,
    edit_series,
    set_all_axes,
)
from engstudio.gui.figure_window import FigureWindow  # noqa: E402
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec, SurfaceSpec  # noqa: E402

T = np.linspace(0, 1, 20)


def two_subplots():
    a = AxesSpec(series=(SeriesSpec("line", T, np.sin(T), label="x"),
                         SeriesSpec("line", T, np.cos(T), label="v")),
                 title="Response", xlabel="t (s)", ylabel="x (m)", cell=(0, 0, 1, 1))
    b = AxesSpec(series=(SeriesSpec("line", T, T ** 2),), title="Second", cell=(1, 0, 1, 1))
    return FigureSpec(number=1, axes=(a, b), rows=2, cols=1)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_pure_edits_return_new_specs():
    spec = two_subplots()
    e = edit_axes(spec, 1, title="New", xlim=(0.0, 0.5))
    assert e.axes[1].title == "New" and e.axes[1].xlim == (0.0, 0.5)
    assert spec.axes[1].title == "Second"  # original untouched
    s = edit_series(spec, 0, 1, color="#ff0000", line_style="--", marker="o")
    assert (s.axes[0].series[1].color, s.axes[0].series[1].line_style) == ("#ff0000", "--")
    g = set_all_axes(spec, grid=True)
    assert all(a.grid for a in g.axes)


def test_dialog_edits_text_limits_and_lines(app, qtbot):
    d = AxesPropertiesDialog(two_subplots(), 0, "xlabel")
    qtbot.addWidget(d)
    d.show()
    assert d.focusWidget() is d.xlabel or d.xlabel.hasFocus() or d.xlabel.selectedText()
    d.title.setText("Free vibration")
    d.xlabel.setText("\\theta (rad)")
    d.figure_title.setText("Lab 3")
    d.xlim.auto.setChecked(False)
    d.xlim.lo.setValue(0.2)
    d.xlim.hi.setValue(0.8)
    d.yscale.setCurrentText("log")
    d.grid.setChecked(True)
    ed = d._editors[1]
    ed.name.setText("velocity")
    ed._set_color("#00aa00")
    ed.style.setCurrentIndex(1)  # dashed
    ed.width.setValue(3)
    ed.marker.setCurrentIndex(1)  # circle
    d._accept()
    out = d.result_spec()
    a = out.axes[0]
    assert (out.title, a.title, a.xlabel) == ("Lab 3", "Free vibration", "\\theta (rad)")
    assert a.xlim == (0.2, 0.8) and a.yscale == "log" and a.grid
    s = a.series[1]
    assert (s.label, s.color, s.line_style, s.line_width, s.marker) == (
        "velocity", "#00aa00", "--", 3.0, "o")


def test_dialog_switches_subplots_without_losing_edits(app, qtbot):
    d = AxesPropertiesDialog(two_subplots(), 0)
    qtbot.addWidget(d)
    d.title.setText("First edited")
    d.subplot.setCurrentIndex(1)
    assert d.title.text() == "Second"
    d.title.setText("Second edited")
    d._accept()
    assert [a.title for a in d.result_spec().axes] == ["First edited", "Second edited"]


def test_window_menus_undo_and_save(app, qtbot, tmp_path):
    w = FigureWindow(1)
    qtbot.addWidget(w)
    w.set_figure(two_subplots())
    menus = [a.text() for a in w.menuBar().actions()]
    assert menus == ["&File", "&Edit", "&View"]
    assert not w.undo_action.isEnabled()
    w.toggle_grid()
    assert all(a.grid for a in w.spec.axes) and w.undo_action.isEnabled()
    w.toggle_legend()
    w.edit_figure_title("Overall")
    assert w.spec.title == "Overall" and "Overall" in w.windowTitle()
    assert w.save_to(tmp_path / "edited.png") and (tmp_path / "edited.png").stat().st_size > 0
    w.undo_changes()
    assert w.spec is w.script_spec and not w.spec.axes[0].grid
    w.toggle_grid()
    w.set_figure(two_subplots())  # the script draws again: its version wins
    assert not w.spec.axes[0].grid


def test_edit_part_opens_the_dialog_at_the_clicked_field(app, qtbot, monkeypatch):
    seen = {}

    def fake_exec(self):
        seen["focus"] = (self.subplot.currentIndex(), self.ylabel.hasFocus()
                         or self.ylabel.selectedText() == self.ylabel.text())
        self.ylabel.setText("edited y")
        self._store()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(figure_edit.AxesPropertiesDialog, "exec", fake_exec)
    w = FigureWindow(2)
    qtbot.addWidget(w)
    w.set_figure(two_subplots())
    w.edit_part(1, "ylabel")
    assert seen["focus"][0] == 1 and w.spec.axes[1].ylabel == "edited y"


def test_double_click_targets_in_the_2d_view(app, qtbot):
    w = FigureWindow(3)
    qtbot.addWidget(w)
    spec = FigureSpec(number=3, title="Sup", axes=(AxesSpec(
        series=(SeriesSpec("line", T, T),), title="Top", xlabel="t", ylabel="y"),))
    w.set_figure(spec)
    w.resize(700, 500)
    w.show()
    qtbot.waitExposed(w)
    v = w.view
    plot = v.plot_items()[0]

    def center(item):
        c = item.sceneBoundingRect().center()
        return v.part_at(c.x(), c.y())

    assert center(v.title_label) == (-1, "figure")
    assert center(plot.titleLabel) == (0, "title")
    assert center(plot.getAxis("bottom")) == (0, "xlabel")
    assert center(plot.getAxis("left")) == (0, "ylabel")
    assert center(plot.vb) == (0, "")


def test_double_click_targets_in_the_3d_view(app, qtbot):
    from matplotlib.backend_bases import MouseEvent

    x, y = np.meshgrid(np.linspace(-1, 1, 5), np.linspace(-1, 1, 5))
    spec = FigureSpec(number=4, axes=(AxesSpec(
        surfaces=(SurfaceSpec("contourf", x, y, x * y),), title="Contours", xlabel="x"),))
    w = FigureWindow(4)
    qtbot.addWidget(w)
    w.set_figure(spec)
    v = w.view
    assert type(v).__name__ == "MplFigureView"
    v.canvas.draw()
    renderer = v.canvas.get_renderer()
    ax = v.main_axes()[0]
    for artist, want in ((ax.title, (0, "title")), (ax.xaxis.label, (0, "xlabel"))):
        box = artist.get_window_extent(renderer)
        ev = MouseEvent("button_press_event", v.canvas, *box.get_points().mean(axis=0),
                        button=1, dblclick=True)
        assert v.part_at(ev) == want
