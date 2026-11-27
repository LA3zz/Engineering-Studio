"""Symbolic mathematics on top of SymPy (E11).

``SymExpr`` wraps a SymPy expression. Every function accepts ``SymExpr``, text such as
``"x^2 + 3*sin(x)"``, or a real/complex number, and returns ``SymExpr`` (or tuples of them).

Text is never passed to ``eval`` unchecked: a tokenizer admits only numbers, identifiers and
``+ - * / ^ ** ( ) ,``; identifiers followed by ``(`` must be one of ``FUNCTIONS``; powers are
inspected on the unevaluated tree before anything is computed (numeric exponents above 1000 are
rejected, so ``9**9**9`` cannot hang). Implicit multiplication (``2x``) is not supported.

Names: ``FUNCTIONS`` (sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, exp, log (natural),
ln, log10, sqrt, abs) and ``CONSTANTS`` (pi, e, I, oo, inf) are reserved; any other identifier
is a plain SymPy ``Symbol`` (no assumptions). Parsing results that are undefined (division by
zero, ``log(0)``) are errors.

Honesty rules (nothing is returned silently wrong):
- ``integrate``/``limit``/``laplace``/``inverse_laplace``/``series`` that SymPy cannot evaluate
  raise ``NotSupportedError`` instead of returning an unevaluated object.
- Integrals whose value depends on assumptions (a ``Piecewise`` result) raise unless
  ``allow_conditional=True``; divergent definite integrals raise.
- ``solve`` returns only complete, finite solution sets (distinct solutions, no multiplicity);
  periodic or infinite families raise. ``solve_system`` checks each solution by substitution; for
  nonlinear systems SymPy may miss solutions.
- A two-sided ``limit`` whose one-sided limits differ raises.
- ``inverse_laplace`` results hold for t > 0 (the Heaviside(t) factor is removed).
- ``equivalent`` returns True only when ``simplify(a - b)`` is exactly zero; False means "not
  shown equal".
Symbolic operations can take very long on hard inputs; stopping them is the kernel's job.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import convert_xor, parse_expr, standard_transformations

from engstudio.core.errors import NotSupportedError, ValidationError

__all__ = [
    "CONSTANTS", "FUNCTIONS", "SymExpr", "diff", "equivalent", "expand", "factor", "integrate",
    "inverse_laplace", "lambdify", "laplace", "limit", "parse", "series", "simplify", "solve",
    "to_matlab_code",
    "solve_system", "subs", "to_numeric",
]

MAX_TEXT = 2000
MAX_TOKENS = 500
MAX_EXPONENT = 1000
MAX_ORDER = 50

_FUNCS: dict[str, Callable] = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "asin": sp.asin, "acos": sp.acos,
    "atan": sp.atan, "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "exp": sp.exp,
    "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs,
    "log10": lambda x, **_kw: sp.log(x, 10),
}
_CONSTS: dict[str, sp.Basic] = {"pi": sp.pi, "e": sp.E, "I": sp.I, "oo": sp.oo, "inf": sp.oo}
FUNCTIONS = tuple(_FUNCS)
CONSTANTS = tuple(_CONSTS)
_RESERVED = frozenset(_FUNCS) | frozenset(_CONSTS)
_GLOBALS = {"__builtins__": {}, "Integer": sp.Integer, "Float": sp.Float,
            "Rational": sp.Rational, "Symbol": sp.Symbol, "Add": sp.Add, "Mul": sp.Mul,
            "Pow": sp.Pow}
_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
    r"|(?P<id>[A-Za-z][A-Za-z0-9_]*)|(?P<op>\*\*|[-+*/^(),]))")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_TRANSFORMS = standard_transformations + (convert_xor,)


@dataclass(frozen=True, eq=False)
class SymExpr:
    """Immutable wrapper around a SymPy expression."""

    expr: sp.Basic

    def __str__(self) -> str:
        return sp.sstr(self.expr)

    def __repr__(self) -> str:
        return f"SymExpr({self})"

    @property
    def free_symbols(self) -> tuple[str, ...]:
        return tuple(sorted(s.name for s in self.expr.free_symbols))

    def latex(self) -> str:
        return sp.latex(self.expr)


# -- parsing ---------------------------------------------------------------------------
def _scan(text: str) -> dict[str, object]:
    """Validate the token stream and build the local namespace."""
    names: dict[str, object] = {}
    pos, count = 0, 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            if text[pos:].strip() == "":
                break
            bad = text[pos:].lstrip()[0]
            raise ValidationError(f"cannot parse {text!r}: unexpected character {bad!r}")
        count += 1
        if count > MAX_TOKENS:
            raise ValidationError(f"expression too long (more than {MAX_TOKENS} tokens)")
        pos = m.end()
        if m.group("num") is not None:
            tok = m.group("num")
            if len(tok) > 30 or not math.isfinite(float(tok)):
                raise ValidationError(f"number out of range: {tok[:30]}")
        elif m.group("id") is not None:
            name = m.group("id")
            call = text[pos:].lstrip().startswith("(")
            if name in _FUNCS:
                if not call:
                    raise ValidationError(f"function {name!r} must be called: {name}(...)")
                names[name] = _FUNCS[name]
            elif call:
                raise ValidationError(f"unknown function {name!r}")
            elif name in _CONSTS:
                names[name] = _CONSTS[name]
            else:
                names[name] = sp.Symbol(name)
    return names


def _check_powers(tree: sp.Basic) -> None:
    for node in sp.postorder_traversal(tree):  # inner powers first
        if not (isinstance(node, sp.Pow) and node.exp.is_number):
            continue
        if bool(abs(sp.N(node.exp)) > MAX_EXPONENT):
            raise ValidationError(f"exponent too large (limit {MAX_EXPONENT})")


def _parse(text: str) -> sp.Basic:
    if not isinstance(text, str):
        raise ValidationError("expected text, a number or a SymExpr")
    if not text.strip():
        raise ValidationError("empty expression")
    if len(text) > MAX_TEXT:
        raise ValidationError(f"expression too long (limit {MAX_TEXT} characters)")
    names = _scan(text)
    try:
        tree = parse_expr(text, local_dict=names, global_dict=dict(_GLOBALS),
                          transformations=_TRANSFORMS, evaluate=False)
    except Exception as exc:  # SymPy raises many types for malformed input
        raise ValidationError(f"cannot parse {text!r}: {exc}") from exc
    _check_powers(tree)
    value = tree.doit()
    if value.has(sp.nan, sp.zoo):
        raise ValidationError(f"{text!r} is undefined (division by zero or similar)")
    return value


def parse(text: str) -> SymExpr:
    """Parse text into a ``SymExpr`` (see the module docstring for the accepted grammar)."""
    return SymExpr(_parse(text))


def _expr(x: object) -> sp.Basic:
    if isinstance(x, SymExpr):
        return x.expr
    if isinstance(x, str):
        return _parse(x)
    if isinstance(x, (bool, np.bool_)):
        raise ValidationError("expected text, a number or a SymExpr, got a boolean")
    if isinstance(x, (int, np.integer)):
        return sp.Integer(int(x))
    if isinstance(x, (float, np.floating)):
        if not math.isfinite(float(x)):
            raise ValidationError("numbers must be finite")
        return sp.Float(float(x))
    if isinstance(x, (complex, np.complexfloating)):
        z = complex(x)
        if not (math.isfinite(z.real) and math.isfinite(z.imag)):
            raise ValidationError("numbers must be finite")
        return sp.Float(z.real) + sp.I * sp.Float(z.imag)
    raise ValidationError(f"expected text, a number or a SymExpr, got {type(x).__name__}")


def _symbol(v: object, what: str = "variable") -> sp.Symbol:
    if isinstance(v, SymExpr) and isinstance(v.expr, sp.Symbol):
        return v.expr
    if isinstance(v, str) and _NAME.match(v) and v not in _RESERVED:
        return sp.Symbol(v)
    raise ValidationError(f"{what}: expected a plain name (not a function or constant), "
                          f"got {v!r}")


def _positive_int(v: object, name: str, upper: int) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or not 1 <= v <= upper:
        raise ValidationError(f"{name}: must be an integer in 1..{upper}")
    return int(v)


# -- simple transformations ---------------------------------------------------------------
def simplify(expr: SymExpr | str) -> SymExpr:
    return SymExpr(sp.simplify(_expr(expr)))


def expand(expr: SymExpr | str) -> SymExpr:
    return SymExpr(sp.expand(_expr(expr)))


def factor(expr: SymExpr | str) -> SymExpr:
    return SymExpr(sp.factor(_expr(expr)))


def subs(expr: SymExpr | str, mapping: Mapping[str, object]) -> SymExpr:
    """Substitute symbols simultaneously; values may be numbers, text or ``SymExpr``."""
    if not isinstance(mapping, Mapping):
        raise ValidationError("mapping: expected a dict of name -> value")
    table = {_symbol(k, "mapping key"): _expr(v) for k, v in mapping.items()}
    return SymExpr(_expr(expr).subs(table, simultaneous=True))


def equivalent(a: SymExpr | str, b: SymExpr | str) -> bool:
    """True if ``simplify(a - b)`` is exactly zero. False means 'not shown equal'."""
    return bool(sp.simplify(_expr(a) - _expr(b)) == 0)


def to_numeric(expr: SymExpr | str, values: Mapping[str, object] | None = None) -> float | complex:
    """Evaluate to a Python float (or complex if the value is not real). All symbols need values."""
    e = _expr(expr)
    if values:
        e = e.subs({_symbol(k, "values key"): _expr(v) for k, v in values.items()},
                   simultaneous=True)
    if e.free_symbols:
        names = ", ".join(sorted(s.name for s in e.free_symbols))
        raise ValidationError(f"to_numeric: no value for symbol(s): {names}")
    try:
        z = complex(sp.N(e, 17))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"to_numeric: {e} is not a finite number") from exc
    if not (math.isfinite(z.real) and math.isfinite(z.imag)):
        raise ValidationError(f"to_numeric: {e} is not a finite number")
    return float(z.real) if z.imag == 0 else z


def lambdify(expr: SymExpr | str, variables: Sequence[str]) -> Callable:
    """NumPy-vectorised function of ``variables`` (in that order). Constants return scalars."""
    e = _expr(expr)
    if isinstance(variables, str) or not isinstance(variables, Sequence):
        raise ValidationError("variables: expected a sequence of names")
    syms = [_symbol(v) for v in variables]
    if len(set(syms)) != len(syms):
        raise ValidationError("variables: names must be distinct")
    missing = e.free_symbols - set(syms)
    if missing:
        raise ValidationError("lambdify: unlisted symbol(s): "
                              + ", ".join(sorted(s.name for s in missing)))
    return sp.lambdify(syms, e, modules="numpy")


# -- calculus -------------------------------------------------------------------------------
def diff(expr: SymExpr | str, var: SymExpr | str, order: int = 1) -> SymExpr:
    """Derivative of ``expr`` with respect to ``var`` (``order`` 1..50)."""
    n = _positive_int(order, "order", MAX_ORDER)
    return SymExpr(sp.diff(_expr(expr), _symbol(var), n))


def integrate(
    expr: SymExpr | str, var: SymExpr | str, a: object = None, b: object = None, *,
    allow_conditional: bool = False,
) -> SymExpr:
    """Indefinite integral (no constant of integration) or definite integral from a to b."""
    f, x = _expr(expr), _symbol(var)
    if (a is None) != (b is None):
        raise ValidationError("give both limits a and b, or neither")
    definite = a is not None
    result = sp.integrate(f, (x, _expr(a), _expr(b))) if definite else sp.integrate(f, x)
    if result.has(sp.Piecewise):
        if not allow_conditional:
            raise NotSupportedError(
                "integrate: the result depends on assumptions about symbols (conditional); "
                "give numeric values for parameters or pass allow_conditional=True")
    elif result.has(sp.Integral):
        raise NotSupportedError("integrate: no closed form found")
    if definite and not result.has(sp.Piecewise) and result.has(sp.oo, -sp.oo, sp.zoo, sp.nan):
        raise NotSupportedError("integrate: the integral diverges or is undefined")
    return SymExpr(result)


def limit(
    expr: SymExpr | str, var: SymExpr | str, point: object, *, direction: str = "+-",
) -> SymExpr:
    """Limit as ``var`` approaches ``point`` (number, ``"oo"``, ``"-oo"``)."""
    if direction not in ("+-", "+", "-"):
        raise ValidationError("direction: must be '+-', '+' or '-'")
    f, x, p = _expr(expr), _symbol(var), _expr(point)
    if p.is_infinite:
        sides = [sp.limit(f, x, p)]
    elif direction == "+-":
        sides = [sp.limit(f, x, p, dir="+"), sp.limit(f, x, p, dir="-")]
    else:
        sides = [sp.limit(f, x, p, dir=direction)]
    for r in sides:
        if r.has(sp.Limit):
            raise NotSupportedError("limit: could not be evaluated")
        if r.has(sp.AccumBounds, sp.nan, sp.zoo):
            raise NotSupportedError("limit: does not exist (oscillating or undefined)")
    if len(sides) == 2 and sides[0] != sides[1]:
        raise NotSupportedError(
            f"limit: two-sided limit does not exist (from the right {sides[0]}, "
            f"from the left {sides[1]}); choose direction '+' or '-'")
    return SymExpr(sides[0])


def series(expr: SymExpr | str, var: SymExpr | str, point: object = 0, n: int = 6) -> SymExpr:
    """Taylor/Laurent polynomial around ``point`` with terms of order below ``n`` (1..50)."""
    order = _positive_int(n, "n", MAX_ORDER)
    f, x, p = _expr(expr), _symbol(var), _expr(point)
    try:
        result = sp.series(f, x, p, order).removeO()
    except (NotImplementedError, ValueError, TypeError) as exc:
        raise NotSupportedError(f"series: could not be computed ({exc})") from exc
    return SymExpr(result)


# -- equations ------------------------------------------------------------------------------
def _equation(eq: object) -> sp.Basic:
    if isinstance(eq, str) and "=" in eq:
        parts = eq.split("=")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValidationError(f"equation {eq!r}: use exactly one '=' (no '==')")
        return _parse(parts[0]) - _parse(parts[1])
    return _expr(eq)


def _sort_key(v: sp.Basic) -> tuple:
    try:
        z = complex(sp.N(v))
        return (0, z.real, z.imag, "")
    except (TypeError, ValueError, OverflowError):
        return (1, 0.0, 0.0, str(v))


def solve(
    equation: SymExpr | str, var: SymExpr | str, *, domain: str = "complex",
) -> tuple[SymExpr, ...]:
    """All distinct solutions of ``equation`` (text with one ``=``, or an expression = 0)."""
    if domain not in ("complex", "real"):
        raise ValidationError("domain: must be 'complex' or 'real'")
    f, x = _equation(equation), _symbol(var)
    dom = sp.S.Complexes if domain == "complex" else sp.S.Reals
    try:
        found = sp.solveset(f, x, domain=dom)
    except (NotImplementedError, ValueError, TypeError) as exc:
        raise NotSupportedError(f"solve: could not be solved ({exc})") from exc
    if found == sp.S.EmptySet:
        return ()
    if not isinstance(found, sp.FiniteSet):
        raise NotSupportedError(
            f"solve: the solution set is not a finite list of closed-form values: {found}")
    return tuple(SymExpr(v) for v in sorted(found, key=_sort_key))


def solve_system(
    equations: Sequence[SymExpr | str], variables: Sequence[SymExpr | str],
) -> tuple[dict[str, SymExpr], ...]:
    """Solutions of simultaneous equations as dicts name -> value (each checked by substitution)."""
    if isinstance(equations, (str, SymExpr)) or not isinstance(equations, Sequence):
        raise ValidationError("equations: expected a sequence")
    if isinstance(variables, (str, SymExpr)) or not isinstance(variables, Sequence):
        raise ValidationError("variables: expected a sequence")
    if not equations or not variables:
        raise ValidationError("equations and variables must not be empty")
    eqs = [_equation(e) for e in equations]
    syms = [_symbol(v) for v in variables]
    if len(set(syms)) != len(syms):
        raise ValidationError("variables: names must be distinct")
    try:
        sols = sp.solve(eqs, syms, dict=True)
    except (NotImplementedError, ValueError, TypeError) as exc:
        raise NotSupportedError(f"solve_system: could not be solved ({exc})") from exc
    out = []
    for sol in sols:
        for eq in eqs:
            residual = sp.simplify(eq.subs(sol))
            if not residual.free_symbols and abs(sp.N(residual)) > 1e-9:
                raise NotSupportedError("solve_system: a candidate solution failed the check")
        out.append({k.name: SymExpr(v) for k, v in sol.items()})
    return tuple(out)


# -- Laplace transforms ----------------------------------------------------------------------
def laplace(expr: SymExpr | str, t: SymExpr | str, s: SymExpr | str) -> SymExpr:
    """One-sided Laplace transform F(s) of f(t) (convergence conditions are not returned)."""
    f, tv, sv = _expr(expr), _symbol(t, "t"), _symbol(s, "s")
    if tv == sv:
        raise ValidationError("t and s must be different symbols")
    try:
        result = sp.laplace_transform(f, tv, sv, noconds=True)
    except (NotImplementedError, ValueError, TypeError) as exc:
        raise NotSupportedError(f"laplace: could not be computed ({exc})") from exc
    if result.has(sp.LaplaceTransform):
        raise NotSupportedError("laplace: no closed form found")
    return SymExpr(result)


def inverse_laplace(expr: SymExpr | str, s: SymExpr | str, t: SymExpr | str) -> SymExpr:
    """Inverse Laplace transform f(t) of F(s), valid for t > 0 (Heaviside(t) removed)."""
    f, sv, tv = _expr(expr), _symbol(s, "s"), _symbol(t, "t")
    if tv == sv:
        raise ValidationError("t and s must be different symbols")
    try:
        result = sp.inverse_laplace_transform(f, sv, tv)
    except (NotImplementedError, ValueError, TypeError) as exc:
        raise NotSupportedError(f"inverse_laplace: could not be computed ({exc})") from exc
    if result.has(sp.InverseLaplaceTransform):
        raise NotSupportedError("inverse_laplace: no closed form found")
    return SymExpr(result.subs(sp.Heaviside(tv), 1))

# -- helpers for the interpreter's symbolic values (B2b-5) -------------------------------------
__all__ = [*__all__, "apply_function", "arith", "as_symexpr", "default_variable", "equation",
           "is_symbol", "negate", "residual_form", "symbol", "to_text"]


def as_symexpr(x: object) -> SymExpr:
    """``SymExpr`` from a ``SymExpr``, text or a number."""
    return SymExpr(_expr(x))


def symbol(name: str) -> SymExpr:
    """A plain symbol (reserved function/constant names are rejected)."""
    return SymExpr(_symbol(name))


def is_symbol(x: object) -> bool:
    return isinstance(x, SymExpr) and isinstance(x.expr, sp.Symbol)


def arith(op: str, a: object, b: object) -> SymExpr:
    """``a op b`` for op in ``+ - * / ^``; division by zero, huge exponents and undefined
    results raise ``ValidationError``."""
    if op not in ("+", "-", "*", "/", "^"):
        raise ValidationError(f"arith: unsupported operator {op!r}")
    x, y = _expr(a), _expr(b)
    if op == "/" and y == 0:
        raise ValidationError("division by zero")
    if op == "^" and y.is_Number and abs(y) > MAX_EXPONENT:
        raise ValidationError(f"exponent too large (limit {MAX_EXPONENT})")
    result = {"+": lambda: x + y, "-": lambda: x - y, "*": lambda: x * y,
              "/": lambda: x / y, "^": lambda: x**y}[op]()
    if result.has(sp.nan, sp.zoo):
        raise ValidationError("the result is undefined (division by zero or similar)")
    return SymExpr(result)


def negate(a: object) -> SymExpr:
    return SymExpr(-_expr(a))


def equation(a: object, b: object) -> SymExpr:
    """The equation ``a == b`` as a ``SymExpr`` (use ``residual_form`` before solving)."""
    return SymExpr(sp.Eq(_expr(a), _expr(b)))


def residual_form(x: object) -> SymExpr:
    """``lhs - rhs`` of an equation (text with one ``=`` or an equation object); an expression
    is taken as ``expr = 0``."""
    e = _expr(x) if isinstance(x, SymExpr) else _equation(x)
    if isinstance(e, sp.Equality):
        e = e.lhs - e.rhs
    return SymExpr(e)


def apply_function(name: str, x: object) -> SymExpr:
    """Apply one of ``FUNCTIONS`` (sin, exp, sqrt, ...) to an expression."""
    if name not in _FUNCS:
        raise ValidationError(f"unknown function {name!r}")
    result = _FUNCS[name](_expr(x))
    if result.has(sp.nan, sp.zoo):
        raise ValidationError(f"{name}: the result is undefined")
    return SymExpr(result)


def default_variable(expr: object) -> str:
    """Default variable: the only symbol, else the one closest to 'x' (later letter on ties);
    ``'x'`` for an expression without symbols."""
    e = _equation(expr) if isinstance(expr, str) else _expr(expr)
    names = sorted(s.name for s in e.free_symbols)
    if not names:
        return "x"
    return min(names, key=lambda n: (abs(ord(n[0].lower()) - ord("x")), -ord(n[0]), n))


def to_matlab_code(x: SymExpr | str) -> str:
    """Element-wise MATLAB code for an expression (``.^``, ``.*``, ``./``), as matlabFunction
    writes it. Equations are not code."""
    e = _expr(x)
    if isinstance(e, sp.Equality):
        raise ValidationError("matlabFunction: an equation cannot be turned into a function")
    return sp.octave_code(e)


def to_text(x: SymExpr) -> str:
    """MATLAB-style text: ``^`` for powers, ``lhs == rhs`` for equations."""
    e = x.expr
    if isinstance(e, sp.Equality):
        return f"{sp.sstr(e.lhs)} == {sp.sstr(e.rhs)}".replace("**", "^")
    return sp.sstr(e).replace("**", "^")
