"""Axes and annotation commands (P5.2) through the interpreter, incl. command syntax."""

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
        self.manager = install_plot(self.interp, self.published.append, lambda n: None)

    def run(self, code):
        self.interp.execute(to_function_syntax(code), None)

    def last(self, number=None):
        specs = [s for s in self.published if number is None or s.number == number]
        return specs[-1]

    def ws(self, name):
        return self.interp.workspace[name]


@pytest.fixture
def rig():
    return Rig()


def test_subplot_grid_and_cells(rig):
    rig.run("for k = 1:4, subplot(2,2,k); plot([1 2], [k k]); end")
    spec = rig.last()
    assert (spec.rows, spec.cols) == (2, 2)
    assert spec.placements() == [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]
    assert [a.series[0].y.tolist() for a in spec.axes] == [[1, 1], [2, 2], [3, 3], [4, 4]]


def test_subplot_reuses_existing_axes(rig):
    rig.run("subplot(2,1,1); plot([1 2]); subplot(2,1,2); plot([3 4]); subplot(2,1,1);"
            " hold on; plot([5 6])")
    top = rig.last().axes[0]
    assert len(rig.last().axes) == 2 and len(top.series) == 2


def test_subplot_mixed_grids_and_span(rig):
    rig.run("subplot(2,2,1); plot(1); subplot(2,2,2); plot(2); subplot(2,1,2); plot(3)")
    spec = rig.last()
    assert (spec.rows, spec.cols) == (2, 2) and len(spec.axes) == 3
    assert spec.placements()[2] == (1, 0, 1, 2)
    rig.run("subplot(2,2,[1 2]); plot(9)")  # overlaps and replaces the two top axes
    spec = rig.last()
    assert len(spec.axes) == 2 and spec.placements()[1] == (0, 0, 1, 2)


def test_subplot_mnp_code_and_handle(rig):
    rig.run("h = subplot(212); g = gca;")
    assert rig.ws("h").item() == rig.ws("g").item()
    assert rig.last().placements() == [(1, 0, 1, 1)]


def test_labels_title_grid_sgtitle(rig):
    rig.run("plot([1 2 3]); title('Mode 1: \\omega'); xlabel('Time (s)'); ylabel('x');"
            " grid on; sgtitle('Response')")
    spec = rig.last()
    a = spec.axes[0]
    assert (a.title, a.xlabel, a.ylabel, a.grid, spec.title) == (
        "Mode 1: \\omega", "Time (s)", "x", True, "Response")
    rig.run("grid off")
    assert rig.last().axes[0].grid is False
    rig.run("grid")
    assert rig.last().axes[0].grid is True


def test_title_cell_is_multiline_and_interpreter(rig):
    rig.run("plot(1); title({'a', 'b'}, 'Interpreter', 'none', 'FontSize', 14)")
    a = rig.last().axes[0]
    assert a.title == "a\nb" and a.interpreter == "none"


def test_plot_resets_labels_without_hold(rig):
    rig.run("plot(1:3); title('t'); xlim([0 5]); plot(1:3)")
    a = rig.last().axes[0]
    assert a.title == "" and a.xlim is None


def test_xlim_ylim_axis(rig):
    rig.run("plot([1 2 3], [4 5 6]); xlim([0 10]); ylim([-1 1]); v = axis;")
    a = rig.last().axes[0]
    assert a.xlim == (0, 10) and a.ylim == (-1, 1)
    assert rig.ws("v").tolist() == [[0, 10, -1, 1]]
    rig.run("axis tight")
    a = rig.last().axes[0]
    assert a.xlim == (1, 3) and a.ylim == (4, 6)
    rig.run("axis([0 1 2 3]); axis equal")
    a = rig.last().axes[0]
    assert a.xlim == (0, 1) and a.ylim == (2, 3) and a.equal_aspect
    rig.run("axis auto; L = xlim;")
    assert rig.last().axes[0].xlim is None and rig.ws("L").tolist() == [[1, 3]]


def test_xlim_with_inf_keeps_data_limit(rig):
    rig.run("plot([2 8], [0 1]); xlim([5 inf])")
    assert rig.last().axes[0].xlim == (5, 8)


def test_set_gca_ticks_and_labels(rig):
    rig.run("labels = {'\\theta_1','\\theta_2','\\theta_3'}; bar([1 -2 3]);"
            " set(gca, 'XTick', 1:3, 'XTickLabel', labels, 'FontSize', 12)")
    a = rig.last().axes[0]
    assert a.xticks == (1, 2, 3)
    assert a.tick_pairs("x") == [(1, "\\theta_1"), (2, "\\theta_2"), (3, "\\theta_3")]


def test_xticks_xticklabels_functions(rig):
    rig.run("plot(1:4); xticks([1 3]); xticklabels({'a', 'b'}); t = xticks;")
    a = rig.last().axes[0]
    assert a.tick_pairs("x") == [(1, "a"), (3, "b")]
    assert rig.ws("t").tolist() == [[1, 3]]


def test_legend_labels_and_default_names(rig):
    rig.run("plot(1:3); hold on; plot(2:4); legend('first', 'second')")
    a = rig.last().axes[0]
    assert a.legend and [s.label for s in a.series] == ["first", "second"]
    rig.run("legend off")
    assert rig.last().axes[0].legend is False
    rig.run("cla; plot(1:2); hold on; plot(3:4, 'DisplayName', 'mine'); legend")
    assert [s.label for s in rig.last().axes[0].series] == ["data1", "mine"]


def test_legend_cell_and_location(rig):
    rig.run("plot([1 2; 3 4]); legend({'a', 'b'}, 'Location', 'northeast')")
    assert [s.label for s in rig.last().axes[0].series] == ["a", "b"]


def test_set_and_get_line_properties(rig):
    rig.run("h = plot(1:3); set(h, 'Color', 'r', 'LineWidth', 3, 'LineStyle', '--');"
            " w = get(h, 'LineWidth'); c = get(h, 'Color'); y = get(h, 'YData');")
    s = rig.last().axes[0].series[0]
    assert (s.color, s.line_width, s.line_style) == ("#ff0000", 3.0, "--")
    assert rig.ws("w").item() == 3 and rig.ws("c").tolist() == [[1, 0, 0]]
    assert rig.ws("y").tolist() == [[1, 2, 3]]


def test_set_figure_and_get_axes(rig):
    rig.run("f = figure; set(f, 'Name', 'My fig'); plot([1 5]); s = get(gca, 'XScale');"
            " set(gca, 'YScale', 'log'); n = get(f, 'Name');")
    assert rig.last().name == "My fig" and rig.last().axes[0].yscale == "log"
    assert rig.ws("s").to_str() == "linear" and rig.ws("n").to_str() == "My fig"


def test_text_annotation(rig):
    rig.run("plot(1:3); h = text(2, 2, 'peak', 'Color', 'k');")
    (t,) = rig.last().axes[0].texts
    assert (t.x, t.y, t.text, t.color) == (2, 2, "peak", "#000000")


def test_command_syntax_mid_line(rig):
    rig.run("plot(1:3); grid on; axis tight; box on; legend show")
    a = rig.last().axes[0]
    assert a.grid and a.xlim == (1, 3) and a.legend


def test_axes_handle_targets_other_axes(rig):
    rig.run("a1 = subplot(2,1,1); plot(1:2); subplot(2,1,2); plot(1:2); title(a1, 'top');"
            " grid(a1, 'on')")
    top, bottom = rig.last().axes
    assert top.title == "top" and top.grid and bottom.title == "" and not bottom.grid


@pytest.mark.parametrize("code, text", [
    ("subplot(2,2,5)", "position must be"),
    ("subplot(0,1,1)", "grid size"),
    ("plot(1); xlim([3 1])", "increasing"),
    ("plot(1); xlim([1 2 3])", "two-element"),
    ("plot(1); axis([0 1])", "xmin xmax"),
    ("plot(1); axis wobbly", "unknown option"),
    ("plot(1); grid sideways", "grid on"),
    ("plot(1); title()", "Not enough"),
    ("plot(1); title('a', 'Bogus', 1)", "unrecognized property"),
    ("h = plot(1); set(h, 'Bogus', 1)", "unrecognized line property"),
    ("plot(1); set(gca, 'Bogus', 1)", "unrecognized axes property"),
    ("set(123456789, 'Color', 'r')", "invalid graphics handle"),
    ("plot(1); text(1, 2)", "text\\(x, y, txt\\)"),
])
def test_errors(rig, code, text):
    with pytest.raises(EngStudioError, match=text):
        rig.run(code)


def test_snapshot_spec_is_self_consistent(rig):
    rig.run("subplot(3,1,1); plot(1:3); subplot(3,1,2); bar(1:3); subplot(3,1,3);"
            " stem(1:3)")
    spec = rig.last()
    assert spec.rows == 3 and [a.series[0].kind for a in spec.axes] == ["line", "bar", "stem"]
    assert np.all([c[1] == 0 for c in spec.placements()])
