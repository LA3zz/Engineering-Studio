"""Simulation model as plain immutable data (Phase 7, S1). No numerics, no Qt.

A ``Model`` holds ``Block``s and ``Line``s (signal wires from an output port to an input port)
plus ``SolverSettings``. Edits return a new model (``add_block``, ``connect``, ...), so the
GUI can keep an undo history and the runner never sees a half-edited graph. Block types and
their ports/parameters are defined by the block library (``sim.blocks``, S2); this module only
checks the graph itself: unique block ids, lines between existing blocks, at most one line
into each input port. Ports are numbered from 1, as in Simulink.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

from engstudio.core.errors import ValidationError

__all__ = ["SOLVERS", "Block", "Line", "Model", "SolverSettings", "param_value"]

SOLVERS = ("ode45", "ode23", "ode15s", "ode113", "rk4", "euler")
_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

ParamValue = float | int | bool | str | tuple


def param_value(name: str, value: object) -> ParamValue:
    """Normalise a block parameter: number, bool, text, or (nested) tuple of numbers.
    Lists become tuples so blocks stay hashable/immutable; non-finite numbers are allowed
    only as +-inf (limits)."""
    if isinstance(value, bool | str):
        return value
    if isinstance(value, int | float):
        v = float(value)
        if math.isnan(v):
            raise ValidationError(f"parameter {name}: NaN is not allowed")
        return v
    if isinstance(value, list | tuple):
        return tuple(param_value(name, v) for v in value)
    raise ValidationError(f"parameter {name}: unsupported value {value!r}")


@dataclass(frozen=True)
class Block:
    """One block. ``params`` is a tuple of (name, value) pairs (use ``param``/``with_params``);
    ``position`` is the top-left corner on the canvas, ``size`` its width and height."""

    id: str
    type: str
    name: str = ""
    params: tuple[tuple[str, ParamValue], ...] = ()
    position: tuple[float, float] = (0.0, 0.0)
    size: tuple[float, float] = (60.0, 40.0)
    subsystem: Model | None = None  # inner model of a 'Subsystem' block

    def __post_init__(self) -> None:
        if not _ID.match(self.id):
            raise ValidationError(f"block id {self.id!r}: letters, digits and _ only")
        if not isinstance(self.type, str) or not self.type:
            raise ValidationError(f"block {self.id}: type must be a non-empty name")
        pairs = dict(self.params) if not isinstance(self.params, dict) else self.params
        object.__setattr__(self, "params", tuple(
            (str(k), param_value(str(k), v)) for k, v in pairs.items()))
        object.__setattr__(self, "name", str(self.name or self.id))
        for what, pair in (("position", self.position), ("size", self.size)):
            try:
                a, b = (float(v) for v in pair)
            except (TypeError, ValueError):
                raise ValidationError(f"block {self.id}: {what} must be two numbers") from None
            if not (math.isfinite(a) and math.isfinite(b)):
                raise ValidationError(f"block {self.id}: {what} must be finite")
            object.__setattr__(self, what, (a, b))
        if self.size[0] <= 0 or self.size[1] <= 0:
            raise ValidationError(f"block {self.id}: size must be positive")
        if (self.type == "Subsystem") != (self.subsystem is not None):
            raise ValidationError(f"block {self.id}: a Subsystem block needs an inner model "
                                  "and only Subsystem blocks have one")

    def param(self, name: str, default: object = None) -> object:
        for k, v in self.params:
            if k == name:
                return v
        return default

    def with_params(self, **changes: object) -> Block:
        merged = dict(self.params)
        merged.update(changes)
        return replace(self, params=tuple(merged.items()))


@dataclass(frozen=True)
class Line:
    """A wire from output port ``src_port`` of ``src`` to input port ``dst_port`` of ``dst``.
    ``points`` are optional bend points for drawing."""

    src: str
    src_port: int
    dst: str
    dst_port: int
    points: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        for name in ("src_port", "dst_port"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValidationError(f"line: {name} must be an integer >= 1, got {v!r}")
        object.__setattr__(self, "points", tuple(
            (float(x), float(y)) for x, y in self.points))


@dataclass(frozen=True)
class SolverSettings:
    start_time: float = 0.0
    stop_time: float = 10.0
    solver: str = "ode45"
    rel_tol: float = 1e-3
    abs_tol: float = 1e-6
    max_step: float = math.inf  # variable-step solvers
    fixed_step: float = 0.01  # rk4 / euler, and the default discrete rate

    def __post_init__(self) -> None:
        if self.solver not in SOLVERS:
            raise ValidationError(f"solver must be one of {', '.join(SOLVERS)}")
        for name in ("start_time", "stop_time", "rel_tol", "abs_tol", "max_step", "fixed_step"):
            object.__setattr__(self, name, float(getattr(self, name)))
        if not (math.isfinite(self.start_time) and math.isfinite(self.stop_time)):
            raise ValidationError("start and stop times must be finite")
        if self.stop_time <= self.start_time:
            raise ValidationError("stop time must be after the start time")
        for name in ("rel_tol", "abs_tol", "fixed_step", "max_step"):
            if not getattr(self, name) > 0:
                raise ValidationError(f"{name} must be positive")


@dataclass(frozen=True)
class Model:
    name: str = "untitled"
    blocks: tuple[Block, ...] = ()
    lines: tuple[Line, ...] = ()
    settings: SolverSettings = field(default_factory=SolverSettings)

    def __post_init__(self) -> None:
        blocks, lines = tuple(self.blocks), tuple(self.lines)
        ids = [b.id for b in blocks]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValidationError(f"duplicate block id(s): {', '.join(sorted(dup))}")
        known = set(ids)
        fed: set[tuple[str, int]] = set()
        for ln in lines:
            for end in (ln.src, ln.dst):
                if end not in known:
                    raise ValidationError(f"line refers to unknown block {end!r}")
            key = (ln.dst, ln.dst_port)
            if key in fed:
                raise ValidationError(f"input {ln.dst_port} of block {ln.dst} has two lines")
            fed.add(key)
        object.__setattr__(self, "blocks", blocks)
        object.__setattr__(self, "lines", lines)

    # -- queries ---------------------------------------------------------------
    def block(self, block_id: str) -> Block:
        for b in self.blocks:
            if b.id == block_id:
                return b
        raise ValidationError(f"no block {block_id!r}")

    def new_id(self, prefix: str) -> str:
        """First free id ``prefix1``, ``prefix2``, ... (prefix cleaned to a valid id)."""
        base = re.sub(r"\W", "_", prefix) or "block"
        if not base[0].isalpha() and base[0] != "_":
            base = "b_" + base
        used = {b.id for b in self.blocks}
        k = 1
        while f"{base}{k}" in used:
            k += 1
        return f"{base}{k}"

    def inputs_of(self, block_id: str) -> dict[int, tuple[str, int]]:
        """{input port: (source block, source port)}."""
        return {ln.dst_port: (ln.src, ln.src_port) for ln in self.lines if ln.dst == block_id}

    # -- edits (each returns a new model) -----------------------------------------
    def add_block(self, block: Block) -> Model:
        return replace(self, blocks=(*self.blocks, block))

    def remove_block(self, block_id: str) -> Model:
        self.block(block_id)
        return replace(self, blocks=tuple(b for b in self.blocks if b.id != block_id),
                       lines=tuple(ln for ln in self.lines
                                   if block_id not in (ln.src, ln.dst)))

    def update_block(self, block: Block) -> Model:
        self.block(block.id)
        return replace(self, blocks=tuple(block if b.id == block.id else b
                                          for b in self.blocks))

    def move_block(self, block_id: str, position: tuple[float, float]) -> Model:
        return self.update_block(replace(self.block(block_id), position=position))

    def set_params(self, block_id: str, **params: object) -> Model:
        return self.update_block(self.block(block_id).with_params(**params))

    def connect(self, src: str, src_port: int, dst: str, dst_port: int) -> Model:
        return replace(self, lines=(*self.lines, Line(src, src_port, dst, dst_port)))

    def disconnect(self, dst: str, dst_port: int) -> Model:
        return replace(self, lines=tuple(ln for ln in self.lines
                                         if (ln.dst, ln.dst_port) != (dst, dst_port)))

    def with_settings(self, **changes: object) -> Model:
        return replace(self, settings=replace(self.settings, **changes))
