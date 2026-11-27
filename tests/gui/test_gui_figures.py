"""Figure rendering (PyQtGraph) and figure windows. Headless (offscreen)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyqtgraph as pg
import pytest
from PySide6.QtCore import Qt

from engstudio.app.kernel.stub import StubKernelClient
from engstudio.gui.figure_window import FigureWindow
from engstudio.gui.main_window import MainWindow
from engstudio.gui.plot_params import SERIES_COLORS
from engstudio.gui.plots import FigureView
from engstudio.gui.settings import UiSettings
from engstudio.gui.theme import THEMES
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec


def series(kind="line", x=(0, 1, 2), y=(0, 1, 4), **kw):
    return SeriesSpec(kind, x, y, **kw)


def one_axes(*s, **kw):
    return FigureSpec(axes=(AxesSpec(series=tuple(s), **kw),))


def bars_in(plot):
    return [i for i in plot.items if isinstance(i, pg.BarGraphItem)]


@pytest.fixture
def view():
    v = FigureView("light")
    yield v
    v.hide()
    v.deleteLater()


def test_line_series_data_and_style(view):
    view.set_figure(one_axes(series(color="#112233", line_width=2, line_style="--")))
    (plot,) = view.plot_items()
    (item,) = plot.listDataItems()
    x, y = item.getData()
    assert list(x) == [0, 1, 2] and list(y) == [0, 1, 4]
    pen = item.opts["pen"]
    assert pen.color().name() == "#112233"
    assert pen.widthF() == 2.0
    assert pen.style() == Qt.PenStyle.DashLine


def test_default_colour_comes_from_the_theme_cycle(view):
    view.set_figure(one_axes(series(), series(y=(1, 2, 3))))
    items = view.plot_items()[0].listDataItems()
    assert [i.opts["pen"].color().name() for i in items] == list(SERIES_COLORS["light"][:2])


def test_scatter_has_symbols_and_no_line(view):
    view.set_figure(one_axes(series("scatter"), series("scatter", marker="^")))
    a, b = view.plot_items()[0].listDataItems()
    assert a.opts["pen"] is None or a.opts["pen"].style() == Qt.PenStyle.NoPen
    assert a.opts["symbol"] == "o"
    assert b.opts["symbol"] == "t1"


def test_marker_on_a_line_series(view):
    view.set_figure(one_axes(series(marker="s", marker_size=8)))
    item = view.plot_items()[0].listDataItems()[0]
    assert item.opts["symbol"] == "s" and item.opts["symbolSize"] == 8.0
    assert item.opts["pen"].style() == Qt.PenStyle.SolidLine


def test_bar_series(view):
    view.set_figure(one_axes(series("bar", x=(1, 2, 3, 4), y=(3, 5, 2, 4))))
    (plot,) = view.plot_items()
    (bar,) = bars_in(plot)
    assert list(bar.opts["height"]) == [3, 5, 2, 4]
    assert not [i for i in plot.listDataItems() if isinstance(i, pg.PlotDataItem)]


def test_title_labels_and_legend(view):
    view.set_figure(one_axes(series(label="L"), series(y=(1, 2, 3)), title="T", xlabel="X",
                             ylabel="Y", legend=True))
    (plot,) = view.plot_items()
    assert plot.titleLabel.text == "T"
    assert plot.getAxis("bottom").labelText == "X"
    assert plot.getAxis("left").labelText == "Y"
    assert plot.legend is not None and len(plot.legend.items) == 1  # only labelled series


def test_no_legend_unless_requested(view):
    view.set_figure(one_axes(series(label="L")))
    assert view.plot_items()[0].legend is None


def test_limits_linear_and_log(view):
    view.set_figure(one_axes(series(), xlim=(0, 10), ylim=(-1, 1)))
    xr, yr = view.plot_items()[0].getViewBox().viewRange()
    assert xr == pytest.approx([0, 10]) and yr == pytest.approx([-1, 1])
    view.set_figure(one_axes(series(x=(1, 10, 100)), xscale="log", xlim=(1, 100)))
    (plot,) = view.plot_items()
    assert plot.getAxis("bottom").logMode is True
    assert plot.getViewBox().viewRange()[0] == pytest.approx([0, 2])


def test_grid_on_and_off(view):
    view.set_figure(one_axes(series(), grid=True))
    assert bool(view.plot_items()[0].getAxis("bottom").grid)
    view.set_figure(one_axes(series(), grid=False))
    assert not view.plot_items()[0].getAxis("bottom").grid


def test_subplot_grid_is_row_major(view):
    a = AxesSpec(series=(series(),))
    view.set_figure(FigureSpec(axes=(a, a, a), rows=2, cols=2))
    plots = view.plot_items()
    assert len(plots) == 3
    assert view.ci.getItem(0, 0) is plots[0]
    assert view.ci.getItem(0, 1) is plots[1]
    assert view.ci.getItem(1, 0) is plots[2]


def test_set_figure_replaces_previous_content(view):
    a = AxesSpec(series=(series(),))
    view.set_figure(FigureSpec(axes=(a, a), cols=2))
    view.set_figure(one_axes(series()))
    assert len(view.plot_items()) == 1


def test_bars_on_log_axes_are_reported_not_drawn(view):
    view.set_figure(one_axes(series("bar", x=(1, 2, 3)), xscale="log"))
    assert bars_in(view.plot_items()[0]) == []
    assert len(view.warnings) == 1 and "logarithmic" in view.warnings[0]
    view.set_figure(one_axes(series()))
    assert view.warnings == []


def test_theme_switch_rerenders_and_validates(view):
    view.set_figure(one_axes(series()))
    view.set_theme("dark")
    assert view.theme == "dark"
    assert view.backgroundBrush().color().name() == THEMES["dark"].base
    item = view.plot_items()[0].listDataItems()[0]
    assert item.opts["pen"].color().name() == SERIES_COLORS["dark"][0]
    with pytest.raises(ValueError):
        view.set_theme("neon")
    assert view.theme == "dark"


def test_window_title_status_and_close_signal():
    win = FigureWindow(3, "light")
    got = []
    win.closed.connect(got.append)
    assert win.windowTitle() == "Figure 3"
    win.set_figure(one_axes(series("bar", x=(1, 2), y=(1, 2)), xscale="log"))
    assert "logarithmic" in win.statusBar().currentMessage()
    win.set_figure(FigureSpec(number=3, title="Hello"))
    assert win.windowTitle() == "Figure 3: Hello"
    assert win.statusBar().currentMessage() == ""
    win.show()
    win.close()
    assert got == [3]


def test_main_window_opens_updates_and_closes_figures():
    win = MainWindow(UiSettings(None), StubKernelClient())
    try:
        win.bridge.execute("demo_plot")
        assert list(win.figures) == [1]
        first = win.figures[1]
        assert len(first.view.plot_items()) == 2  # the demo has two axes
        assert first.isVisible()
        win.bridge.execute("demo_plot")  # same number: updated in place
        assert win.figures[1] is first
        win.bridge.execute("demo_plot 2")
        assert sorted(win.figures) == [1, 2]
        win.set_theme("dark")
        assert all(w.view.theme == "dark" for w in win.figures.values())
        win.figures[2].close()
        assert sorted(win.figures) == [1]
    finally:
        win.tabs.current_editor().document().setModified(False)
        win.close()
        win.deleteLater()
    assert win.figures == {}


# ----------------------------------------------------------------- P5.2 / P5.3 rendering
def test_cells_and_sgtitle_layout(view):
    from engstudio.plotting.model import AxesSpec as A
    spec = FigureSpec(rows=2, cols=2, title="All modes", axes=(
        A(series=(series(),), cell=(0, 0, 1, 1)), A(series=(series(),), cell=(0, 1, 1, 1)),
        A(series=(series(),), cell=(1, 0, 1, 2))))
    view.set_figure(spec)
    assert view.title_label is not None and len(view.plot_items()) == 3
    cells = [sorted(view.ci.items[p]) for p in view.plot_items()]  # (row, col) per grid cell
    assert cells == [[(1, 0)], [(1, 1)], [(2, 0), (2, 1)]]  # row 0 holds the sgtitle


def test_custom_ticks_use_unicode_subscripts(view):
    view.set_figure(one_axes(series("bar", x=(1, 2), y=(1, -1)), xticks=(1, 2),
                             xticklabels=("\\theta_1", "\\theta_2")))
    axis = view.plot_items()[0].getAxis("bottom")
    assert axis._tickLevels == [[(1.0, "θ₁"), (2.0, "θ₂")]]


def test_title_tex_becomes_html(view):
    view.set_figure(one_axes(series(), title="\\omega_n", xlabel="a^2"))
    plot = view.plot_items()[0]
    assert "ω<sub>n</sub>" in plot.titleLabel.text
    assert "a<sup>2</sup>" in plot.getAxis("bottom").labelText


def test_stem_area_and_bar_base(view):
    view.set_figure(one_axes(
        series("stem", x=(1, 2), y=(3, 4), marker="o"),
        series("area", x=(1, 2), y=(1, 2)),
        series("bar", x=(1, 2), y=(5, 6), bar_width=0.5, base_value=1.0)))
    plot = view.plot_items()[0]
    curves = [i for i in plot.items if isinstance(i, pg.PlotDataItem)]
    assert len(curves) == 3  # stem lines + stem markers + area
    assert any(c.opts.get("fillLevel") == 0.0 for c in curves)
    (bar,) = bars_in(plot)
    assert bar.opts["width"] == 0.5 and bar.opts["y0"] == 1.0
    assert list(bar.opts["height"]) == [4.0, 5.0]


def test_text_items_drawn(view):
    from engstudio.plotting.model import TextSpec
    view.set_figure(one_axes(series(), texts=(TextSpec(1, 2, "peak"),)))
    items = [i for i in view.plot_items()[0].items if isinstance(i, pg.TextItem)]
    assert len(items) == 1 and "peak" in items[0].textItem.toHtml()


def test_window_switches_to_matplotlib_for_3d_and_back(qtbot):
    from engstudio.gui.mpl_view import MplFigureView
    from engstudio.plotting.model import SurfaceSpec
    w = FigureWindow(5)
    qtbot.addWidget(w)
    surf = SurfaceSpec("surface", (0, 1), (0, 1), ((0, 1), (1, 2)))
    w.set_figure(FigureSpec(number=5, axes=(AxesSpec(surfaces=(surf,), projection="3d"),)))
    assert isinstance(w.view, MplFigureView) and w.centralWidget() is w.view
    assert len(w.view.figure.axes) == 1 and w.view.figure.axes[0].name == "3d"
    w.set_figure(one_axes(series()))
    assert isinstance(w.view, FigureView) and len(w.view.plot_items()) == 1
