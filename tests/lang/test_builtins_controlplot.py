"""Control response plots (Phase 6, C3): plotted data equals the engine's results."""

import math

import numpy as np
import pytest

from engstudio.control import lti
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_control import install_control
from engstudio.lang.builtins_controlplot import install_control_plots
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.builtins_plot import install_plot
from engstudio.lang.interp import Interpreter


class Rig:
    def __init__(self):
        self.interp = Interpreter()
        install_core(self.interp)
        install_extra(self.interp)
        install_control(self.interp)
        self.published = []
        manager = install_plot(self.interp, self.published.append, lambda n: None)
        install_control_plots(self.interp, manager)

    def run(self, code):
        self.interp.execute(code, None)
        return self.interp.workspace

    def last(self):
        return self.published[-1]


@pytest.fixture
def rig():
    return Rig()


def test_step_plot_and_data(rig):
    rig.run("G = tf(1, [1 1]); step(G, 5);")
    a = rig.last().axes[0]
    (s,) = a.series
    assert a.title == "Step Response" and a.xlabel == "Time (seconds)"
    assert np.max(np.abs(s.y - (1 - np.exp(-s.x)))) < 1e-6
    ws = rig.run("[y, t] = step(G, 5);")
    assert ws["y"].shape[1] == 1 and ws["t"][-1, 0] == pytest.approx(5)
    assert len(rig.published) == 1  # the data form draws nothing


def test_several_systems_with_linespecs(rig):
    rig.run("G = tf(1, [1 1]); step(G, 'r--', feedback(G, 1), 'b');")
    a, b = rig.last().axes[0].series
    assert (a.color, a.line_style, b.color) == ("#ff0000", "--", "#0000ff")
    assert b.y[-1] == pytest.approx(0.5, rel=1e-3)


def test_impulse_initial_lsim(rig):
    rig.run("impulse(tf(1, [1 1]), 3);")
    s = rig.last().axes[0].series[0]
    assert np.max(np.abs(s.y - np.exp(-s.x))) < 1e-6
    rig.run("initial(ss(-2, 1, 1, 0), 3, 1);")
    s = rig.last().axes[0].series[0]
    assert s.y[0] == pytest.approx(3)
    rig.run("t = 0:0.01:5; lsim(tf(1, [1 1]), t, t);")
    u, y = rig.last().axes[0].series
    assert rig.last().axes[0].title == "Linear Simulation Results"
    assert np.max(np.abs(y.y - (y.x - 1 + np.exp(-y.x)))) < 1e-3 and u.color == "#a0a0a0"


def test_discrete_response_is_drawn_as_steps(rig):
    rig.run("step(c2d(tf(1, [1 1]), 0.5), 2);")
    s = rig.last().axes[0].series[0]
    assert np.any(np.diff(s.x) == 0)  # vertical risers of the staircase


def test_bode_two_axes_db_and_log(rig):
    rig.run("bode(tf(1, [1 1]), [0.1 1 10]);")
    mag_ax, ph_ax = rig.last().axes
    assert mag_ax.xscale == "log" and mag_ax.ylabel == "Magnitude (dB)"
    assert mag_ax.series[0].y == pytest.approx(-10 * np.log10(1 + np.array([0.01, 1, 100])))
    assert ph_ax.series[0].y == pytest.approx(-np.degrees(np.arctan([0.1, 1, 10])))
    ws = rig.run("[m, p, w] = bode(tf(1, [1 1]), [1 2]);")
    assert ws["m"][0, 0] == pytest.approx(1 / math.sqrt(2))


def test_margin_plot_marks_crossovers(rig):
    rig.run("margin(tf(10, [1 3 3 1]));")
    mag_ax, _ = rig.last().axes
    lines = [s for s in mag_ax.series if s.kind == "xline"]
    assert sorted(float(s.x[0]) for s in lines) == pytest.approx(
        sorted([math.sqrt(3), lti.margin(lti.tf([10], [1, 3, 3, 1]))[3]]), rel=1e-4)
    assert "Gm = -1.94 dB" in mag_ax.title
    ws = rig.run("[gm, pm] = margin(tf(1, [1 1 0]));")
    assert math.isinf(ws["gm"].item())


def test_nyquist_rlocus_pzmap(rig):
    rig.run("nyquist(tf(1, [1 1]));")
    ax = rig.last().axes[0]
    assert ax.title == "Nyquist Diagram" and ax.series[-1].x.tolist() == [-1.0]
    rig.run("rlocus(tf(1, [1 3 2]));")
    ax = rig.last().axes[0]
    branches = [s for s in ax.series if s.kind == "line"]
    assert len(branches) == 2 and ax.title == "Root Locus"
    rig.run("pzmap(tf([1 3], [1 3 2]));")
    poles, zeros = rig.last().axes[0].series
    assert sorted(poles.x.tolist()) == pytest.approx([-2, -1]) and zeros.x.tolist() == [-3]
    ws = rig.run("[p, z] = pzmap(tf([1 3], [1 3 2]));")
    assert ws["z"].ravel().real.tolist() == pytest.approx([-3])


@pytest.mark.parametrize("code, text", [
    ("step(5)", "must be a system"),
    ("initial(tf(1, [1 1]), 1)", "state-space"),
    ("lsim(tf(1, [1 1]), [1 2])", "lsim\\(sys, u, t\\)"),
    ("bode(tf(1, [1 1]), [-1 2])", "positive"),
])
def test_errors(rig, code, text):
    with pytest.raises(EngStudioError, match=text):
        rig.run(code)
