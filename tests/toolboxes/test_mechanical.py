"""Mechanical Engineering toolbox: every result against a textbook formula or worked example."""

import math

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics, ToolboxList
from engstudio.core.errors import EngStudioError
from engstudio.toolboxes import mechanical as me

E, I_ = 200e9, 8e-6


# ------------------------------------------------------------------- sections and stress
def test_sections():
    r = me.section_rect(0.1, 0.2)
    assert (r.A, r.Ix, r.Iy) == pytest.approx((0.02, 0.1 * 0.2 ** 3 / 12, 0.2 * 0.1 ** 3 / 12))
    assert r.Sx == pytest.approx(r.Ix / 0.1) and r.c == 0.1
    c = me.section_circle(0.05)
    assert c.Ix == pytest.approx(math.pi * 0.05 ** 4 / 64) and c.J == pytest.approx(2 * c.Ix)
    t = me.section_tube(0.05, 0.04)
    assert t.A == pytest.approx(math.pi * (0.05 ** 2 - 0.04 ** 2) / 4)
    ib = me.section_ibeam(0.1, 0.01, 0.2, 0.006)
    assert ib.Ix == pytest.approx((0.1 * 0.2 ** 3 - 0.094 * 0.18 ** 3) / 12)
    sq = me.section_rect(0.1, 0.1)
    assert sq.J == pytest.approx(0.1406 * 0.1 ** 4, rel=2e-3)  # square: 0.1406 a^4


def test_stress_formulas():
    assert me.stress_axial(1000, 0.01) == 1e5
    assert me.stress_bending(500, 0.05, 1e-6) == pytest.approx(2.5e7)
    assert me.stress_torsion(100, 0.01, 1e-8) == pytest.approx(1e8)
    assert me.safety_factor(100e6, 250e6) == 2.5
    assert me.buckling_euler(E, I_, 2, 0.5) == pytest.approx(math.pi ** 2 * E * I_ / 1.0)


def test_mohr_and_von_mises():
    m = me.mohr(80e6, -40e6, 25e6)
    assert m.center == pytest.approx(20e6) and m.radius == pytest.approx(65e6)
    assert (m.s1, m.s2, m.tau_max) == pytest.approx((85e6, -45e6, 65e6))
    assert m.theta_p == pytest.approx(0.5 * math.degrees(math.atan2(50, 120)))
    assert me.von_mises(100e6) == pytest.approx(100e6)  # uniaxial
    assert me.von_mises(0, 0, 50e6) == pytest.approx(math.sqrt(3) * 50e6)  # pure shear
    assert me.von_mises(80e6, -40e6, 25e6) == pytest.approx(
        math.sqrt(85e6 ** 2 - 85e6 * -45e6 + 45e6 ** 2))


# --------------------------------------------------------------------------------- beams
def test_simply_supported_center_load():
    P, L = 1000.0, 2.0
    r = me.beam(L, E, I_, "simply", [P], [L / 2])
    assert r.max_deflection == pytest.approx(-P * L ** 3 / (48 * E * I_), rel=1e-5)
    assert r.x_max_deflection == pytest.approx(L / 2)
    assert r.max_moment == pytest.approx(P * L / 4) and r.reactions == pytest.approx([P / 2] * 2)
    assert r.slope[0] == pytest.approx(-P * L ** 2 / (16 * E * I_), rel=1e-4)


def test_simply_supported_udl_and_offset_load():
    w, L = 500.0, 3.0
    r = me.beam(L, E, I_, "simply", None, None, w)
    assert r.max_deflection == pytest.approx(-5 * w * L ** 4 / (384 * E * I_), rel=1e-5)
    assert r.max_moment == pytest.approx(w * L ** 2 / 8)
    P, a = 2000.0, 1.0
    r2 = me.beam(L, E, I_, "simply", [P], [a])
    b = L - a
    assert r2.reactions == pytest.approx([P * b / L, P * a / L])
    y_at_a = r2.deflection[np.argmin(np.abs(r2.x - a))]
    assert y_at_a == pytest.approx(-P * a ** 2 * b ** 2 / (3 * E * I_ * L), rel=1e-5)


def test_cantilever():
    P, L, w = 800.0, 1.5, 300.0
    r = me.beam(L, E, I_, "cantilever", [P], [L])
    assert r.deflection[-1] == pytest.approx(-P * L ** 3 / (3 * E * I_), rel=1e-5)
    assert r.reactions == pytest.approx([P, -P * L]) and r.M[-1] == pytest.approx(0, abs=1e-9)
    ru = me.beam(L, E, I_, "cantilever", None, None, w)
    assert ru.deflection[-1] == pytest.approx(-w * L ** 4 / (8 * E * I_), rel=1e-5)


# ---------------------------------------------------------------------------- vibrations
def test_sdof_properties_and_regimes():
    p = me.sdof(2, 4, 800)
    assert (p.wn, p.zeta, p.ccr) == pytest.approx((20, 0.05, 80))
    assert p.wd == pytest.approx(20 * math.sqrt(1 - 0.0025)) and p.regime == "underdamped"
    assert me.sdof(1, 0, 4).regime == "undamped"
    assert me.sdof(1, 4, 4).regime == "critically damped" and me.sdof(1, 10, 4).wd == 0


@pytest.mark.parametrize("c", [0.0, 2.0, 20.0, 40.0])  # undamped, under, critical, over
def test_sdof_free_satisfies_the_ode(c):
    m, k, x0, v0 = 1.0, 100.0, 0.02, -0.3
    t = np.linspace(0, 2, 20001)
    x, v = me.sdof_free(m, c, k, x0, v0, t)
    assert (x[0], v[0]) == pytest.approx((x0, v0))
    assert np.max(np.abs(np.gradient(x, t) - v)) < 1e-3
    a = np.gradient(v, t)
    assert np.max(np.abs(m * a[5:-5] + c * v[5:-5] + k * x[5:-5])) < 2e-3


def test_forced_response_and_transmissibility():
    f = me.sdof_forced(1, 2, 100, 10, 10)  # at resonance, zeta = 0.1
    assert f.r == 1 and f.MF == pytest.approx(5) and f.phase == pytest.approx(90)
    assert f.X == pytest.approx(0.5)
    assert me.transmissibility(0.0, 2.0) == pytest.approx(1 / 3)
    assert me.transmissibility(0.3, math.sqrt(2)) == pytest.approx(1.0)  # crossover at sqrt(2)
    assert me.transmissibility(0.1, np.array([0.0, 1.0])).tolist() == pytest.approx(
        [1.0, math.sqrt(1.04) / 0.2])
    with pytest.raises(EngStudioError, match="resonance"):
        me.sdof_forced(1, 0, 100, 1, 10)


def test_log_decrement():
    zeta = 0.05
    delta = 2 * math.pi * zeta / math.sqrt(1 - zeta ** 2)
    d = me.log_decrement(1.0, math.exp(-3 * delta), 3)
    assert d.delta == pytest.approx(delta) and d.zeta == pytest.approx(zeta)


def test_modes_two_dof_and_rigid_body():
    m = me.modes(np.array([[2.0, 0], [0, 1]]), np.array([[600.0, -200], [-200, 200]]))
    assert m.wn == pytest.approx([10, 20])
    phi = m.shapes_mass
    assert phi.T @ np.diag([2.0, 1]) @ phi == pytest.approx(np.eye(2))
    assert np.max(np.abs(m.shapes), axis=0) == pytest.approx([1, 1])
    free = me.modes(np.eye(2), np.array([[1.0, -1], [-1, 1]]))  # free-free: rigid mode
    assert free.wn == pytest.approx([0, math.sqrt(2)])


# ---------------------------------------------------------------------- machine elements
def test_spring_gear_shaft():
    s = me.spring_helical(0.004, 0.032, 10, 79.3e9, 100)
    assert s.k == pytest.approx(79.3e9 * 0.004 ** 4 / (8 * 0.032 ** 3 * 10))
    assert s.C == 8 and s.Kw == pytest.approx((31 / 28) + 0.615 / 8)
    assert s.deflection == pytest.approx(100 / s.k)
    g = me.gear_pair(20, 60, 0.002, 300, 10)
    assert (g.ratio, g.d1, g.d2, g.center_distance, g.w2, g.T2) == pytest.approx(
        (3, 0.04, 0.12, 0.08, 100, 30))
    assert me.shaft_power(100, 1500) == pytest.approx(100 * 50 * math.pi)
    d = me.shaft_diameter(500, 40e6)
    assert me.stress_torsion(500, d / 2, math.pi * d ** 4 / 32) == pytest.approx(40e6)


def test_fourbar_norton_example():
    r = me.fourbar(2, 7, 9, 6, 30, 10)  # Norton, Design of Machinery, Example 4-1/6-1
    assert (r.theta3, r.theta4) == pytest.approx((88.84, 117.29), abs=0.01)
    assert r.grashof == "crank-rocker"
    # velocity closure: a w2 e^{i t2} + b w3 e^{i t3} - c w4 e^{i t4} = 0
    t2, t3, t4 = (math.radians(v) for v in (30, r.theta3, r.theta4))
    vx = -2 * 10 * math.sin(t2) - 7 * r.omega3 * math.sin(t3) + 9 * r.omega4 * math.sin(t4)
    vy = 2 * 10 * math.cos(t2) + 7 * r.omega3 * math.cos(t3) - 9 * r.omega4 * math.cos(t4)
    assert (vx, vy) == pytest.approx((0, 0), abs=1e-9)
    assert me.fourbar(2, 7, 9, 6, 30, branch="crossed").theta4 != r.theta4
    assert me.fourbar(5, 5, 5, 5, 10).grashof == "change-point"
    with pytest.raises(EngStudioError, match="cannot be assembled"):
        me.fourbar(1, 1, 1, 10, 0)


@pytest.mark.parametrize("call, text", [
    (lambda: me.sdof(-1, 0, 1), "> 0"),
    (lambda: me.section_tube(0.02, 0.03), "inner"),
    (lambda: me.beam(2, E, I_, "fixed"), "must be one of"),
    (lambda: me.beam(2, E, I_, "simply", [1, 2], [1]), "same number"),
    (lambda: me.beam(2, E, I_, "simply", [1], [3]), "on the beam"),
    (lambda: me.modes(np.eye(2), np.array([[1.0, 2], [0, 1]])), "symmetric"),
    (lambda: me.log_decrement(1, 2), "0 < xn < x1"),
])
def test_validation(call, text):
    with pytest.raises(EngStudioError, match=text):
        call()


# --------------------------------------------------------------- from scripts (kernel)
def test_toolbox_in_the_kernel():
    k = InProcessKernelClient(threaded=False)
    events = []
    k.subscribe(events.append)
    k.execute("p = sdof(2, 4, 800); w = p.wn; r = beam(2, 200e9, 8e-6, 'simply', 1000, 1);"
              " [x, v] = sdof_free(1, 0, 100, 0.01, 0, [0 0.1]); m = modes([2 0; 0 1],"
              " [600 -200; -200 200]); s = m.regime;", None)
    errors = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
    ws = k._interp.workspace
    assert ws["w"].item() == pytest.approx(20) and ws["x"].shape == (1, 2)
    assert errors and "regime" in errors[0]  # modes has no 'regime' field: a normal error
    assert ws["r"].get("max_moment").item() == pytest.approx(500)
    k.list_toolboxes()
    listing = [e for e in events if isinstance(e, ToolboxList)][-1]
    names = {b.display_name: {f.name for f in b.functions} for b in listing.toolboxes}
    assert {"beam", "sdof", "modes", "fourbar"} <= names["Mechanical Engineering"]
    k.shutdown()
