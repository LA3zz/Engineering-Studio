"""Simulation runner (Phase 7, S6): runs a compiled model and logs its signals.

Time is split into segments at discrete sample hits and at block breakpoints (Step/Pulse
edges), so solvers never step across a jump. Inside a segment the continuous states are
advanced one accepted step at a time with SciPy's solver classes (variable step) or with
fixed-step RK4/Euler. After every accepted step the outputs are evaluated in compiled order,
the signals arriving at sinks are logged, and memory blocks get ``after_step``. At a sample
hit discrete blocks ``sample`` their input, outputs are logged, then discrete states
``update``.

Solvers: ode45 -> RK45 (Dormand-Prince, as MATLAB), ode23 -> RK23 (Bogacki-Shampine), ode15s
-> BDF, ode113 -> LSODA (Adams/BDF switching; MATLAB's ode113 is Adams only), rk4/euler fixed
step. Default maximum step: (stop - start)/50, as Simulink. Models without continuous states
are evaluated on a grid of MaxStep (or FixedStep) between hits.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import BDF, LSODA, RK23, RK45

from engstudio.core.errors import EngStudioError, ValidationError
from engstudio.sim.compiler import CompiledModel, compile_model
from engstudio.sim.model import Model

__all__ = ["ScopeData", "SimResult", "SimulationCancelled", "run"]

_METHODS = {"ode45": RK45, "ode23": RK23, "ode15s": BDF, "ode113": LSODA}
_MAX_POINTS = 2_000_000


class SimulationCancelled(EngStudioError):
    code = "E_CANCELLED"


@dataclass
class ScopeData:
    title: str
    t: np.ndarray
    signals: list[np.ndarray]  # one (n, width) array per input


@dataclass
class SimResult:
    tout: np.ndarray
    scopes: dict[str, ScopeData] = field(default_factory=dict)
    workspace: dict[str, np.ndarray] = field(default_factory=dict)  # ToWorkspace variables
    outports: dict[int, np.ndarray] = field(default_factory=dict)  # top-level Outports
    displays: dict[str, np.ndarray] = field(default_factory=dict)  # final values
    steps: int = 0
    status: str = "ok"


class _Engine:
    def __init__(self, c: CompiledModel) -> None:
        self.c = c
        self.blocks = c.blocks
        self.sinks = [i for i, b in enumerate(self.blocks) if b.n_out == 0 and b.n_in > 0]
        self.t_log: list[float] = []
        self.sink_log: dict[int, list[list[np.ndarray]]] = {i: [] for i in self.sinks}

    def outputs(self, t: float, x: np.ndarray, hits: frozenset[int] = frozenset()
                ) -> tuple[list[list[np.ndarray]], list[list[np.ndarray]]]:
        """(outputs per block, inputs per block) at time t and state x."""
        # Pass 1: outputs in compiled order. Only direct-feedthrough blocks read their inputs
        # here (their sources come earlier); the others depend on state/memory only.
        outs: list[list[np.ndarray]] = [[] for _ in self.blocks]
        for i, b in enumerate(self.blocks):
            u = [outs[src][port] for src, port in b.inputs] if b.feedthrough else []
            if i in hits and b.feedthrough:
                b.impl.sample(t, u)
            outs[i] = [np.atleast_1d(np.asarray(v, dtype=float))
                       for v in b.impl.outputs(t, x[b.state], u)]
        # Pass 2: every block's inputs (for derivatives, logging and discrete updates).
        ins = [[outs[src][port] for src, port in b.inputs] for b in self.blocks]
        for i in hits:
            if not self.blocks[i].feedthrough:
                self.blocks[i].impl.sample(t, ins[i])
        return outs, ins

    def derivatives(self, t: float, x: np.ndarray) -> np.ndarray:
        outs, ins = self.outputs(t, x)
        dx = np.empty_like(x)
        for b, u in zip(self.blocks, ins, strict=True):
            if b.impl.n_states:
                dx[b.state] = b.impl.derivatives(t, x[b.state], u)
        return dx

    def log(self, t: float, ins: list[list[np.ndarray]]) -> None:
        if self.t_log and t == self.t_log[-1]:  # same instant (hit after a step): replace
            self.t_log.pop()
            for i in self.sinks:
                self.sink_log[i].pop()
        self.t_log.append(t)
        for i in self.sinks:
            self.sink_log[i].append([np.array(v, copy=True) for v in ins[i]])
        if len(self.t_log) > _MAX_POINTS:
            raise ValidationError("simulation produced more than 2 million output points; "
                                  "increase MaxStep or shorten the stop time")

    def accept(self, t: float, x: np.ndarray, hits: frozenset[int] = frozenset()) -> None:
        outs, ins = self.outputs(t, x, hits)
        self.log(t, ins)
        for b, u in zip(self.blocks, ins, strict=True):
            b.impl.after_step(t, x[b.state], u)
        for i in hits:
            self.blocks[i].impl.update(t, ins[i])


def _hit_times(c: CompiledModel, t0: float, t1: float) -> dict[float, set[int]]:
    hits: dict[float, set[int]] = {}
    for i, b in enumerate(c.blocks):
        ts = b.impl.sample_time
        if not ts:
            continue
        n = math.floor((t1 - t0) / ts + 1e-9)
        if n > _MAX_POINTS:
            raise ValidationError(f"block {b.id}: sample time {ts:g} gives too many samples")
        for k in range(n + 1):
            hits.setdefault(round(t0 + k * ts, 12), set()).add(i)
    return hits


def run(model: Model | CompiledModel, progress: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None) -> SimResult:
    """Simulate ``model``; ``progress(fraction)`` is called now and then and
    ``should_stop()`` is polled every step (True cancels: ``SimulationCancelled``)."""
    c = model if isinstance(model, CompiledModel) else compile_model(model)
    s = c.model.settings
    t0, tf = s.start_time, s.stop_time
    eng = _Engine(c)
    max_step = s.max_step if math.isfinite(s.max_step) else (tf - t0) / 50
    delays = [b.params["DelayTime"] for b in c.blocks if b.type == "TransportDelay"]
    if delays:
        max_step = min(max_step, min(delays))  # type: ignore[type-var]
    hits = _hit_times(c, t0, tf)
    bounds = sorted({*hits, *c.breakpoints(t0, tf), tf} - {t0})
    bounds = [b for b in bounds if t0 < b <= tf]
    x = c.x0.copy()
    steps = 0

    def check(t: float) -> None:
        if should_stop is not None and should_stop():
            raise SimulationCancelled("Simulation stopped by the user.")
        if progress is not None and steps % 50 == 0:
            progress((t - t0) / (tf - t0))

    eng.accept(t0, x, frozenset(hits.get(round(t0, 12), ())))
    t = t0
    for te in bounds:
        if te <= t:
            continue
        if c.n_states and s.solver in _METHODS:
            solver = _METHODS[s.solver](eng.derivatives, t, x, te, max_step=max_step,
                                        rtol=s.rel_tol, atol=s.abs_tol)
            while solver.status == "running":
                msg = solver.step()
                if solver.status == "failed":
                    raise ValidationError(f"solver {s.solver} failed at t = {solver.t:g}: "
                                          f"{msg}")
                t, x = solver.t, np.array(solver.y)
                steps += 1
                check(t)
                eng.accept(t, x)
        else:
            h_nom = s.fixed_step if s.solver in ("rk4", "euler") else max_step
            while t < te - 1e-12 * max(1.0, abs(te)):
                h = min(h_nom, te - t)
                if c.n_states:
                    x = _fixed_step(eng.derivatives, t, x, h, s.solver)
                t = t + h if te - (t + h) > 1e-12 * max(1.0, abs(te)) else te
                steps += 1
                check(t)
                eng.accept(t, x)
        t = te
        hit = frozenset(hits.get(round(te, 12), ()))
        if hit:
            eng.accept(te, x, hit)
    if progress is not None:
        progress(1.0)
    return _result(eng, steps)


def _fixed_step(f, t: float, x: np.ndarray, h: float, method: str) -> np.ndarray:
    if method == "euler":
        return x + h * f(t, x)
    k1 = f(t, x)
    k2 = f(t + h / 2, x + h / 2 * k1)
    k3 = f(t + h / 2, x + h / 2 * k2)
    k4 = f(t + h, x + h * k3)
    return x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)


def _stack(rows: list[np.ndarray]) -> np.ndarray:
    width = max(r.size for r in rows) if rows else 1
    out = np.full((len(rows), width), np.nan)
    for k, r in enumerate(rows):
        out[k, :r.size] = r
    return out


def _result(eng: _Engine, steps: int) -> SimResult:
    res = SimResult(np.array(eng.t_log), steps=steps)
    for i in eng.sinks:
        b = eng.blocks[i]
        log = eng.sink_log[i]
        per_input = [_stack([row[k] for row in log]) for k in range(b.n_in)]
        if b.type == "Scope":
            res.scopes[b.id] = ScopeData(str(b.params.get("Title") or b.name), res.tout,
                                         per_input)
        elif b.type == "ToWorkspace":
            res.workspace[str(b.params["VariableName"])] = per_input[0]
        elif b.type == "Outport":
            res.outports[int(b.params["Port"])] = per_input[0]
        elif b.type == "Display":
            res.displays[b.id] = per_input[0][-1]
    return res
