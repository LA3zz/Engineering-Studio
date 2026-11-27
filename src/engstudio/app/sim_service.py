"""Simulation services for the model editor (Phase 7, S13-S16).

The GUI may only use ``sim.model``/``sim.serialization`` directly (layer rules), so this module
hands it plain data: the block library (``catalog``), port counts (``ports_of``), parameter
text <-> values (``parse_param``/``format_param``, MATLAB-style ``[1 2; 3 4]``, ``inf``,
``pi``), parameter checks (``check_block``), running a model (``run_model``) and Scope
figures (``scope_figures``).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec
from engstudio.sim.blocks import BLOCK_TYPES, ports, resolve
from engstudio.sim.compiler import load_library
from engstudio.sim.model import Block, Model
from engstudio.sim.runner import SimResult, run

__all__ = ["BlockInfo", "ParamInfo", "catalog", "check_block", "format_param", "parse_param",
           "ports_of", "run_model", "scope_figures"]


@dataclass(frozen=True)
class ParamInfo:
    name: str
    kind: str  # number | vector | matrix | text | choice
    default_text: str
    choices: tuple[str, ...]
    doc: str


@dataclass(frozen=True)
class BlockInfo:
    name: str
    category: str
    doc: str
    params: tuple[ParamInfo, ...]


def catalog() -> list[BlockInfo]:
    """Every block type, sorted by category then name (Subsystem ports excluded)."""
    load_library()
    out = []
    for bt in BLOCK_TYPES.values():
        params = tuple(ParamInfo(s.name, s.kind, format_param(s.default), s.choices, s.doc)
                       for s in bt.params)
        out.append(BlockInfo(bt.name, bt.category, bt.doc, params))
    order = ["Sources", "Sinks", "Math Operations", "Continuous", "Discrete",
             "Discontinuities", "Signal Routing", "User-Defined Functions",
             "Ports & Subsystems"]
    return sorted(out, key=lambda b: (order.index(b.category) if b.category in order else 99,
                                      b.name))


def ports_of(block: Block) -> tuple[int, int]:
    load_library()
    try:
        return ports(block)
    except ValidationError:
        return (1, 1) if block.type not in BLOCK_TYPES else (0, 0)


def check_block(block: Block) -> None:
    """Raise ValidationError if the block's parameters are invalid."""
    load_library()
    if block.subsystem is None:
        resolve(block)
    else:
        ports(block)


_NUM = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _number(tok: str) -> float:
    t = tok.strip().lower()
    sign = -1.0 if t.startswith("-") else 1.0
    core = t.lstrip("+-")
    if core in ("inf", "infinity"):
        return sign * math.inf
    if core == "pi":
        return sign * math.pi
    if _NUM.match(t):
        return float(t)
    raise ValidationError(f"{tok!r} is not a number")


def parse_param(kind: str, text: str) -> object:
    """Text typed in a parameter dialog -> model value for a parameter of ``kind``."""
    s = text.strip()
    if kind in ("text", "choice"):
        return s.strip("'\"")
    if kind == "number":
        return _number(s)
    body = s[1:-1] if s.startswith("[") and s.endswith("]") else s
    rows = [r for r in body.split(";") if r.strip()]
    if not rows:
        raise ValidationError("enter at least one number")
    values = [[_number(tok) for tok in re.split(r"[,\s]+", r.strip()) if tok] for r in rows]
    if kind == "vector":
        flat = [v for row in values for v in row]
        return flat[0] if len(flat) == 1 else flat
    if len({len(r) for r in values}) != 1:
        raise ValidationError("all matrix rows need the same number of values")
    return values


def _fmt(v: float) -> str:
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    return f"{v:g}"


def format_param(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return _fmt(float(value))
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return _fmt(float(arr))
    if arr.ndim == 1:
        return "[" + " ".join(_fmt(float(v)) for v in arr) + "]"
    return "[" + "; ".join(" ".join(_fmt(float(v)) for v in row) for row in arr) + "]"


def run_model(model: Model, progress: Callable[[float], None] | None = None,
              should_stop: Callable[[], bool] | None = None) -> SimResult:
    return run(model, progress=progress, should_stop=should_stop)


def scope_figures(result: SimResult, first_number: int = 1001) -> list[FigureSpec]:
    """One figure per Scope (lines per input/element, legend when several)."""
    figs = []
    for k, (scope_id, data) in enumerate(sorted(result.scopes.items())):
        series = []
        for i, sig in enumerate(data.signals):
            for j in range(sig.shape[1]):
                label = f"in{i + 1}" + (f"({j + 1})" if sig.shape[1] > 1 else "")
                series.append(SeriesSpec("line", data.t, sig[:, j], label=label))
        axes = AxesSpec(series=tuple(series), title=data.title or scope_id,
                        xlabel="Time (s)", grid=True, legend=len(series) > 1)
        figs.append(FigureSpec(number=first_number + k, axes=(axes,),
                               name=f"Scope: {data.title or scope_id}"))
    return figs
