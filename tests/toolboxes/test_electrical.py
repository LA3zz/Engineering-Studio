"""Electrical and electronics toolbox against hand calculations."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.toolboxes.electrical import functions as el


def test_networks_and_divider():
    assert el.resistors(np.array([100.0, 200, 300])) == 600
    assert el.resistors(np.array([100.0, 100]), "parallel") == pytest.approx(50)
    assert el.voltage_divider(10, 1000, 1000) == pytest.approx(5)
    assert el.voltage_divider(10, 1000, 1000, 1000) == pytest.approx(10 / 3)


def test_rlc_parameters():
    s = el.rlc(10, 0.1, 1e-4)
    assert s.wn == pytest.approx(1 / math.sqrt(1e-5)) and s.zeta == pytest.approx(
        5 * math.sqrt(1e-3))
    assert s.Q == pytest.approx(1 / (2 * s.zeta)) and s.response == "underdamped"
    assert el.rlc(2 * math.sqrt(0.1 / 1e-4), 0.1, 1e-4).response == "critically damped"
    p = el.rlc(100, 0.1, 1e-4, "parallel")
    assert p.zeta == pytest.approx(1 / 200 * math.sqrt(1e3))


def test_transients():
    t = np.array([0.0, 1e-3, 1.0])
    vc, i = el.rc_step(1000, 1e-6, 5, t)
    assert vc[0] == 0 and vc[1] == pytest.approx(5 * (1 - math.exp(-1)))
    assert vc[-1] == pytest.approx(5) and i[0] == pytest.approx(5e-3)
    il, vl = el.rl_step(10, 0.1, 20, t)
    assert il[-1] == pytest.approx(2) and vl[0] == 20


def test_ac_impedance_and_power():
    zl = el.impedance("L", 0.1, 50)
    assert zl == pytest.approx(complex(0, 2 * math.pi * 5))
    assert el.impedance("C", 1e-6, 1000) == pytest.approx(complex(0, -1 / (2 * math.pi * 1e-3)))
    pw = el.ac_power(230, complex(30, 40))
    assert pw.S == pytest.approx(230 ** 2 / 50) and pw.pf == pytest.approx(0.6)
    assert pw.P == pytest.approx(pw.S * 0.6) and pw.Q == pytest.approx(pw.S * 0.8)
    P, Q, S = el.three_phase_power(400, 10, 0.8)
    assert S == pytest.approx(math.sqrt(3) * 4000) and P == pytest.approx(0.8 * S)


def test_electronics():
    assert el.opamp_gain("inverting", 10e3, 1e3) == -10
    assert el.opamp_gain("noninverting", 9e3, 1e3) == 10
    assert el.opamp_gain("follower") == 1
    with pytest.raises(EngStudioError, match="needs Rf and Rin"):
        el.opamp_gain("inverting")
    fc, H = el.rc_filter(1e3, 1e-6)
    assert fc == pytest.approx(159.15494, rel=1e-6) and abs(H[0]) == pytest.approx(
        1 / math.sqrt(2))
    _, Hh = el.rc_filter(1e3, 1e-6, "highpass", np.array([1e6]))
    assert abs(Hh[0]) == pytest.approx(1, abs=1e-3)
    i = el.diode_current(0.6)
    assert i == pytest.approx(1e-14 * math.expm1(0.6 / (1.380649e-23 * 300 / 1.602176634e-19)))
    tm = el.timer555(1e3, 10e3, 1e-6)
    assert tm.f == pytest.approx(1 / (math.log(2) * 21e3 * 1e-6)) and tm.duty == pytest.approx(
        11 / 21)
