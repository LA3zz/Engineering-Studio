"""Robotics and aerospace toolboxes against closed forms and standard tables."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.toolboxes.aero import functions as ae
from engstudio.toolboxes.robotics import functions as rb


# ------------------------------------------------------------------------------ robotics
def test_rotations_and_transform():
    R = rb.rotz(90)
    assert R @ np.array([1, 0, 0]) == pytest.approx([0, 1, 0])
    assert rb.rotx(30) @ rb.rotx(-30) == pytest.approx(np.eye(3))
    assert np.linalg.det(rb.roty(37)) == pytest.approx(1)
    T = rb.transform(R, np.array([1, 2, 3]))
    assert T @ np.array([1, 0, 0, 1]) == pytest.approx([1, 3, 3, 1])


def test_fkine_matches_planar_arm():
    L, q = np.array([1.0, 0.5]), np.array([0.3, 0.7])
    tab = np.array([[1.0, 0, 0, 0], [0.5, 0, 0, 0]])
    fk = rb.fkine(tab, q)
    x, y, J = rb.planar_arm(L, q)
    assert fk.position[:2] == pytest.approx([x[-1], y[-1]])
    assert fk.joints.shape == (3, 3) and fk.euler_zyx[0] == pytest.approx(math.degrees(1.0))
    # Jacobian against a finite difference
    h = 1e-7
    for i in range(2):
        dq = q.copy()
        dq[i] += h
        x2, y2, _ = rb.planar_arm(L, dq)
        assert J[:, i] == pytest.approx([(x2[-1] - x[-1]) / h, (y2[-1] - y[-1]) / h], rel=1e-5)
    prism = rb.fkine(np.array([[0.0, 0, 1, 0]]), np.array([0.5]), np.array([1.0]))
    assert prism.position == pytest.approx([0, 0, 1.5])


def test_ik_2link_roundtrip_and_reach():
    for elbow in ("up", "down"):
        q1, q2 = rb.ik_2link(1, 0.8, 1.2, 0.6, elbow)
        x, y, _ = rb.planar_arm(np.array([1, 0.8]), np.array([q1, q2]))
        assert (x[-1], y[-1]) == pytest.approx((1.2, 0.6))
    with pytest.raises(EngStudioError, match="out of reach"):
        rb.ik_2link(1, 1, 3, 0)


def test_trajectories():
    t = np.linspace(0, 2, 201)
    for kind in ("cubic", "quintic", "trapezoid"):
        q, qd, _ = rb.trajectory(0, 1, 2, t, kind)
        assert q[0] == pytest.approx(0) and q[-1] == pytest.approx(1)
        assert qd[0] == pytest.approx(0, abs=1e-9) and qd[-1] == pytest.approx(0, abs=1e-9)
        assert np.trapezoid(qd, t) == pytest.approx(1, rel=1e-3)
    _, _, a = rb.trajectory(0, 1, 2, t, "quintic")
    assert a[0] == pytest.approx(0) and a[-1] == pytest.approx(0, abs=1e-9)
    with pytest.raises(EngStudioError, match="v_max"):
        rb.trajectory(0, 1, 2, t, "trapezoid", 5)


# ------------------------------------------------------------------------------ aerospace
def test_isa_table_values():
    T, a, p, rho = ae.atmosisa(0)
    assert (T, p, rho) == pytest.approx((288.15, 101325, 1.225), rel=1e-4)
    assert a == pytest.approx(340.294, rel=1e-4)
    T, a, p, rho = ae.atmosisa(np.array([11000.0, 20000, 32000]))
    assert T == pytest.approx([216.65, 216.65, 228.65])
    assert p == pytest.approx([22632, 5474.9, 868.02], rel=1e-3)
    assert rho[0] == pytest.approx(0.36392, rel=1e-3)


def test_airspeed_lift_drag_stall():
    s = ae.airspeed(340.294)
    assert s.mach == pytest.approx(1, rel=1e-4) and s.p0 / 101325 == pytest.approx(1.8929,
                                                                                    rel=1e-3)
    L, D, cd = ae.lift_drag(50, 16, 0.5, 0.025, 8, 0.8)
    assert cd == pytest.approx(0.025 + 0.25 / (math.pi * 6.4))
    assert L / D == pytest.approx(0.5 / cd)
    assert ae.stall_speed(10e3, 16, 1.5) == pytest.approx(math.sqrt(2e4 / (1.225 * 24)))


def test_range_rocket_orbits():
    r = ae.breguet("jet-range", 15, 70e3, 55e3, 1.6e-4, 230)
    assert r == pytest.approx(230 / 1.6e-4 * 15 * math.log(70 / 55))
    assert ae.rocket_dv(300, 100, 50) == pytest.approx(300 * 9.80665 * math.log(2))
    o = ae.orbit(400e3)
    assert o.v_circular == pytest.approx(7669, rel=1e-3) and o.period / 60 == pytest.approx(
        92.4, rel=2e-3)
    h = ae.hohmann(6678e3, 42164e3)  # LEO -> GEO
    assert h.dv_total == pytest.approx(3893, rel=2e-3)
    assert h.transfer_time / 3600 == pytest.approx(5.29, rel=5e-3)
    with pytest.raises(EngStudioError, match="below W0"):
        ae.breguet("jet-endurance", 15, 50, 60, 1e-4)
