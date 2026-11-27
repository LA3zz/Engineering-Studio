"""Symbolic builtins (B2b-5): ``syms``, ``sym``, ``diff``, ``int``, ``limit``, ``taylor``,
``solve``, ``simplify``, ``expand``, ``factor``, ``subs``, ``laplace``, ``ilaplace``, ``latex``,
``symvar``, plus symbolic behaviour for ``double``, ``char``, ``disp`` and the elementary
functions (``sin cos tan asin acos atan sinh cosh tanh exp log log10 sqrt abs``).
``install_sym(interp)`` registers them (after the core builtins, which it extends).

A symbolic value is a ``SymValue`` (class ``sym``) wrapping an ``engine.symbolic.SymExpr``.
Every symbolic function also accepts text (``diff('x^3', 'x')``) and plain scalar numbers.

Differences from MATLAB (nothing is returned silently wrong):
- Only scalar symbolic values: no symbolic vectors or matrices (``[x y]`` is an error).
- ``solve`` returns a ``sym`` for one solution, a cell array (column) for several and ``[]`` for
  none; a system ``solve({eq1, eq2}, {x, y})`` returns a struct with one field per unknown (an
  error if there are several solution sets). Equations are written ``x^2 == 4`` or as text
  ``'x^2 = 4'``; an expression alone means ``expr == 0``.
- ``syms x y`` creates the variables in the base workspace; assumptions (``real``...) are not
  supported. Numbers combined with symbols stay doubles (``x*pi`` holds the float value of pi).
- ``taylor(f, x, 'Order', n)`` keeps terms below ``x^n`` (default 6) like MATLAB.
- Functions that SymPy cannot evaluate in closed form raise an error instead of returning an
  unevaluated object. ``double(expr)`` needs numeric values for every symbol.
- ``ilaplace`` results hold for t > 0. Expression text uses ``^`` for powers.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _need
from engstudio.lang.display import format_value, short_text
from engstudio.lang.interp import Interpreter
from engstudio.lang.parser import parse
from engstudio.lang.symops import number_of
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    LtiValue,
    StructValue,
    SymValue,
    class_of,
    empty_double,
    size_of,
)

__all__ = ["display_text", "install_sym", "preview_text", "sym_functions", "sym_text"]

_ELEMENTARY = ("sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "exp", "log",
               "log10", "sqrt", "abs")
_ASSUMPTIONS = ("real", "positive", "integer", "rational", "clear")
_TAYLOR_OPTIONS = ("order", "expansionpoint")


def _engine():
    from engstudio.engine import symbolic

    return symbolic


# -- display ---------------------------------------------------------------------------
def sym_text(value: SymValue) -> str:
    return _engine().to_text(value.expr)


def _item_text(v: object) -> str:
    if isinstance(v, SymValue):
        return "{[" + sym_text(v) + "]}"
    rows, cols = size_of(v)
    return "{" + f"{rows}x{cols} {class_of(v)}" + "}"


def _sym_cell_text(name: str, cell: CellArray) -> str:
    rows, cols = cell.shape
    lines = ["    " + "  ".join(_item_text(cell.data[i, j]) for j in range(cols))
             for i in range(rows)]
    return f"{name} =\n\n  {rows}x{cols} cell array\n\n" + "\n".join(lines) + "\n\n"


def display_text(name: str, value: object) -> str:
    """Command Window text: symbolic values as ``name =`` + expression, others as before."""
    if isinstance(value, SymValue):
        return f"{name} =\n{sym_text(value)}\n\n"
    if isinstance(value, LtiValue):
        from engstudio.lang.builtins_control import lti_text

        return f"{name} =\n \n{lti_text(value)}\n\n"
    if isinstance(value, CellArray) and any(
            isinstance(v, SymValue) for v in value.data.ravel()):
        return _sym_cell_text(name, value)
    return format_value(name, value)


def preview_text(value: object) -> str:
    """Short text for the Workspace browser."""
    if isinstance(value, SymValue):
        text = sym_text(value)
        return text if len(text) <= 40 else text[:37] + "..."
    if isinstance(value, LtiValue):
        from engstudio.lang.builtins_control import lti_preview

        return lti_preview(value)
    return short_text(value)


# -- argument helpers --------------------------------------------------------------------
def _arg(v: object, name: str) -> object:
    if isinstance(v, SymValue):
        return v.expr
    if isinstance(v, CharArray):
        return v.to_str()
    try:
        return number_of(v)
    except ValidationError:
        raise ValidationError(
            f"{name}: expected a symbolic expression, text or a scalar number.") from None


def _lim(v: object, name: str) -> object:
    """Like ``_arg`` but +-Inf becomes the symbolic infinity."""
    if isinstance(v, np.ndarray) and v.shape == (1, 1) and v.dtype.kind == "f":
        if np.isposinf(v[0, 0]):
            return "oo"
        if np.isneginf(v[0, 0]):
            return "-oo"
    return _arg(v, name)


def _var(v: object, name: str) -> object:
    if isinstance(v, SymValue):
        return v.expr
    if isinstance(v, CharArray):
        return v.to_str()
    raise ValidationError(f"{name}: the variable must be a symbol or a name.")


def _is_var_arg(v: object) -> bool:
    return isinstance(v, (SymValue, CharArray))


def _count(v: object, name: str) -> int:
    n = number_of(v)
    if not isinstance(n, int) or n < 1:
        raise ValidationError(f"{name}: expected a positive integer.")
    return n


def _name_of(v: object, name: str) -> str:
    eng = _engine()
    if isinstance(v, SymValue) and eng.is_symbol(v.expr):
        return str(v.expr)
    if isinstance(v, CharArray):
        return v.to_str()
    raise ValidationError(f"{name}: the variable to replace must be a symbol.")


def _equation(v: object, name: str) -> object:
    if isinstance(v, SymValue):
        return _engine().residual_form(v.expr)
    if isinstance(v, CharArray):
        return _engine().residual_form(v.to_str())
    raise ValidationError(f"{name}: expected an equation or expression.")


def _numeric(value: object, name: str) -> complex | float:
    if isinstance(value, SymValue):
        return _engine().to_numeric(value.expr)
    try:
        return number_of(value)
    except ValidationError:
        raise ValidationError(f"{name}: all elements must be symbolic or numeric scalars."
                              ) from None


def sym_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The B2b-5 builtins bound to ``interp`` (overloads wrap the existing numeric ones)."""
    host = interp.host
    eng = _engine

    def default_var(f: object) -> object:
        return eng().default_variable(f)

    def syms(args: list, nargout: int) -> list:
        names = []
        for a in args:
            if not isinstance(a, CharArray):
                raise ValidationError("syms: names must be text, as in syms('x') or syms x y.")
            names.append(a.to_str())
        if not names:
            raise ValidationError("syms: give at least one name.")
        for n in names:
            if n in _ASSUMPTIONS:
                raise NotSupportedError(
                    f"syms: assumptions ('{n}') are not supported; declare plain symbols.")
        created = [(n, eng().symbol(n)) for n in names]
        for n, s in created:
            interp.workspace[n] = SymValue(s)
        return []

    def sym(args: list, nargout: int) -> list:
        _need("sym", args, 1)
        if isinstance(args[0], SymValue):
            return [args[0]]
        value = _arg(args[0], "sym")
        return [SymValue(eng().parse(value) if isinstance(value, str)
                         else eng().as_symexpr(value))]

    def diff(args: list, nargout: int) -> list:
        name = "diff"
        symbolic = bool(args) and (
            isinstance(args[0], SymValue)
            or (isinstance(args[0], CharArray) and len(args) >= 2 and _is_var_arg(args[1])))
        if not symbolic:
            return numeric_diff(args, nargout)
        _need(name, args, 1, 3)
        f = _arg(args[0], name)
        rest = list(args[1:])
        var = _var(rest.pop(0), name) if rest and _is_var_arg(rest[0]) else default_var(f)
        order = _count(rest.pop(0), name) if rest else 1
        if rest:
            raise ValidationError("diff: too many arguments.")
        return [SymValue(eng().diff(f, var, order))]

    def integral(args: list, nargout: int) -> list:
        name = "int"
        _need(name, args, 1, 4)
        f = _arg(args[0], name)
        rest = list(args[1:])
        if len(rest) == 0:
            var, lims = default_var(f), None
        elif len(rest) == 1:
            var, lims = _var(rest[0], name), None
        elif len(rest) == 2:
            var, lims = default_var(f), (rest[0], rest[1])
        else:
            var, lims = _var(rest[0], name), (rest[1], rest[2])
        if lims is None:
            return [SymValue(eng().integrate(f, var))]
        return [SymValue(eng().integrate(f, var, _lim(lims[0], name), _lim(lims[1], name)))]

    def limit(args: list, nargout: int) -> list:
        name = "limit"
        _need(name, args, 2, 4)
        f = _arg(args[0], name)
        rest = list(args[1:])
        direction = "+-"
        if len(rest) > 1 and isinstance(rest[-1], CharArray) and rest[-1].to_str() in (
                "left", "right"):
            direction = "-" if rest.pop().to_str() == "left" else "+"
        if len(rest) == 1:
            var, point = default_var(f), rest[0]
        elif len(rest) == 2:
            var, point = _var(rest[0], name), rest[1]
        else:
            raise ValidationError("limit: use limit(f, x, a), limit(f, a) or add 'left'/'right'.")
        return [SymValue(eng().limit(f, var, _lim(point, name), direction=direction))]

    def taylor(args: list, nargout: int) -> list:
        name = "taylor"
        _need(name, args, 1, 7)
        f = _arg(args[0], name)
        rest = list(args[1:])

        def is_option(v: object) -> bool:
            return isinstance(v, CharArray) and v.to_str().lower() in _TAYLOR_OPTIONS

        var = _var(rest.pop(0), name) if rest and _is_var_arg(rest[0]) and not is_option(
            rest[0]) else default_var(f)
        point: object = 0
        if rest and not is_option(rest[0]):
            point = _arg(rest.pop(0), name)
        order = 6
        if len(rest) % 2:
            raise ValidationError("taylor: options must be name-value pairs.")
        for key, val in zip(rest[::2], rest[1::2], strict=True):
            k = key.to_str().lower() if isinstance(key, CharArray) else ""
            if k == "order":
                order = _count(val, name)
            elif k == "expansionpoint":
                point = _arg(val, name)
            else:
                raise NotSupportedError(f"taylor: unsupported option {k or '?'!r}.")
        return [SymValue(eng().series(f, var, point, order))]

    def solve(args: list, nargout: int) -> list:
        name = "solve"
        _need(name, args, 1, 2)
        first = args[0]
        if isinstance(first, CellArray):
            if len(args) < 2 or not isinstance(args[1], CellArray):
                raise ValidationError(
                    "solve: for a system give the unknowns as a cell array: "
                    "solve({eq1, eq2}, {x, y}).")
            eqs = [_equation(e, name) for e in first.data.ravel(order="F")]
            unknowns = [_var(v, name) for v in args[1].data.ravel(order="F")]
            found = eng().solve_system(eqs, unknowns)
            if not found:
                raise ValidationError("solve: the system has no solution.")
            if len(found) > 1:
                raise NotSupportedError(
                    f"solve: the system has {len(found)} solution sets, which cannot be "
                    "returned as one struct yet.")
            return [StructValue({k: SymValue(v) for k, v in found[0].items()})]
        eq = _equation(first, name)
        var = _var(args[1], name) if len(args) > 1 else default_var(eq)
        solutions = eng().solve(eq, var)
        if not solutions:
            return [empty_double()]
        if len(solutions) == 1:
            return [SymValue(solutions[0])]
        return [CellArray.from_rows([[SymValue(s)] for s in solutions])]

    def transform1(name: str, fn_name: str) -> Builtin:
        def run(args: list, nargout: int) -> list:
            _need(name, args, 1)
            return [SymValue(getattr(eng(), fn_name)(_arg(args[0], name)))]

        return run

    def subs(args: list, nargout: int) -> list:
        name = "subs"
        _need(name, args, 3)
        f = _arg(args[0], name)
        old, new = args[1], args[2]
        if isinstance(old, CellArray) or isinstance(new, CellArray):
            if not (isinstance(old, CellArray) and isinstance(new, CellArray)
                    and old.shape == new.shape):
                raise ValidationError("subs: give two cell arrays of the same size.")
            keys, vals = old.data.ravel(order="F"), new.data.ravel(order="F")
        else:
            keys, vals = [old], [new]
        mapping = {_name_of(k, name): _arg(v, name) for k, v in zip(keys, vals, strict=True)}
        return [SymValue(eng().subs(f, mapping))]

    def transform_pair(name: str, forward: bool) -> Builtin:
        def run(args: list, nargout: int) -> list:
            _need(name, args, 1, 3)
            f = _arg(args[0], name)
            e = eng()
            if len(args) == 3:
                a, b = _var(args[1], name), _var(args[2], name)
            else:
                names = {s for s in e.as_symexpr(f).free_symbols}
                if forward:
                    a = "t" if "t" in names else default_var(f)
                    b = "s" if a != "s" else "z"
                else:
                    a = "s" if "s" in names else default_var(f)
                    b = "t" if a != "t" else "x"
            fn = e.laplace if forward else e.inverse_laplace
            return [SymValue(fn(f, a, b))]

        return run

    def latex(args: list, nargout: int) -> list:
        _need("latex", args, 1)
        return [CharArray.from_str(eng().as_symexpr(_arg(args[0], "latex")).latex())]

    def symvar(args: list, nargout: int) -> list:
        _need("symvar", args, 1)
        names = eng().as_symexpr(_arg(args[0], "symvar")).free_symbols
        return [CellArray.from_rows([[SymValue(eng().symbol(n)) for n in names]])]

    def matlab_function(args: list, nargout: int) -> list:
        """matlabFunction(f) / matlabFunction(f, 'Vars', {x, y}): an anonymous function handle
        with element-wise operators; inputs default to symvar(f) in alphabetical order."""
        _need("matlabFunction", args, 1, 3)
        expr = eng().as_symexpr(_arg(args[0], "matlabFunction"))
        names = sorted(expr.free_symbols)
        if len(args) > 1:
            if len(args) != 3 or not (isinstance(args[1], CharArray)
                                      and args[1].to_str().lower() == "vars"):
                raise NotSupportedError("matlabFunction: only the 'Vars' option is supported.")
            spec = args[2]
            items = list(spec.data.ravel(order="F")) if isinstance(spec, CellArray) else [spec]
            names = [str(_arg(v, "matlabFunction")) for v in items]
            missing = set(expr.free_symbols) - set(names)
            if missing:
                raise ValidationError("matlabFunction: 'Vars' must list every variable; missing "
                                      + ", ".join(sorted(missing)) + ".")
        code = eng().to_matlab_code(expr)
        program = parse(f"__mf = @({', '.join(names)}) {code};", "<matlabFunction>")
        node = program.body[0].value  # the AnonFunc
        return [FunctionHandle(params=node.params, body=node.body, captured={})]

    # -- overloads of existing numeric builtins ------------------------------------------------
    functions = interp.functions
    numeric_diff = functions.get("diff")
    if numeric_diff is None:
        raise ValidationError("install_sym must run after install_core.")

    def overload(name: str, wanted, convert) -> Builtin | None:
        original = functions.get(name)
        if original is None:
            return None

        def run(args: list, nargout: int) -> list:
            if wanted(args):
                return convert(args)
            return original(args, nargout)

        return run

    def elementary(name: str) -> Builtin | None:
        def convert(args: list) -> list:
            if len(args) != 1:
                raise ValidationError(f"{name}: expected exactly one argument.")
            return [SymValue(eng().apply_function(name, args[0].expr))]

        return overload(name, lambda a: bool(a) and isinstance(a[0], SymValue), convert)

    def to_double(args: list) -> list:
        value = args[0]
        if isinstance(value, SymValue):
            return [np.array([[_numeric(value, "double")]])]
        data = value.data
        numbers = [_numeric(v, "double") for v in data.ravel(order="F")]
        out = np.array(numbers, dtype=complex if any(isinstance(n, complex) for n in numbers)
                       else float)
        return [out.reshape(data.shape, order="F")]

    def has_sym(args: list) -> bool:
        if not args:
            return False
        a = args[0]
        return isinstance(a, SymValue) or (
            isinstance(a, CellArray) and any(isinstance(v, SymValue) for v in a.data.ravel()))

    def show(args: list) -> list:
        if isinstance(args[0], LtiValue):
            from engstudio.lang.builtins_control import lti_text

            host.write(" \n" + lti_text(args[0]) + "\n\n")
            return []
        host.write(sym_text(args[0]) + "\n")
        return []

    table: dict[str, Builtin] = {
        "syms": syms, "sym": sym, "int": integral, "limit": limit, "taylor": taylor,
        "solve": solve, "simplify": transform1("simplify", "simplify"),
        "expand": transform1("expand", "expand"), "factor": transform1("factor", "factor"),
        "subs": subs, "laplace": transform_pair("laplace", True),
        "ilaplace": transform_pair("ilaplace", False), "latex": latex, "symvar": symvar,
        "matlabFunction": matlab_function,
        "diff": diff,
    }
    extra = {
        "double": overload("double", has_sym, to_double),
        "char": overload("char", lambda a: bool(a) and isinstance(a[0], SymValue),
                         lambda a: [CharArray.from_str(sym_text(a[0]))]),
        "disp": overload("disp", lambda a: len(a) == 1 and isinstance(a[0], (SymValue, LtiValue)),
                         show),
    }
    for fn_name in _ELEMENTARY:
        extra[fn_name] = elementary(fn_name)
    table.update({k: v for k, v in extra.items() if v is not None})
    return table


def install_sym(interp: Interpreter) -> None:
    """Register the symbolic builtins on ``interp`` (after ``install_core``)."""
    interp.functions.update(sym_functions(interp))
