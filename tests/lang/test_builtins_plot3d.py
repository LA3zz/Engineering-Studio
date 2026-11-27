"""3-D, gridded, polar and reference-line plot commands (P5.4)."""

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import to_function_syntax
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.builtins_plot import install_plot
from engstudio.lang.interp import Interpreter
from engstudio.plotting.export import build_figure


class Rig:
    def __init__(self):
        self.interp = Interpreter()
        install_core(self.interp)
        install_extra(self.interp)
        self.published = []
        install_plot(self.interp, self.published.append, lambda n: None)

    def run(self, code):
        self.interp.execute(to_function_syntax(code), None)

    def axes(self, i=0):
        return self.published[-1].axes[i]

    def ws(self, name):
        return self.interp.workspace[name]


@pytest.fixture
def rig():
    return Rig()


GRID = "[X, Y] = meshgrid(1:4, 1:3); Z = X + 10*Y;"


def test_plot3_line_with_z(rig):
    rig.run("t = 0:3; plot3(t, 2*t, t.^2, 'r--')")
    a = rig.axes()
    (s,) = a.series
    assert a.projection == "3d" and s.z.tolist() == [0, 1, 4, 9] and s.color == "#ff0000"
    assert rig.published[-1].needs_matplotlib


def test_scatter3(rig):
    rig.run("scatter3([1 2], [3 4], [5 6], 49, 'filled')")
    (s,) = rig.axes().series
    assert s.kind == "scatter" and s.z.tolist() == [5, 6] and s.marker_size == pytest.approx(7)


def test_surf_grid_matches_input(rig):
    rig.run(GRID + " surf(X, Y, Z); zlabel('z'); colormap jet; colorbar")
    a = rig.axes()
    (g,) = a.surfaces
    assert g.kind == "surface" and g.z.shape == (3, 4)
    assert np.array_equal(g.z, rig.ws("Z")) and g.x[0].tolist() == [1, 2, 3, 4]
    assert (a.projection, a.zlabel, a.colormap, a.colorbar) == ("3d", "z", "jet", True)


def test_surf_z_only_uses_indices(rig):
    rig.run("surf([1 2 3; 4 5 6])")
    (g,) = rig.axes().surfaces
    assert g.x[0].tolist() == [1, 2, 3] and g.y[:, 0].tolist() == [1, 2]


def test_mesh_and_shading(rig):
    rig.run(GRID + " surf(X, Y, Z); shading interp")
    assert rig.axes().surfaces[0].edge_color == "none"
    rig.run("mesh(X, Y, Z)")
    assert rig.axes().surfaces[0].kind == "mesh"


def test_contour_levels_and_2d_projection(rig):
    rig.run(GRID + " contour(X, Y, Z, 5, 'ShowText', 'on')")
    a = rig.axes()
    (g,) = a.surfaces
    assert a.projection == "2d" and g.levels == 5 and g.show_text
    rig.run("contourf(Z, [12 20 30])")
    assert rig.axes().surfaces[0].levels == (12, 20, 30)
    assert rig.published[-1].needs_matplotlib


def test_contour_outputs(rig):
    rig.run(GRID + " [C, h] = contour(X, Y, Z);")
    assert rig.ws("C").size == 0 and rig.ws("h").item() > 100000


def test_view_zlim(rig):
    rig.run(GRID + " surf(X, Y, Z); view(45, 20); zlim([0 50]); v = view;")
    a = rig.axes()
    assert a.view == (45, 20) and a.zlim == (0, 50) and rig.ws("v").tolist() == [[45, 20]]
    rig.run("view(2)")
    assert rig.axes().view == (0, 90)


def test_hold_keeps_3d_projection(rig):
    rig.run(GRID + " surf(X, Y, Z); hold on; plot3([1 2], [1 2], [20 30])")
    a = rig.axes()
    assert a.projection == "3d" and len(a.surfaces) == 1 and len(a.series) == 1


def test_polarplot(rig):
    rig.run("th = linspace(0, 2*pi, 5); polarplot(th, ones(1, 5))")
    assert rig.axes().projection == "polar"
    rig.run("plot(1:3)")  # a plain plot resets the projection
    assert rig.axes().projection == "2d"


def test_errorbar_forms(rig):
    rig.run("errorbar([1 2 3], [0.1 0.2 0.3])")
    (s,) = rig.axes().series
    assert s.kind == "errorbar" and s.x.tolist() == [1, 2, 3] and s.err_low.tolist() == [
        0.1, 0.2, 0.3]
    rig.run("errorbar(1:2, [5 6], [1 2], [3 4], 'ro', 'DisplayName', 'm')")
    (s,) = rig.axes().series
    assert s.err_low.tolist() == [1, 2] and s.err_high.tolist() == [3, 4] and s.label == "m"


def test_xline_yline_do_not_clear(rig):
    rig.run("plot(1:3); xline(2, '--'); yline([1 2], 'Color', 'r', 'Label', 'lim')")
    kinds = [s.kind for s in rig.axes().series]
    assert kinds == ["line", "xline", "yline"]
    assert rig.axes().series[2].x.tolist() == [1, 2] and rig.axes().series[2].label == "lim"


def test_specs_render_with_matplotlib(rig):
    rig.run(GRID + " subplot(2,2,1); surf(X,Y,Z); colorbar; subplot(2,2,2); contourf(X,Y,Z);"
            " subplot(2,2,3); polarplot([0 1 2], [1 2 3]); subplot(2,2,4);"
            " errorbar(1:3, 1:3, [1 1 1]); xline(2)")
    fig = build_figure(rig.published[-1])
    names = [ax.name for ax in fig.axes]
    assert "3d" in names and "polar" in names


@pytest.mark.parametrize("code, text", [
    ("plot3([1 2], [1 2])", "plot3\\(x, y, z\\)"),
    ("surf([1 2 3])", "at least 2x2"),
    ("surf(1:3, 1:2, ones(3, 3))", "must match"),
    ("colormap('nope')", "unknown colormap"),
    ("view(1, 2, 3)", "Too many"),
    ("errorbar(1)", "errorbar\\(x, y, err\\)"),
    ("errorbar([1 2], [1 2], [1 2 3])", "points"),
    ("xline()", "xline\\(value\\)"),
    ("surf(ones(2), ones(2), ones(2), ones(2))", "colour matrix"),
])
def test_errors(rig, code, text):
    with pytest.raises(EngStudioError, match=text):
        rig.run(code)
