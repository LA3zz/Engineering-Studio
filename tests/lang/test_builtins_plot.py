"""Plot commands through the interpreter (P5.1). Spec contents must equal the data passed in."""

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import to_function_syntax
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_plot import install_plot
from engstudio.lang.interp import Interpreter


class Rig:
    def __init__(self):
        self.interp = Interpreter()
        install_core(self.interp)
        self.published = []
        self.retired = []
        self.manager = install_plot(self.interp, self.published.append, self.retired.append)

    def run(self, code):
        self.interp.execute(to_function_syntax(code), None)

    def last(self):
        return self.published[-1]


@pytest.fixture
def rig():
    return Rig()


def test_plot_xy_spec_holds_the_data(rig):
    rig.run("x = [0 1 2 3]; y = x.^2; plot(x, y)")
    (s,) = rig.last().axes[0].series
    assert s.x.tolist() == [0, 1, 2, 3] and s.y.tolist() == [0, 1, 4, 9]
    assert rig.last().number == 1


def test_plot_y_only_and_column_vector(rig):
    rig.run("plot([5; 6; 7])")
    (s,) = rig.last().axes[0].series
    assert s.x.tolist() == [1, 2, 3] and s.y.tolist() == [5, 6, 7]


def test_plot_matrix_columns_and_linespec(rig):
    rig.run("plot([1 2 3]', [1 10; 2 20; 3 30], 'r--')")
    a, b = rig.last().axes[0].series
    assert a.y.tolist() == [1, 2, 3] and b.y.tolist() == [10, 20, 30]
    assert a.color == "#ff0000" and a.line_style == "--"


def test_two_groups_and_name_value(rig):
    rig.run("plot(1:3, [1 4 9], 'g', 1:3, [2 3 4], 'b:', 'LineWidth', 2, 'DisplayName', 'd')")
    a, b = rig.last().axes[0].series
    assert (a.color, b.color, b.line_style, a.line_width, a.label) == (
        "#00ff00", "#0000ff", ":", 2.0, "d")


def test_hold_on_command_syntax_appends(rig):
    rig.run("plot([1 2]); hold on; plot([3 4]); hold off; plot([5 6])")
    assert len(rig.published[1].axes[0].series) == 2
    assert [s.y.tolist() for s in rig.last().axes[0].series] == [[5, 6]]


def test_hold_returns_state(rig):
    rig.run("hold on; a = ishold; hold off; b = ishold")
    assert bool(rig.interp.workspace["a"].item()) is True
    assert bool(rig.interp.workspace["b"].item()) is False


def test_figure_numbers_name_and_handles(rig):
    rig.run("f = figure('Name', 'Mode shapes', 'Color', 'w', 'Position', [100 100 1000 700]);"
            " g = figure; h = gcf")
    ws = rig.interp.workspace
    assert (ws["f"].item(), ws["g"].item(), ws["h"].item()) == (1, 2, 2)
    assert rig.published[0].name == "Mode shapes"
    assert rig.manager.props(1)["Position"] == [100, 100, 1000, 700]


def test_gca_is_stable_handle(rig):
    rig.run("a = gca; plot([1 2]); b = gca")
    ws = rig.interp.workspace
    assert ws["a"].item() == ws["b"].item() > 100000


def test_plot_handles_returned(rig):
    rig.run("h = plot([1 2; 3 4]);")
    assert rig.interp.workspace["h"].shape == (2, 1)


def test_clf_cla_and_close(rig):
    rig.run("plot([1 2]); cla")
    assert rig.last().axes[0].series == ()
    rig.run("plot([1 2]); clf")
    assert rig.last().axes == ()
    rig.run("figure(3); close all")
    assert rig.retired == [1, 3]
    rig.run("close all")  # nothing open: fine
    rig.run("figure(4); close(4)")
    assert rig.retired[-1] == 4


def test_drawnow_republishes(rig):
    rig.run("plot([1 2]); drawnow")
    assert len(rig.published) == 2 and rig.published[0] == rig.published[1]


@pytest.mark.parametrize("code, text", [
    ("plot()", "Not enough input"),
    ("plot([1 2 3], [1 2])", "same length"),
    ("plot([1 2], 'Colour', 'r')", "unrecognized property"),
    ("plot([1 2], 'rr')", "pairs|expected data|invalid"),
    ("plot('abc')", "expected data"),
    ("plot({1})", "unsupported argument"),
    ("figure(0)", "figure number|integer"),
    ("figure('Foo', 1)", "unrecognized property"),
    ("figure('Position', [1 2 3])", "four elements"),
    ("close(9)", "does not exist"),
    ("close('foo')", "all"),
    ("hold maybe", "unknown option"),
])
def test_errors(rig, code, text):
    with pytest.raises(EngStudioError, match=text):
        rig.run(code)


def test_plot_values_are_not_shared(rig):
    rig.run("v = [1 2 3]; plot(v); v(1) = 99;")
    assert rig.last().axes[0].series[0].y.tolist() == [1, 2, 3]
    assert not np.shares_memory(rig.last().axes[0].series[0].y, rig.interp.workspace["v"])


def test_figure_position_sets_window_size(rig):
    rig.run("figure('Position', [100 100 1000 700]); plot(1:2)")
    assert rig.last().size == (1000, 700)
    rig.run("figure(2); plot(1)")
    assert rig.last().size is None


def test_drawnow_options(rig):
    rig.run("plot(1:2); drawnow limitrate; drawnow('nocallbacks')")
    with pytest.raises(EngStudioError, match="drawnow: options"):
        rig.run("drawnow sometimes")
