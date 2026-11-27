"""Block library framework and math blocks (Phase 7, S2).

A ``BlockType`` describes a kind of block: its parameters (``ParamSpec`` with defaults and
checks), how many input/output ports it has (possibly depending on parameters, e.g. Sum with
signs '+-+'), whether its outputs depend directly on its inputs (direct feedthrough, needed
for sorting and algebraic-loop detection) and a factory for the runtime ``BlockImpl``.

Runtime contract (used by the compiler/runner, S5/S6): signals are 1-D float arrays (a scalar
is length 1). ``outputs(t, x, u)`` returns one array per output port from the time, the
block's continuous state slice ``x`` and its inputs ``u``; continuous blocks also implement
``derivatives(t, x, u)``. Parameters are resolved once (``resolve``): model values override
defaults and are checked, so a bad value is reported before a simulation starts.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.model import Block

__all__ = ["BLOCK_TYPES", "BlockImpl", "BlockType", "ParamSpec", "block_type", "ports",
           "register", "resolve"]

KINDS = ("source", "algebraic", "continuous", "discrete", "sink")


@dataclass(frozen=True)
class ParamSpec:
    name: str
    default: object
    kind: str = "number"  # number | vector | text | choice
    choices: tuple[str, ...] = ()
    positive: bool = False
    doc: str = ""

    def check(self, block: str, value: object) -> object:
        where = f"block {block}: parameter {self.name}"
        if self.kind == "number":
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValidationError(f"{where} must be a number, got {value!r}")
            v = float(value)
            if math.isnan(v):
                raise ValidationError(f"{where} must not be NaN")
            if self.positive and not v > 0:
                raise ValidationError(f"{where} must be positive")
            return v
        if self.kind == "vector":
            try:
                arr = np.atleast_1d(np.asarray(value, dtype=float))
            except (TypeError, ValueError):
                arr = np.array([np.nan])  # reported below
            if arr.ndim != 1 or arr.size == 0 or not np.all(np.isfinite(arr)):
                raise ValidationError(f"{where} must be a non-empty vector of finite numbers")
            return arr
        if not isinstance(value, str):
            raise ValidationError(f"{where} must be text, got {value!r}")
        if self.kind == "choice" and value not in self.choices:
            raise ValidationError(f"{where} must be one of {', '.join(self.choices)}")
        return value


class BlockImpl:
    """Runtime behaviour of one block instance (subclasses override what they need)."""

    n_states = 0

    def __init__(self, p: dict[str, object]) -> None:
        self.p = p

    def initial_state(self) -> np.ndarray:
        return np.zeros(self.n_states)

    def outputs(self, t: float, x: np.ndarray, u: list[np.ndarray]) -> list[np.ndarray]:
        raise NotImplementedError

    def derivatives(self, t: float, x: np.ndarray, u: list[np.ndarray]) -> np.ndarray:
        return np.zeros(0)


@dataclass(frozen=True)
class BlockType:
    name: str
    category: str
    kind: str
    params: tuple[ParamSpec, ...]
    n_inputs: Callable[[dict], int]
    n_outputs: Callable[[dict], int]
    feedthrough: bool  # outputs depend on inputs at the same instant
    impl: Callable[[dict], BlockImpl]
    doc: str = ""
    extra_check: Callable[[str, dict], None] | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValidationError(f"block type {self.name}: kind must be one of {KINDS}")


BLOCK_TYPES: dict[str, BlockType] = {}


def register(bt: BlockType) -> BlockType:
    if bt.name in BLOCK_TYPES:
        raise ValidationError(f"block type {bt.name} is already registered")
    BLOCK_TYPES[bt.name] = bt
    return bt


def block_type(name: str) -> BlockType:
    try:
        return BLOCK_TYPES[name]
    except KeyError:
        raise ValidationError(f"unknown block type {name!r}") from None


def resolve(block: Block) -> dict[str, object]:
    """Checked parameters of ``block``: defaults overridden by the model's values."""
    bt = block_type(block.type)
    specs = {s.name: s for s in bt.params}
    unknown = [k for k, _ in block.params if k not in specs]
    if unknown:
        raise ValidationError(f"block {block.id} ({bt.name}): unknown parameter(s) "
                              + ", ".join(unknown))
    given = dict(block.params)
    p = {name: s.check(block.id, given.get(name, s.default)) for name, s in specs.items()}
    if bt.extra_check is not None:
        bt.extra_check(block.id, p)
    return p


def ports(block: Block) -> tuple[int, int]:
    """(inputs, outputs) of ``block``."""
    bt = block_type(block.type)
    p = resolve(block)
    return bt.n_inputs(p), bt.n_outputs(p)


def _fixed(n: int) -> Callable[[dict], int]:
    return lambda p: n


# ----------------------------------------------------------------------------- math blocks
class _Constant(BlockImpl):
    def outputs(self, t, x, u):
        return [np.atleast_1d(np.asarray(self.p["Value"], dtype=float))]


class _Gain(BlockImpl):
    def outputs(self, t, x, u):
        return [np.asarray(self.p["K"], dtype=float) * u[0]]


def _signs(text: str) -> str:
    return text.replace("|", "")


class _Sum(BlockImpl):
    def outputs(self, t, x, u):
        out = np.zeros(1)
        for s, v in zip(_signs(self.p["Signs"]), u, strict=True):  # type: ignore[arg-type]
            out = out + v if s == "+" else out - v
        return [out]


class _Product(BlockImpl):
    def outputs(self, t, x, u):
        out = np.ones(1)
        for op, v in zip(self.p["Operations"], u, strict=True):  # type: ignore[arg-type]
            if op == "*":
                out = out * v
            else:
                with np.errstate(divide="ignore", invalid="ignore"):
                    out = out / v
        return [out]


class _Abs(BlockImpl):
    def outputs(self, t, x, u):
        return [np.abs(u[0])]


_MATH = {
    "exp": np.exp, "log": np.log, "log10": np.log10, "sqrt": np.sqrt,
    "square": np.square, "reciprocal": lambda v: 1 / v, "sin": np.sin, "cos": np.cos,
    "tan": np.tan, "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan, "sinh": np.sinh,
    "cosh": np.cosh, "tanh": np.tanh, "sign": np.sign,
}


class _MathFunction(BlockImpl):
    def outputs(self, t, x, u):
        with np.errstate(all="ignore"):
            return [_MATH[self.p["Function"]](u[0])]  # type: ignore[index]


def _check_signs(block: str, p: dict) -> None:
    s = _signs(p["Signs"])  # type: ignore[arg-type]
    if not s or set(s) - {"+", "-"}:
        raise ValidationError(f"block {block}: Signs must contain only + and - (e.g. '+-')")


def _check_ops(block: str, p: dict) -> None:
    s = p["Operations"]
    if not s or set(s) - {"*", "/"}:  # type: ignore[arg-type]
        raise ValidationError(f"block {block}: Operations must contain only * and / (e.g. '*/')")


register(BlockType("Constant", "Sources", "source", (ParamSpec("Value", 1.0, "vector"),),
                   _fixed(0), _fixed(1), False, _Constant, "Constant output value."))
register(BlockType("Gain", "Math Operations", "algebraic", (ParamSpec("K", 1.0, "vector"),),
                   _fixed(1), _fixed(1), True, _Gain, "Output = K * input (element-wise)."))
register(BlockType("Sum", "Math Operations", "algebraic", (ParamSpec("Signs", "++", "text"),),
                   lambda p: len(_signs(p["Signs"])), _fixed(1), True, _Sum,
                   "Adds or subtracts its inputs, one sign per input (e.g. '+-').", _check_signs))
register(BlockType("Product", "Math Operations", "algebraic",
                   (ParamSpec("Operations", "**", "text"),),
                   lambda p: len(p["Operations"]), _fixed(1), True, _Product,
                   "Multiplies or divides its inputs ('*' or '/' per input).", _check_ops))
register(BlockType("Abs", "Math Operations", "algebraic", (), _fixed(1), _fixed(1), True, _Abs,
                   "Absolute value."))
register(BlockType("MathFunction", "Math Operations", "algebraic",
                   (ParamSpec("Function", "exp", "choice", tuple(_MATH)),),
                   _fixed(1), _fixed(1), True, _MathFunction,
                   "Applies a function: " + ", ".join(_MATH) + "."))
