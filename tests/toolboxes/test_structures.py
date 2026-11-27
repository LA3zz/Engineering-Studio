"""2-D FEA (truss, frame, plane-stress plate) against closed-form results."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.toolboxes.structures import functions as st

E, A = 200e9, 1e-3


def test_two_bar_truss_statics():
    # symmetric V: supports at (0,0), (2,0), apex (1,1) loaded with 10 kN down
    nodes = np.array([[0.0, 0], [2, 0], [1, 1]])
    el = np.array([[1, 3], [2, 3]])
    sup = np.array([[1, 1, 1], [2, 1, 1]])
    r = st.truss2d(nodes, el, E, A, sup, np.array([[3, 0, -10e3]]))
    assert r.N == pytest.approx([-10e3 / math.sqrt(2)] * 2)  # both in compression
    assert r.reactions[:2, 1] == pytest.approx([5e3, 5e3])
    assert r.reactions[:2, 0] == pytest.approx([5e3, -5e3])
    L = math.sqrt(2)
    # apex drop: each bar shortens N L / EA; geometry: dv = dL / sin45
    assert r.u[2, 1] == pytest.approx(-(10e3 / math.sqrt(2)) * L / (E * A) * math.sqrt(2))


def test_truss_mechanism_detected():
    nodes = np.array([[0.0, 0], [1, 0]])
    with pytest.raises(EngStudioError, match="mechanism"):
        st.truss2d(nodes, np.array([[1, 2]]), E, A, np.array([[1, 1, 1]]),
                   np.array([[2, 0, -1]]))


def test_cantilever_frame_tip_load():
    I_, L, P = 8e-6, 2.0, 1000.0
    nodes = np.array([[0.0, 0], [1, 0], [2, 0]])
    r = st.frame2d(nodes, np.array([[1, 2], [2, 3]]), E, A, I_, np.array([[1, 1, 1, 1]]),
                   np.array([[3, 0, -P, 0]]))
    assert r.u[2, 1] == pytest.approx(-P * L ** 3 / (3 * E * I_))
    assert r.u[2, 2] == pytest.approx(-P * L ** 2 / (2 * E * I_))
    assert r.M[0, 0] == pytest.approx(-P * L) and r.M[1, 1] == pytest.approx(0, abs=1e-6)
    assert r.reactions[0] == pytest.approx([0, P, P * L])
    assert r.V[0] == pytest.approx([P, P])


def test_fixed_beam_udl_and_portal_frame():
    I_, L, w = 8e-6, 4.0, -2000.0
    nodes = np.array([[0.0, 0], [2, 0], [4, 0]])
    sup = np.array([[1, 1, 1, 1], [3, 1, 1, 1]])
    r = st.frame2d(nodes, np.array([[1, 2], [2, 3]]), E, A, I_, sup, None, w)
    assert r.u[1, 1] == pytest.approx(w * L ** 4 / (384 * E * I_))
    assert r.M[0, 0] == pytest.approx(w * L ** 2 / 12)  # hogging at the walls (w < 0)
    assert r.M[0, 1] == pytest.approx(-w * L ** 2 / 24)  # sagging at mid-span
    # portal frame with a sway load: horizontal reactions balance the load
    pn = np.array([[0.0, 0], [0, 3], [4, 3], [4, 0]])
    pr = st.frame2d(pn, np.array([[1, 2], [2, 3], [3, 4]]), E, A, I_,
                    np.array([[1, 1, 1, 1], [4, 1, 1, 1]]), np.array([[2, 5e3, 0, 0]]))
    assert pr.reactions[[0, 3], 0].sum() == pytest.approx(-5e3)
    assert pr.u[1, 0] > 0 and pr.u[2, 0] == pytest.approx(pr.u[1, 0], rel=0.05)


def test_plate_uniform_tension_is_exact():
    tx = 50e6
    r = st.plate2d(0.2, 0.1, 0.01, E, 0.3, 8, 4, "left-roller", "right", np.array([tx, 0]))
    assert np.allclose(r.sx, tx, rtol=1e-8) and np.allclose(r.sy, 0, atol=1e-3 * tx)
    assert r.ux[:, -1] == pytest.approx(np.full(5, tx * 0.2 / E))
    assert r.uy[-1, 0] == pytest.approx(-0.3 * tx / E * 0.1)
    assert r.X.shape == (5, 9) and r.max_von_mises == pytest.approx(tx)


def test_plate_hole_concentrates_stress():
    tx = 10e6
    r = st.plate2d(0.4, 0.2, 0.005, E, 0.3, 60, 30, "left-roller", "right",
                   np.array([tx, 0]), 0.02)
    assert np.isnan(r.sx[15, 30])  # node at the hole centre
    assert 2.0 < r.max_von_mises / tx < 3.6  # Kirsch: Kt ~ 3 (finite width, coarse mesh)


def test_plate_validation():
    with pytest.raises(EngStudioError, match="loaded edge"):
        st.plate2d(1, 1, 0.01, E, 0.3, 2, 2, "left", "left", np.array([1.0, 0]))
