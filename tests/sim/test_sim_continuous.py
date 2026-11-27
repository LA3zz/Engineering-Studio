"""Continuous blocks (Phase 7, S4): realisations and responses against analytic solutions.
Blocks are integrated here directly with solve_ivp (the model runner comes in S6)."""

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

import engstudio.sim.blocks_continuous  # noqa: F401  (registers the blocks)
from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import block_type, feedthrough, resolve
from engstudio.sim.blocks_continuous import tf_to_ss
from engstudio.sim.model import Block


def impl_of(btype, **params):
    block = Block("b1", btype, params=params)
    return block_type(btype).impl(resolve(block)), block


def simulate(impl, u_of_t, t_end, n=201):
    """Integrate one block driven by u(t); returns t and the block output."""
    t_eval = np.linspace(0, t_end, n)

    def rhs(t, x):
        return impl.derivatives(t, x, [np.atleast_1d(u_of_t(t))])

    x0 = impl.initial_state()
    if x0.size:
        sol = solve_ivp(rhs, (0, t_end), x0, t_eval=t_eval, rtol=1e-10, atol=1e-12)
        xs = sol.y.T
    else:
        xs = np.zeros((n, 0))
    y = np.array([impl.outputs(t, x, [np.atleast_1d(u_of_t(t))])[0][0]
                  for t, x in zip(t_eval, xs, strict=True)])
    return t_eval, y


def test_integrator_ramp_and_initial_condition():
    impl, block = impl_of("Integrator", InitialCondition=2)
    t, y = simulate(impl, lambda t: 3.0, 2)
    assert np.max(np.abs(y - (2 + 3 * t))) < 1e-9
    assert not feedthrough(block)


def test_integrator_limits_hold():
    impl, _ = impl_of("Integrator", UpperLimit=1.0)
    t, y = simulate(impl, lambda t: 1.0, 3)
    assert y[-1] == pytest.approx(1.0) and np.max(y) <= 1.0 + 1e-9
    before = t < 1.0
    assert np.max(np.abs(y[before] - t[before])) < 1e-6  # unlimited ramp until it hits 1


@pytest.mark.parametrize("num, den", [([1], [1, 1]), ([2, 3], [1, 5, 6]), ([1, 0, 4], [2, 3, 1]),
                                      ([5], [1])])
def test_tf_realisation_matches_frequency_response(num, den):
    A, B, C, D = tf_to_ss(num, den)
    for w in (0.1, 1.0, 7.0):
        s = 1j * w
        h_ss = (C @ np.linalg.solve(s * np.eye(A.shape[0]) - A, B) + D)[0, 0] if A.size \
            else D[0, 0]
        assert h_ss == pytest.approx(np.polyval(num, s) / np.polyval(den, s))


def test_transfer_fcn_step_second_order():
    wn, z = 2.0, 0.3
    impl, block = impl_of("TransferFcn", Num=[wn ** 2], Den=[1, 2 * z * wn, wn ** 2])
    t, y = simulate(impl, lambda t: 1.0, 6)
    wd = wn * math.sqrt(1 - z ** 2)
    exact = 1 - np.exp(-z * wn * t) * (np.cos(wd * t) + z / math.sqrt(1 - z ** 2)
                                         * np.sin(wd * t))
    assert np.max(np.abs(y - exact)) < 1e-8
    assert not feedthrough(block)
    assert feedthrough(Block("b2", "TransferFcn", params={"Num": [1, 1], "Den": [1, 2]}))


def test_state_space_mass_spring_damper():
    m, c, k = 1.0, 0.4, 4.0
    impl, block = impl_of("StateSpace", A=[[0, 1], [-k / m, -c / m]], B=[[0], [1 / m]],
                          C=[[1, 0]], D=[[0]], X0=[0.1, 0])
    t, y = simulate(impl, lambda t: 0.0, 5)
    wn, z = 2.0, 0.1
    wd = wn * math.sqrt(1 - z ** 2)
    exact = 0.1 * np.exp(-z * wn * t) * (np.cos(wd * t) + z * wn / wd * np.sin(wd * t))
    assert np.max(np.abs(y - exact)) < 1e-8 and not feedthrough(block)


def test_derivative_approximates_du_dt():
    impl, block = impl_of("Derivative", Coefficient=1000)
    t, y = simulate(impl, lambda t: math.sin(t), 3, n=301)
    late = t > 0.05  # after the 1 ms filter transient
    assert np.max(np.abs(y[late] - np.cos(t[late]))) < 2e-3
    assert feedthrough(block)


@pytest.mark.parametrize("btype, params, text", [
    ("TransferFcn", {"Num": [1, 2, 3], "Den": [1, 1]}, "improper"),
    ("TransferFcn", {"Den": [0, 0]}, "denominator"),
    ("Integrator", {"LowerLimit": 2, "UpperLimit": 1}, "below"),
    ("StateSpace", {"A": [[1, 2]]}, "square"),
    ("StateSpace", {"B": [[1], [2]]}, "rows"),
    ("StateSpace", {"X0": [1, 2, 3]}, "X0"),
    ("Derivative", {"Coefficient": 0}, "positive"),
])
def test_bad_parameters(btype, params, text):
    with pytest.raises(ValidationError, match=text):
        resolve(Block("b1", btype, params=params))
