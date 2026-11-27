"""E9 tests: engine.ode against analytic solutions (reasoning in each docstring)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from scipy.linalg import expm

from engstudio.core.errors import ConvergenceError, DimensionError, ValidationError
from engstudio.engine.ode import METHODS, OdeResult, solve_ode

G = 9.80665  # standard gravity, m/s^2 (exact by definition)


# -- analytic solutions ---------------------------------------------------------------
@pytest.mark.parametrize("method", METHODS)
def test_exponential_decay(method):
    """y' = -k y has y = y0 exp(-k t) (separable ODE)."""
    k, y0 = 2.0, 3.0
    r = solve_ode(lambda t, y: -k * y, (0, 2), [y0], method=method, rtol=1e-10, atol=1e-12)
    exact = y0 * np.exp(-k * r.t)
    assert r.status == 0 and r.method == method
    assert np.max(np.abs(r.y[:, 0] - exact)) < 1e-6
    assert r.t[0] == 0.0 and r.t[-1] == 2.0


@pytest.mark.parametrize("method", METHODS)
def test_logistic(method):
    """y' = r y (1 - y/K) has y = K / (1 + ((K - y0)/y0) exp(-r t)) (Verhulst 1838)."""
    r_, K, y0 = 1.3, 10.0, 0.5
    sol = solve_ode(lambda t, y: r_ * y * (1 - y / K), (0, 8), y0, method=method,
                    rtol=1e-10, atol=1e-12)
    exact = K / (1 + ((K - y0) / y0) * np.exp(-r_ * sol.t))
    assert np.max(np.abs(sol.y[:, 0] - exact)) < 1e-6


@pytest.mark.parametrize("method", ["RK45", "DOP853", "LSODA", "Radau"])
def test_harmonic_oscillator_position_and_energy(method):
    """x'' = -w^2 x: x = cos(w t) for x(0)=1, v(0)=0; E = (v^2 + w^2 x^2)/2 is conserved."""
    w = 2.0 * np.pi
    T = 5.0  # five periods
    sol = solve_ode(lambda t, y: [y[1], -w * w * y[0]], (0, T), [1.0, 0.0], method=method,
                    rtol=1e-10, atol=1e-12)
    assert np.max(np.abs(sol.y[:, 0] - np.cos(w * sol.t))) < 1e-5
    energy = 0.5 * (sol.y[:, 1] ** 2 + (w * sol.y[:, 0]) ** 2)
    assert np.max(np.abs(energy - energy[0])) / energy[0] < 1e-6


def test_harmonic_oscillator_energy_tight_dop853():
    """DOP853 at rtol 1e-12 keeps the energy drift over 10 periods below 1e-9 (relative)."""
    w = 3.0
    T = 10 * 2 * np.pi / w
    sol = solve_ode(lambda t, y: [y[1], -w * w * y[0]], (0, T), [1.0, 0.0],
                    method="DOP853", rtol=1e-12, atol=1e-14)
    energy = 0.5 * (sol.y[:, 1] ** 2 + (w * sol.y[:, 0]) ** 2)
    assert np.max(np.abs(energy - energy[0])) / energy[0] < 1e-9


def test_backward_integration():
    """y' = -y integrated from t=2 back to 0 starting at exp(-2) returns y(0) = 1."""
    sol = solve_ode(lambda t, y: -y, (2.0, 0.0), [np.exp(-2.0)], rtol=1e-10, atol=1e-12)
    assert sol.t[0] == 2.0 and sol.t[-1] == 0.0
    assert sol.y[-1, 0] == pytest.approx(1.0, abs=1e-8)


# -- stiff problem ---------------------------------------------------------------------
def _stiff(t, y):
    # y' = -1000 (y - cos t) - sin t with y(0) = 1 has the exact solution y = cos t
    return -1000.0 * (y - np.cos(t)) - np.sin(t)


@pytest.mark.parametrize("method", ["Radau", "BDF", "LSODA"])
def test_stiff_implicit_methods_accurate_and_cheap(method):
    """Exact solution y = cos t (verify by substitution). Implicit methods need few steps."""
    sol = solve_ode(_stiff, (0, 10), [1.0], method=method, rtol=1e-8, atol=1e-10)
    assert np.max(np.abs(sol.y[:, 0] - np.cos(sol.t))) < 1e-5
    assert sol.nfev < 5000
    assert not [d for d in sol.diagnostics if d.code == "ODE_STIFF_SUSPECTED"]


def test_stiff_explicit_method_is_expensive_and_flagged():
    """RK45 is stability-limited (step ~ 3/|lambda|): many evaluations and a hint diagnostic."""
    lam = 2000.0
    explicit = solve_ode(lambda t, y: -lam * (y - np.cos(t)) - np.sin(t), (0, 20), [1.0],
                         method="RK45", rtol=1e-6, atol=1e-9)
    implicit = solve_ode(lambda t, y: -lam * (y - np.cos(t)) - np.sin(t), (0, 20), [1.0],
                         method="Radau", rtol=1e-6, atol=1e-9)
    assert explicit.nfev > 10 * implicit.nfev
    assert any(d.code == "ODE_STIFF_SUSPECTED" for d in explicit.diagnostics)


def test_analytic_jacobian_matches_numeric():
    """A user Jacobian (callable or matrix) gives the same answer for a linear system."""
    A = np.array([[-100.0, 1.0], [0.0, -0.5]])
    def f(t, y):
        return A @ y

    base = solve_ode(f, (0, 1), [1.0, 1.0], method="Radau", rtol=1e-9, atol=1e-12)
    with_call = solve_ode(f, (0, 1), [1.0, 1.0], method="Radau", rtol=1e-9, atol=1e-12,
                          jac=lambda t, y: A)
    with_mat = solve_ode(f, (0, 1), [1.0, 1.0], method="BDF", rtol=1e-9, atol=1e-12, jac=A)
    exact = expm(A) @ np.array([1.0, 1.0])
    assert np.allclose(base.y[-1], exact, atol=1e-6)
    assert np.allclose(with_call.y[-1], exact, atol=1e-6)
    assert np.allclose(with_mat.y[-1], exact, atol=1e-6)


# -- options: t_eval, events, shapes -----------------------------------------------------
def test_result_shape_and_t_eval_respected():
    te = np.linspace(0, 1, 11)
    r = solve_ode(lambda t, y: [y[1], -y[0]], (0, 1), [0.0, 1.0], t_eval=te,
                  rtol=1e-10, atol=1e-12)
    assert r.y.shape == (11, 2) and np.array_equal(r.t, te)
    assert np.allclose(r.y[:, 0], np.sin(te), atol=1e-8)  # y'' = -y, y(0)=0, y'(0)=1


def test_terminal_event_ball_drop():
    """Free fall from h=10 m: y = 0 at t = sqrt(2 h / g); the event ends the run there."""
    def hit(t, y):
        return y[0]
    hit.terminal = True
    hit.direction = -1
    r = solve_ode(lambda t, y: [y[1], -G], (0, 10), [10.0, 0.0], events=hit,
                  rtol=1e-10, atol=1e-12)
    t_hit = np.sqrt(2 * 10.0 / G)
    assert r.status == 1
    assert r.t_events[0][0] == pytest.approx(t_hit, abs=1e-7)
    assert r.t[-1] == pytest.approx(t_hit, abs=1e-7)
    assert r.y_events[0].shape == (1, 2)
    assert r.y_events[0][0, 1] == pytest.approx(-G * t_hit, abs=1e-6)
    assert any(d.code == "ODE_EVENT" for d in r.diagnostics)


def test_non_terminal_events_list_counts_crossings():
    """cos(t) crosses zero at pi/2 + k pi: three crossings in (0, 10)."""
    r = solve_ode(lambda t, y: [y[1], -y[0]], (0, 10), [1.0, 0.0],
                  events=[lambda t, y: y[0]], rtol=1e-10, atol=1e-12)
    assert r.status == 0 and len(r.t_events) == 1
    expected = np.pi / 2 + np.pi * np.arange(3)
    assert np.allclose(r.t_events[0], expected, atol=1e-6)


def test_scalar_rhs_for_one_state():
    r = solve_ode(lambda t, y: 1.0, (0, 3), 2.0, rtol=1e-10, atol=1e-12)  # y = 2 + t
    assert r.y[-1, 0] == pytest.approx(5.0, abs=1e-9)


def test_inputs_not_mutated_and_result_frozen():
    y0 = np.array([1.0, 2.0])
    keep = y0.copy()

    def f(t, y):
        y[0] = 99.0  # user code mutating its argument must not affect the solver
        return -y

    solve_ode(f, (0, 1), y0)
    assert np.array_equal(y0, keep)
    r = solve_ode(lambda t, y: -y, (0, 1), [1.0])
    assert isinstance(r, OdeResult) and isinstance(r.diagnostics, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.status = 5  # type: ignore[misc]


def test_vector_atol():
    r = solve_ode(lambda t, y: [-y[0], -2 * y[1]], (0, 1), [1.0, 1.0],
                  rtol=1e-9, atol=[1e-12, 1e-12])
    assert r.y[-1, 1] == pytest.approx(np.exp(-2.0), abs=1e-7)


# -- failures ----------------------------------------------------------------------------
@pytest.mark.parametrize("method", METHODS)
def test_finite_time_blowup_raises_convergence_error(method):
    """y' = y^2, y(0)=1 has y = 1/(1 - t), singular at t = 1: no solution reaches t = 2."""
    with pytest.raises(ConvergenceError) as ei:
        solve_ode(lambda t, y: y * y, (0, 2), [1.0], method=method)
    assert ei.value.last_estimate is not None


@pytest.mark.parametrize("method", METHODS)
def test_evaluation_budget(method):
    with pytest.raises(ConvergenceError, match="max_nfev"):
        solve_ode(lambda t, y: -y, (0, 100), [1.0], method=method, rtol=1e-10, max_nfev=20)


def test_budget_message_hints_stiffness_for_explicit_only():
    with pytest.raises(ConvergenceError, match="stiff"):
        solve_ode(_stiff, (0, 10), [1.0], method="RK45", max_nfev=50)
    with pytest.raises(ConvergenceError) as ei:
        solve_ode(_stiff, (0, 10), [1.0], method="BDF", max_nfev=5)
    assert "stiff" not in str(ei.value)


def test_nonfinite_initial_derivative_is_validation_error():
    with pytest.raises(ValidationError, match="NaN or Inf"):
        solve_ode(lambda t, y: [np.nan], (0, 1), [1.0])


# -- validation -----------------------------------------------------------------------------
@pytest.mark.parametrize("kwargs", [
    {"method": "euler"}, {"method": "rk45"}, {"rtol": 0.0}, {"rtol": -1e-3}, {"rtol": 1e-15},
    {"rtol": np.nan}, {"atol": -1e-9}, {"atol": [1e-9, 1e-9, 1e-9]}, {"atol": np.nan},
    {"max_step": 0.0}, {"max_step": -1.0}, {"first_step": 0.0}, {"max_nfev": 0},
    {"max_nfev": 1.5}, {"max_nfev": True}, {"t_eval": [0.0, 2.0]}, {"t_eval": [0.5, 0.2]},
    {"t_eval": [0.2, 0.2]}, {"events": 5}, {"events": []}, {"events": [lambda t, y: 0, 3]},
])
def test_invalid_options(kwargs):
    with pytest.raises(ValidationError):
        solve_ode(lambda t, y: -y, (0, 1), [1.0], **kwargs)


@pytest.mark.parametrize("jac", [np.eye(2), [[np.nan]], [[1j]], "x"])
def test_invalid_jac_for_implicit_method(jac):
    with pytest.raises(ValidationError, match="jac"):
        solve_ode(lambda t, y: -y, (0, 1), [1.0], method="Radau", jac=jac)


@pytest.mark.parametrize("t_span", [(0, 0), (0, np.inf), (np.nan, 1), (0, 1, 2), [[0], [1], [2]],
                                    "ab"])
def test_invalid_t_span(t_span):
    with pytest.raises(ValidationError):
        solve_ode(lambda t, y: -y, t_span, [1.0])


@pytest.mark.parametrize("y0", [[], [np.nan], [np.inf], [1 + 1j], [[1.0, 2.0], [3.0, 4.0]],
                                ["a"]])
def test_invalid_y0(y0):
    with pytest.raises(ValidationError):
        solve_ode(lambda t, y: -y, (0, 1), y0)


def test_invalid_f():
    with pytest.raises(ValidationError, match="callable"):
        solve_ode("not callable", (0, 1), [1.0])  # type: ignore[arg-type]
    with pytest.raises(DimensionError):
        solve_ode(lambda t, y: [1.0, 2.0], (0, 1), [1.0])
    with pytest.raises(ValidationError, match="real"):
        solve_ode(lambda t, y: [1j], (0, 1), [1.0])
    with pytest.raises(ValidationError, match="real"):
        solve_ode(lambda t, y: "x", (0, 1), [1.0])


def test_jac_rejected_for_explicit_method():
    with pytest.raises(ValidationError, match="jac"):
        solve_ode(lambda t, y: -y, (0, 1), [1.0], method="RK45", jac=lambda t, y: [[-1.0]])


def test_exception_in_f_propagates():
    class Boom(RuntimeError):
        pass

    def f(t, y):
        raise Boom("user error")

    for method in ("RK45", "LSODA"):
        with pytest.raises(Boom):
            solve_ode(f, (0, 1), [1.0], method=method)
