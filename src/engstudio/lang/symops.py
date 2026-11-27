"""Operators on symbolic values (B2b-5): hooks called by the interpreter.

``binary_op``, ``unary_op``, ``transpose`` and ``build_matrix`` behave exactly like their
``lang.ops`` counterparts unless a ``SymValue`` is involved. Symbolic arithmetic supports
``+ - * / ^`` (and the element-wise spellings) with scalar numbers, and ``==`` which builds an
equation; every other operator raises ``NotSupportedError`` instead of guessing. SymPy is
reached only through ``engine.symbolic`` and imported on first use.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang import ops
from engstudio.lang.values import LtiValue, SymValue

__all__ = ["binary_op", "build_matrix", "number_of", "transpose", "unary_op"]

_ARITH = {"+": "+", "-": "-", "*": "*", ".*": "*", "/": "/", "./": "/", "^": "^", ".^": "^"}


def _engine():
    from engstudio.engine import symbolic

    return symbolic


def number_of(v: object) -> int | float | complex:
    """Python number from a 1-by-1 double (integral values become ``int``)."""
    if isinstance(v, np.ndarray) and v.shape == (1, 1) and v.dtype.kind in "fc":
        x = v[0, 0]
        if v.dtype.kind == "c":
            if x.imag != 0:
                return complex(x)
            x = x.real
        f = float(x)
        return int(f) if f.is_integer() and abs(f) < 1e15 else f
    raise ValidationError(
        "Symbolic operations support only scalar numbers (symbolic matrices and vectors are "
        "not supported yet).")


def _operand(v: object) -> object:
    return v.expr if isinstance(v, SymValue) else number_of(v)


_SYSTEM_OPS: dict[str, object] = {}  # filled by lang.builtins_control (no import cycle)


def register_system_ops(binary: object, unary: object) -> None:
    """Operators for control-system values; ``lang.builtins_control`` registers them."""
    _SYSTEM_OPS["binary"], _SYSTEM_OPS["unary"] = binary, unary


def _system_ops(kind: str):
    fn = _SYSTEM_OPS.get(kind)
    if fn is None:
        raise NotSupportedError("Control-system operators are not available (control "
                                "functions are not installed).")
    return fn


def binary_op(op: str, left: object, right: object, diags: list) -> object:
    if isinstance(left, LtiValue) or isinstance(right, LtiValue):
        return _system_ops("binary")(op, left, right)
    if not (isinstance(left, SymValue) or isinstance(right, SymValue)):
        return ops.binary_op(op, left, right, diags)
    eng = _engine()
    if op in _ARITH:
        return SymValue(eng.arith(_ARITH[op], _operand(left), _operand(right)))
    if op == "==":
        return SymValue(eng.equation(_operand(left), _operand(right)))
    raise NotSupportedError(f"Operator '{op}' is not supported for symbolic values.")


def unary_op(op: str, value: object) -> object:
    if isinstance(value, LtiValue):
        return _system_ops("unary")(op, value)
    if not isinstance(value, SymValue):
        return ops.unary_op(op, value)
    if op == "+":
        return value
    if op == "-":
        return SymValue(_engine().negate(value.expr))
    raise NotSupportedError(f"Operator '{op}' is not supported for symbolic values.")


def transpose(value: object, conjugate: bool) -> object:
    return value if isinstance(value, SymValue) else ops.transpose(value, conjugate)


def _has_sym(x: object) -> bool:
    if isinstance(x, (list, tuple)):
        return any(_has_sym(i) for i in x)
    return isinstance(x, SymValue)


def build_matrix(rows: object) -> object:
    if _has_sym(rows):
        raise NotSupportedError(
            "Vectors and matrices of symbolic values are not supported yet; use a cell array "
            "such as {a, b}.")
    return ops.build_matrix(rows)  # type: ignore[arg-type]
