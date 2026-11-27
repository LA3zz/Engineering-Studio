"""2-D plot types (P5.3): data in the spec must match the arguments exactly."""

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import to_function_syntax
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.builtins_plot import install_plot
from engstudio.lang.interp import Interpreter


class Rig:
    def __init__(self):
        self.interp = Interpreter()
        install_core(self.interp)
        install_extra(self.interp)
        self.published = []
        install_plot(self.interp, self.published.append, lambda n: None)

    def run(self, code):
        self.interp.execute(to_function_syntax(code), None)

    def series(self):
        return self.published[-1].axes[0].series

    def ws(self, name):
        return self.interp.workspace[name]


@pytest.fixture
def rig():
    return Rig()


def test_bar_vector_width_and_facecolor(rig):
    rig.run("bar([3 -1 2], 0.6, 'FaceColor', [0.2 0.45 0.8])")
    (s,) = rig.series()
    assert s.kind == "bar" and s.x.tolist() == [1, 2, 3] and s.y.tolist() == [3, -1, 2]
    assert s.bar_width == pytest.approx(0.6) and s.color == "#3373cc"


def test_bar_x_spacing_and_color_letter(rig):
    rig.run("bar([0 2 4], [1 2 3], 'r')")
    (s,) = rig.series()
    assert s.x.tolist() == [0, 2, 4] and s.bar_width == pytest.approx(1.6)
    assert s.color == "#ff0000"


def test_bar_grouped_matrix(rig):
    rig.run("bar([1 2; 3 4; 5 6])")
    a, b = rig.series()
    assert a.y.tolist() == [1, 3, 5] and b.y.tolist() == [2, 4, 6]
    assert np.all(a.x < b.x) and a.bar_width == b.bar_width
    assert (a.x + b.x).tolist() == pytest.approx([2, 4, 6])  # symmetric about the group


def test_bar_then_hold_then_plot_zero_line(rig):
    rig.run("bar([1 -1]); hold on; plot([0.5 2.5], [0 0], 'k-')")
    kinds = [s.kind for s in rig.series()]
    assert kinds == ["bar", "line"]


def test_stem_and_basevalue(rig):
    rig.run("stem([0 1 2], [1 -1 2], 'filled', 'BaseValue', 0.5)")
    (s,) = rig.series()
    assert s.kind == "stem" and s.marker == "o" and s.base_value == 0.5
    assert s.y.tolist() == [1, -1, 2]


def test_stairs_is_a_step_line(rig):
    rig.run("stairs([0 1 2], [5 6 7])")
    (s,) = rig.series()
    assert s.kind == "line"
    assert s.x.tolist() == [0, 1, 1, 2, 2] and s.y.tolist() == [5, 5, 6, 6, 7]


def test_area(rig):
    rig.run("area(1:3, [2 4 3], 'FaceColor', 'g')")
    (s,) = rig.series()
    assert s.kind == "area" and s.color == "#00ff00" and s.base_value == 0


def test_scatter_size_color_marker(rig):
    rig.run("scatter([1 2 3], [3 2 1], 64, [1 0 0], 'filled', 'd')")
    (s,) = rig.series()
    assert s.kind == "scatter" and s.marker_size == pytest.approx(8.0)
    assert s.color == "#ff0000" and s.marker == "d"


@pytest.mark.parametrize("fn, xs, ys", [("semilogx", "log", "linear"),
                                        ("semilogy", "linear", "log"),
                                        ("loglog", "log", "log")])
def test_log_plots_set_scales(rig, fn, xs, ys):
    rig.run(f"{fn}([1 10 100], [1 10 100])")
    a = rig.published[-1].axes[0]
    assert (a.xscale, a.yscale) == (xs, ys)
    rig.run("plot([1 2], [3 4])")  # plot without hold resets the scales
    a = rig.published[-1].axes[0]
    assert (a.xscale, a.yscale) == ("linear", "linear")


def test_histogram_counts_and_edges(rig):
    rig.run("histogram([1 2 2 3 3 3 4], [0.5 1.5 2.5 3.5 4.5])")
    (s,) = rig.series()
    assert s.y.tolist() == [1, 2, 3, 1] and s.x.tolist() == [1, 2, 3, 4]
    assert s.bar_width == pytest.approx(1.0)


def test_histogram_nbins_and_probability(rig):
    rig.run("histogram([0 0 1 1], 2, 'Normalization', 'probability')")
    (s,) = rig.series()
    assert s.y.tolist() == pytest.approx([0.5, 0.5])


def test_histogram_pdf_integrates_to_one(rig):
    rig.run("rng(1); histogram(randn(1, 1000), 'Normalization', 'pdf')")
    (s,) = rig.series()
    assert float(np.sum(s.y * s.bar_width)) == pytest.approx(1.0)


def test_hist_outputs_do_not_plot(rig):
    rig.run("[n, c] = hist([1 1 2 3 3 3], 3);")
    assert rig.ws("n").tolist() == [[2, 1, 3]]
    assert rig.ws("c").ravel().tolist() == pytest.approx([4 / 3, 2, 8 / 3])
    assert rig.published == []


def test_histcounts(rig):
    rig.run("[n, e] = histcounts([1 2 2 3], [0 1.5 2.5 3.5]);")
    assert rig.ws("n").tolist() == [[1, 2, 1]]
    assert rig.ws("e").tolist() == [[0, 1.5, 2.5, 3.5]]


def test_plot_handles_from_bar(rig):
    rig.run("h = bar([1 2; 3 4]);")
    assert rig.ws("h").shape == (2, 1)


@pytest.mark.parametrize("code, text", [
    ("bar([1 2], 'stacked')", "not supported"),
    ("bar()", "Not enough"),
    ("bar([1 2], 'Bogus', 1)", "unrecognized property"),
    ("area([1 2; 3 4])", "stacked areas"),
    ("scatter([1 2], [1 2 3])", "same length"),
    ("scatter([1 2], [1 2], [5 6])", "per-point"),
    ("histogram([1 2 3], [0 1 3])", "unevenly"),
    ("histogram([1 2], 'Normalization', 'odd')", "Normalization"),
    ("stem([1 2], [1 2 3])", "one value per row"),
])
def test_errors(rig, code, text):
    with pytest.raises(EngStudioError, match=text):
        rig.run(code)
