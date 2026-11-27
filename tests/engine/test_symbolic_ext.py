"""Engine helpers behind the interpreter's symbolic values (B2b-5). Reference values are exact
algebra: 2*x + x/4 = 9x/4, (x-1)(x+1), sin(pi/2) = 1, closest-to-x default variable rule."""

import pytest

from engstudio.core.errors import ValidationError
from engstudio.engine import symbolic as sy


def val(e, **kw):
    return sy.to_numeric(e, kw or None)


def test_arith_all_operators():
    x = sy.symbol("x")
    assert val(sy.arith("+", x, 2), x=3) == 5
    assert val(sy.arith("-", 2, x), x=3) == -1
    assert val(sy.arith("*", x, x), x=3) == 9
    assert val(sy.arith("/", x, 4), x=2) == 0.5
    assert val(sy.arith("^", x, 3), x=2) == 8
    assert str(sy.arith("+", sy.arith("*", 2, x), sy.arith("/", x, 4))) == "9*x/4"


def test_arith_rejects_bad_input():
    x = sy.symbol("x")
    with pytest.raises(ValidationError):
        sy.arith("/", 1, sy.arith("-", x, x))
    with pytest.raises(ValidationError):
        sy.arith("^", x, 5000)
    with pytest.raises(ValidationError):
        sy.arith("%", x, 1)
    with pytest.raises(ValidationError):
        sy.arith("^", 0, -1)


def test_negate_symbol_and_reserved_names():
    assert str(sy.negate(sy.symbol("y"))) == "-y"
    assert sy.is_symbol(sy.symbol("y")) and not sy.is_symbol(sy.negate(sy.symbol("y")))
    for bad in ("sin", "pi", "1x", ""):
        with pytest.raises(ValidationError):
            sy.symbol(bad)


def test_equation_and_residual_form():
    x = sy.symbol("x")
    eq = sy.equation(sy.arith("^", x, 2), 4)
    assert sy.to_text(eq) == "x^2 == 4"
    assert str(sy.residual_form(eq)) == "x**2 - 4"
    assert str(sy.residual_form("x^2 = 9")) == "x**2 - 9"
    assert str(sy.residual_form(x)) == "x"
    assert [val(s) for s in sy.solve(sy.residual_form(eq), "x")] == [-2, 2]


def test_apply_function():
    assert val(sy.apply_function("sin", sy.arith("/", sy.parse("pi"), 2))) == pytest.approx(1.0)
    assert str(sy.apply_function("sqrt", sy.symbol("x"))) == "sqrt(x)"
    with pytest.raises(ValidationError):
        sy.apply_function("gamma", 1)
    with pytest.raises(ValidationError):
        sy.apply_function("log", 0)


def test_default_variable_rule():
    assert sy.default_variable("x^2 + 1") == "x"
    assert sy.default_variable("a*t") == "t"
    assert sy.default_variable("a + b") == "b"  # closest to x; later letter wins ties
    assert sy.default_variable("5") == "x"
    assert sy.default_variable("y = 2") == "y"
    assert sy.default_variable("w + y") == "y"


def test_as_symexpr_and_text():
    assert str(sy.as_symexpr("x^2")) == "x**2" and sy.to_text(sy.as_symexpr("x^2")) == "x^2"
    assert sy.to_text(sy.as_symexpr(3)) == "3"
