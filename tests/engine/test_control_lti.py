"""control.lti (Phase 6, C1): every result checked against analytic values."""

import math
import pickle

import numpy as np
import pytest

from engstudio.control import lti
from engstudio.core.errors import DimensionError, EngStudioError, ValidationError


def first_order():
    return lti.tf([1], [1, 1])  # 1/(s+1)


def second_order(wn=2.0, zeta=0.3):
    return lti.tf([wn ** 2], [1, 2 * zeta * wn, wn ** 2])


def test_tf_trims_and_is_immutable():
    g = lti.tf([0, 0, 2], [1, 3])
    assert g.data[0].tolist() == [2] and g.order == 1
    with pytest.raises(ValueError):
        g.data[0][0] = 5


def test_forms_convert_round_trip():
    g = second_order()
    z = lti.to_zpk(g)
    s = lti.to_ss(g)
    assert z.form == "zpk" and z.data[2] == pytest.approx(4.0)
    assert sorted(np.abs(lti.poles(z))) == pytest.approx([2, 2])
    back = lti.to_tf(s)
    assert back.data[1] / back.data[1][0] == pytest.approx([1, 1.2, 4])
    assert back.data[0][-1] / back.data[1][0] == pytest.approx(4)


def test_poles_zeros_dcgain():
    g = lti.tf([1, 3], [1, 3, 2])  # (s+3)/((s+1)(s+2))
    assert sorted(lti.poles(g).real) == pytest.approx([-2, -1])
    assert lti.zeros(g).tolist() == pytest.approx([-3])
    assert lti.dcgain(g) == pytest.approx(1.5)


def test_series_parallel_feedback():
    g = first_order()
    cl = lti.feedback(g)  # 1/(s+2)
    assert cl.data[0] / cl.data[1][0] == pytest.approx([1])
    assert cl.data[1] / cl.data[1][0] == pytest.approx([1, 2])
    s = lti.series(g, lti.tf([2], [1, 0]))
    assert lti.to_tf(s).data[1].tolist() == pytest.approx([1, 1, 0])
    p = lti.parallel(g, 1.0)  # (s+2)/(s+1)
    assert lti.dcgain(p) == pytest.approx(2)
    pos = lti.feedback(g, 0.5, sign=+1)  # 1/(s + 0.5)
    assert lti.dcgain(pos) == pytest.approx(2)


def test_form_precedence():
    g = first_order()
    assert lti.series(g, lti.to_zpk(g)).form == "zpk"
    assert lti.series(lti.to_ss(g), g).form == "ss"


def test_damp_second_order():
    wn, zeta, p = lti.damp(second_order(2.0, 0.3))
    assert wn == pytest.approx([2, 2]) and zeta == pytest.approx([0.3, 0.3])


def test_stability():
    assert lti.is_stable(first_order())
    assert not lti.is_stable(lti.tf([1], [1, -1]))
    assert not lti.is_stable(lti.tf([1], [1, 0, 1]))  # marginal: not asymptotically stable
    assert lti.is_stable(lti.tf([1], [1, -0.5], dt=0.1))


def test_step_first_order_matches_exact():
    t, y = lti.step(first_order(), 5)
    assert t[-1] == pytest.approx(5)
    assert np.max(np.abs(y - (1 - np.exp(-t)))) < 1e-6


def test_impulse_and_initial():
    t, y = lti.impulse(first_order(), np.linspace(0, 3, 301))
    assert np.max(np.abs(y - np.exp(-t))) < 1e-6
    sys = lti.ss([[-2]], [[1]], [[1]], [[0]])
    t, y = lti.initial(sys, [3], np.linspace(0, 1, 101))
    assert np.max(np.abs(y - 3 * np.exp(-2 * t))) < 1e-6


def test_lsim_ramp():
    t = np.linspace(0, 5, 501)
    _, y = lti.lsim(first_order(), t, t)  # ramp in -> t - 1 + e^-t
    assert np.max(np.abs(y - (t - 1 + np.exp(-t)))) < 1e-3


def test_default_final_time_covers_settling():
    t, y = lti.step(lti.tf([1], [1, 0.1]))
    assert y[-1] == pytest.approx(10, rel=0.01)


def test_stepinfo_second_order():
    zeta, wn = 0.3, 2.0
    info = lti.stepinfo(second_order(wn, zeta))
    os_exact = 100 * math.exp(-zeta * math.pi / math.sqrt(1 - zeta ** 2))
    tp_exact = math.pi / (wn * math.sqrt(1 - zeta ** 2))
    assert info.overshoot == pytest.approx(os_exact, rel=1e-3)
    assert info.peak_time == pytest.approx(tp_exact, rel=1e-3)
    assert info.peak == pytest.approx(1 + os_exact / 100, rel=1e-3)
    assert 0 < info.rise_time < info.peak_time < info.settling_time


def test_stepinfo_first_order_rise_and_settling():
    info = lti.stepinfo(first_order())
    assert info.rise_time == pytest.approx(math.log(9), rel=1e-3)  # 10%->90%
    assert info.settling_time == pytest.approx(-math.log(0.02), rel=1e-3)
    assert info.overshoot == 0


def test_bode_first_order():
    mag, phase, w = lti.bode(first_order(), [0.1, 1, 10])
    assert mag == pytest.approx(1 / np.sqrt(1 + np.array([0.01, 1, 100])))
    assert phase == pytest.approx(-np.degrees(np.arctan([0.1, 1, 10])))


def test_nyquist_points():
    re, im, _ = lti.nyquist(first_order(), [1.0])
    assert (re[0], im[0]) == pytest.approx((0.5, -0.5))


def test_margin_third_order():
    gm, pm, wcg, wcp = lti.margin(lti.tf([10], [1, 3, 3, 1]))  # 10/(s+1)^3
    assert wcg == pytest.approx(math.sqrt(3), rel=1e-4) and gm == pytest.approx(0.8, rel=1e-4)
    assert pm < 0  # unstable closed loop
    gm2, pm2, _, wcp2 = lti.margin(lti.tf([1], [1, 1, 0]))  # 1/(s(s+1))
    assert math.isinf(gm2)
    assert pm2 == pytest.approx(51.8273, rel=1e-3)


def test_c2d_zoh_first_order():
    ts = 0.1
    d = lti.c2d(first_order(), ts)
    a = math.exp(-ts)
    assert d.dt == ts
    assert d.data[0] / d.data[1][0] == pytest.approx([1 - a])
    assert d.data[1] / d.data[1][0] == pytest.approx([1, -a])
    t, y = lti.step(d, 1.0)
    assert y[-1] == pytest.approx(1 - math.exp(-1.0), rel=1e-9)


def test_rlocus_roots_satisfy_characteristic_equation():
    g = lti.tf([1], [1, 3, 2])
    roots, k = lti.rlocus(g, [0, 1, 10])
    for row, kk in zip(roots, k, strict=True):
        assert np.allclose(np.sort_complex(row), np.sort_complex(np.roots([1, 3, 2 + kk])))


def test_pid_forms():
    c = lti.pid(1, 2, 3)  # (3 s^2 + s + 2)/s
    assert c.data[0].tolist() == [3, 1, 2] and c.data[1].tolist() == [1, 0]
    assert lti.pid(2).data[0].tolist() == [2]
    assert lti.pid(1, 2).data[0].tolist() == [1, 2]
    f = lti.pid(1, 0, 1, 0.1)  # 1 + s/(0.1 s + 1) = (1.1 s + 1)/(0.1 s + 1)
    assert f.data[0].tolist() == pytest.approx([1.1, 1]) and f.data[1].tolist() == [0.1, 1]
    s = lti.pidstd(2, 4, 0.5)  # Kp=2, Ki=0.5, Kd=1
    assert s.data[0].tolist() == pytest.approx([1, 2, 0.5])


@pytest.mark.parametrize("kind", ["PI", "PID"])
def test_pidtune_gives_stable_loop_with_target_margin(kind):
    plant = lti.tf([1], [1, 3, 3, 1])  # (s+1)^-3
    ctrl, info = lti.pidtune(plant, kind)
    loop = lti.series(ctrl, plant)
    assert lti.is_stable(lti.feedback(loop))
    gm, pm, _, wcp = lti.margin(loop)
    assert pm == pytest.approx(60, abs=8)
    assert wcp == pytest.approx(info.crossover, rel=0.05)
    assert gm >= 1.9


def test_pidtune_fixed_crossover():
    plant = lti.tf([1], [1, 1, 0])
    ctrl, info = lti.pidtune(plant, "PD", wc=2.0)
    _, pm, _, wcp = lti.margin(lti.series(ctrl, plant))
    assert wcp == pytest.approx(2.0, rel=0.05) and pm == pytest.approx(60, abs=8)


def test_pickle_round_trip():
    g = lti.to_ss(second_order())
    h = pickle.loads(pickle.dumps(g))
    assert h.form == "ss" and np.array_equal(h.data[0], g.data[0])


@pytest.mark.parametrize("call, err", [
    (lambda: lti.tf([1], [0, 0]), ValidationError),
    (lambda: lti.tf([1], [1, np.inf]), ValidationError),
    (lambda: lti.ss([[1, 2]], [[1]], [[1]], [[0]]), DimensionError),
    (lambda: lti.zpk([1j], [-1, -2], 1), ValidationError),
    (lambda: lti.c2d(lti.c2d(first_order(), 0.1), 0.1), ValidationError),
    (lambda: lti.c2d(first_order(), 0.1, "bogus"), ValidationError),
    (lambda: lti.pidtune(first_order(), "PIDF2"), ValidationError),
    (lambda: lti.lsim(first_order(), [1, 2], [0, 1, 2]), DimensionError),
    (lambda: lti.series(first_order(), lti.tf([1], [1, 1], dt=0.1)), ValidationError),
])
def test_errors(call, err):
    with pytest.raises(err):
        call()


def test_mimo_ss_limits():
    m = lti.ss(np.eye(2) * -1, np.eye(2), np.eye(2), np.zeros((2, 2)))
    assert m.shape == (2, 2) and np.allclose(lti.dcgain(m), np.eye(2))
    with pytest.raises(EngStudioError, match="single-input"):
        lti.step(m)
