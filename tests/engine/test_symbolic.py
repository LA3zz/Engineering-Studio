"""E11 tests: engine.symbolic checked against textbook identities and numeric cross-checks."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.engine.calculus import derivative, quad
from engstudio.engine.symbolic import (
    SymExpr,
    diff,
    equivalent,
    expand,
    factor,
    integrate,
    inverse_laplace,
    lambdify,
    laplace,
    limit,
    parse,
    series,
    simplify,
    solve,
    solve_system,
    subs,
    to_numeric,
)


def _values(solutions):
    return [to_numeric(s) for s in solutions]


# -- parsing and safety ------------------------------------------------------------------
def test_parse_basics_and_symbols():
    e = parse("b*a + c^2 - 1")
    assert isinstance(e, SymExpr)
    assert e.free_symbols == ("a", "b", "c")
    assert equivalent(e, "a*b + c**2 - 1")
    assert "frac" in parse("x/2").latex()
    assert repr(parse("x")) == "SymExpr(x)"
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.expr = None  # type: ignore[misc]


def test_parse_values_and_constants():
    assert to_numeric("sin(pi/6)") == pytest.approx(0.5, abs=1e-15)
    assert to_numeric("e") == pytest.approx(math.e, rel=1e-15)
    assert to_numeric("2.5e3*x", {"x": 2}) == pytest.approx(5000.0)
    assert to_numeric("ln(e^3) + log10(1000) + abs(-2) + sqrt(16)") == pytest.approx(12.0)
    assert to_numeric("2^10 - 2**3") == 1016.0
    assert to_numeric("sqrt(-4)") == 2j


@pytest.mark.parametrize("text", [
    "__import__('os')", "x.__class__", "open('f')", "x; y", "x = 1", "x == 1", "[1, 2]",
    "{x}", "x[0]", "'a'", "lambda", "import os", "foo(x)", "x(2)", "sin", "2x", "x y", "x**",
    "(x", "x)", "2(3)", "", "   ", "1/0", "0/0", "log(0)", "x@y", "x!", "x<2", "1e999",
    "1" * 40, "9**9**9", "2^1001", "x^1001", "(x^2)^1001", "x" * 2001,
])
def test_parse_rejects_unsafe_or_invalid_text(text):
    with pytest.raises(ValidationError):
        parse(text)


def test_exponent_limit_boundary_and_bad_types():
    assert to_numeric("2^1000") == 2.0**1000
    for bad in (None, [1], {"x": 1}, True, float("nan"), float("inf"), 1 + float("inf") * 1j):
        with pytest.raises(ValidationError):
            simplify(bad)  # type: ignore[arg-type]


# -- transformations ------------------------------------------------------------------------
def test_expand_factor_simplify():
    assert equivalent(expand("(x+1)^2"), "x^2 + 2*x + 1") and "(" not in str(expand("(x+1)^2"))
    assert equivalent(factor("x^2 - 1"), "(x-1)*(x+1)") and "(" in str(factor("x^2 - 1"))
    assert str(simplify("sin(x)^2 + cos(x)^2")) == "1"


def test_subs_and_equivalent():
    assert equivalent(subs("x^2 + y", {"x": 3}), "9 + y")
    assert equivalent(subs("x + y", {"x": "y", "y": "x"}), "x + y")  # simultaneous
    assert equivalent(subs("x^2", {"x": "y + 1"}), "(y+1)^2")
    assert equivalent("sin(2*x)", "2*sin(x)*cos(x)")
    assert not equivalent("x", "x + 1")
    with pytest.raises(ValidationError):
        subs("x", {"sin": 1})
    with pytest.raises(ValidationError):
        subs("x", [("x", 1)])  # type: ignore[arg-type]


def test_to_numeric_errors_and_types():
    with pytest.raises(ValidationError, match="no value"):
        to_numeric("x + y", {"x": 1})
    with pytest.raises(ValidationError, match="finite"):
        to_numeric("oo")
    assert to_numeric("x^2", {"x": np.float64(3.0)}) == 9.0
    assert to_numeric("x^2", {"x": np.int64(4)}) == 16.0
    assert to_numeric("x", {"x": 1 + 2j}) == 1 + 2j
    for bad in ({"x": True}, {"x": "y"}, {"x": None}):
        with pytest.raises(ValidationError):
            to_numeric("x", bad)  # type: ignore[arg-type]


def test_lambdify():
    f = lambdify("x^2 + sin(x)", ["x"])
    x = np.linspace(0, 3, 7)
    assert np.allclose(f(x), x**2 + np.sin(x), atol=1e-14)
    g = lambdify("a - 2*b", ["b", "a"])
    assert g(1.0, 5.0) == 3.0  # argument order follows the list
    assert lambdify("3", [])() == 3
    for bad in (["x"], "x", ["x", "x"], ["sin"]):
        with pytest.raises(ValidationError):
            lambdify("x + y", bad)  # type: ignore[arg-type]


# -- differentiation ---------------------------------------------------------------------------
def test_diff_known_derivatives():
    assert equivalent(diff("x^3", "x"), "3*x^2")
    assert equivalent(diff("x^4", "x", 2), "12*x^2")
    assert equivalent(diff("sin(x)*exp(x)", "x"), "cos(x)*exp(x) + sin(x)*exp(x)")
    assert equivalent(diff("x^2*y", "y"), "x^2")
    assert str(diff("y", "x")) == "0"
    assert equivalent(diff("ln(x)", "x"), "1/x")
    assert equivalent(diff("atan(x)", "x"), "1/(1+x^2)")


def test_diff_matches_numeric_derivative():
    d = lambdify(diff("sin(x)*exp(-x/2)", "x"), ["x"])
    f = lambdify("sin(x)*exp(-x/2)", ["x"])
    for x0 in (0.3, 0.7, 2.0):
        assert d(x0) == pytest.approx(derivative(lambda t: float(f(t)), x0), abs=1e-7)


@pytest.mark.parametrize("kwargs", [
    {"order": 0}, {"order": 51}, {"order": 1.5}, {"order": True}, {"var": "sin"},
    {"var": "1x"}, {"var": "e"}, {"var": ""}, {"var": 5},
])
def test_diff_validation(kwargs):
    args = {"var": "x", "order": 1} | kwargs
    with pytest.raises(ValidationError):
        diff("x^2", **args)


# -- integration ----------------------------------------------------------------------------------
def test_indefinite_integrals_verified_by_differentiation():
    for f in ("x^2", "cos(x)", "exp(2*x)", "1/x", "x*exp(x)"):
        assert equivalent(diff(integrate(f, "x"), "x"), f), f


def test_definite_integrals_known_values():
    assert to_numeric(integrate("sin(x)", "x", 0, "pi")) == pytest.approx(2.0, abs=1e-14)
    assert to_numeric(integrate("exp(-x)", "x", 0, "oo")) == pytest.approx(1.0, abs=1e-14)
    assert to_numeric(integrate("1/x^2", "x", 1, "oo")) == pytest.approx(1.0, abs=1e-14)
    assert to_numeric(integrate("exp(-x^2)", "x", "-oo", "oo")) == pytest.approx(
        math.sqrt(math.pi), rel=1e-14)
    assert to_numeric(integrate("x^2", "x", -1, 1)) == pytest.approx(2 / 3, abs=1e-14)


def test_definite_integral_matches_numeric_quadrature():
    f = lambdify("x*exp(-x^2/3) + cos(x)", ["x"])
    exact = to_numeric(integrate("x*exp(-x^2/3) + cos(x)", "x", 0, 2))
    assert exact == pytest.approx(quad(lambda t: float(f(t)), 0, 2).value, rel=1e-9)


def test_integrate_refuses_unsound_results():
    with pytest.raises(NotSupportedError, match="closed form"):
        integrate("exp(x^x)", "x")
    with pytest.raises(NotSupportedError, match="diverges"):
        integrate("1/x", "x", 0, 1)
    with pytest.raises(NotSupportedError, match="assumptions"):
        integrate("exp(-a*x)", "x", 0, "oo")
    cond = integrate("exp(-a*x)", "x", 0, "oo", allow_conditional=True)
    assert "Piecewise" in str(cond)
    assert to_numeric(integrate("exp(-2*x)", "x", 0, "oo")) == pytest.approx(0.5)
    with pytest.raises(ValidationError, match="both limits"):
        integrate("x", "x", 0)
    with pytest.raises(ValidationError, match="both limits"):
        integrate("x", "x", b=1)


# -- equations ------------------------------------------------------------------------------------
def test_solve_polynomials():
    assert _values(solve("x^2 - 4 = 0", "x")) == [-2.0, 2.0]
    assert _values(solve("x^2 = 4", "x")) == [-2.0, 2.0]
    assert _values(solve("x^2 - 4", "x")) == [-2.0, 2.0]
    assert _values(solve(parse("x^2 - 4"), "x")) == [-2.0, 2.0]
    cubic = _values(solve("(x-1)*(x-2)*(x-3)", "x"))
    assert cubic == [1.0, 2.0, 3.0]
    assert _values(solve("x^2 + 1", "x")) == [-1j, 1j]
    assert solve("x^2 + 1", "x", domain="real") == ()
    assert solve("x + 1", "x") and to_numeric(solve("x + 1", "x")[0]) == -1.0


def test_solve_symbolic_parameter_and_quintic():
    sols = solve("a*x^2 - 1", "x")
    assert len(sols) == 2
    for s in sols:
        assert equivalent(subs("a*x^2 - 1", {"x": s}), "0")
    (root,) = solve("x^5 - x - 1", "x", domain="real")
    r = to_numeric(root)
    assert r == pytest.approx(1.1673039782614187, abs=1e-12)  # real root of x^5 = x + 1
    assert abs(r**5 - r - 1) < 1e-12


def test_solve_refuses_incomplete_answers():
    with pytest.raises(NotSupportedError, match="finite"):
        solve("sin(x) = 1/2", "x")
    with pytest.raises(NotSupportedError, match="finite"):
        solve("x - x", "x")


@pytest.mark.parametrize("eq", ["x == 2", "x = 2 = 3", "= 2", "x ="])
def test_solve_equation_text_errors(eq):
    with pytest.raises(ValidationError):
        solve(eq, "x")


def test_solve_domain_and_variable_errors():
    with pytest.raises(ValidationError, match="domain"):
        solve("x", "x", domain="rational")
    with pytest.raises(ValidationError):
        solve("x", "sin")


def test_solve_system_linear_nonlinear_and_empty():
    (sol,) = solve_system(["x + y = 3", "x - y = 1"], ["x", "y"])
    assert to_numeric(sol["x"]) == 2.0 and to_numeric(sol["y"]) == 1.0
    sols = solve_system(["x^2 + y^2 = 25", "x - y = 1"], ["x", "y"])
    pairs = sorted((to_numeric(s["x"]), to_numeric(s["y"])) for s in sols)
    assert pairs == [(-3.0, -4.0), (4.0, 3.0)]  # the circle meets the line at (4,3) and (-3,-4)
    assert solve_system(["x + y = 1", "x + y = 2"], ["x", "y"]) == ()


@pytest.mark.parametrize("eqs,vars_", [
    ("x = 1", ["x"]), (["x = 1"], "x"), ([], ["x"]), (["x = 1"], []), (["x = 1"], ["x", "x"]),
    (["x = 1"], ["sin"]),
])
def test_solve_system_validation(eqs, vars_):
    with pytest.raises(ValidationError):
        solve_system(eqs, vars_)


# -- limits and series --------------------------------------------------------------
def test_limits_known_values():
    assert str(limit("sin(x)/x", "x", 0)) == "1"
    assert str(limit("(exp(x)-1)/x", "x", 0)) == "1"
    assert to_numeric(limit("(1+1/x)^x", "x", "oo")) == pytest.approx(math.e, rel=1e-14)
    assert str(limit("1/x", "x", 0, direction="+")) == "oo"
    assert str(limit("1/x", "x", 0, direction="-")) == "-oo"
    assert str(limit("1/x^2", "x", 0)) == "oo"
    assert str(limit("1/x", "x", "oo")) == "0"
    assert to_numeric(limit("x^2", "x", 3)) == 9.0


def test_limit_refuses_nonexistent_limits():
    with pytest.raises(NotSupportedError, match="two-sided"):
        limit("1/x", "x", 0)
    with pytest.raises(NotSupportedError, match="does not exist"):
        limit("sin(x)", "x", "oo")
    with pytest.raises(ValidationError, match="direction"):
        limit("x", "x", 0, direction="up")


def test_series_known_expansions():
    assert equivalent(series("exp(x)", "x", 0, 5), "1 + x + x^2/2 + x^3/6 + x^4/24")
    assert equivalent(series("sin(x)", "x", 0, 6), "x - x^3/6 + x^5/120")
    assert equivalent(series("ln(x)", "x", 1, 4), "(x-1) - (x-1)^2/2 + (x-1)^3/3")
    assert equivalent(series("1/(1-x)", "x", 0, 4), "1 + x + x^2 + x^3")
    poly = lambdify(series("exp(x)", "x", 0, 8), ["x"])
    assert float(poly(0.1)) == pytest.approx(math.exp(0.1), abs=1e-10)  # next term 0.1^8/8!


@pytest.mark.parametrize("n", [0, 51, 2.5, True, "3"])
def test_series_order_errors(n):
    with pytest.raises(ValidationError):
        series("exp(x)", "x", 0, n)


# -- Laplace -------------------------------------------------------------------------
@pytest.mark.parametrize("f,F", [
    ("1", "1/s"),
    ("exp(-3*t)", "1/(s+3)"),
    ("sin(w*t)", "w/(s^2 + w^2)"),
    ("cos(2*t)", "s/(s^2 + 4)"),
    ("t^2", "2/s^3"),
    ("t*exp(-a*t)", "1/(s+a)^2"),
])
def test_laplace_table(f, F):
    """Standard table of one-sided Laplace transforms (e.g. Oppenheim, Signals & Systems)."""
    assert equivalent(laplace(f, "t", "s"), F)


@pytest.mark.parametrize("F,f", [
    ("1/(s+3)", "exp(-3*t)"),
    ("1/(s^2+4)", "sin(2*t)/2"),
    ("s/(s^2+9)", "cos(3*t)"),
    ("2/s^3", "t^2"),
])
def test_inverse_laplace_table(F, f):
    assert equivalent(inverse_laplace(F, "s", "t"), f)


def test_laplace_round_trip_numeric():
    f = "exp(-2*t)*sin(3*t)"
    back = inverse_laplace(laplace(f, "t", "s"), "s", "t")
    for t0 in (0.3, 0.7, 1.5):
        assert to_numeric(back, {"t": t0}) == pytest.approx(
            to_numeric(f, {"t": t0}), rel=1e-9)


def test_laplace_errors():
    with pytest.raises(ValidationError, match="different"):
        laplace("t", "t", "t")
    with pytest.raises(ValidationError, match="different"):
        inverse_laplace("1/s", "s", "s")
    with pytest.raises(NotSupportedError):
        laplace("exp(t^2)", "t", "s")
