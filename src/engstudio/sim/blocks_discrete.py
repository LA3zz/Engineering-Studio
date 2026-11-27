"""Discrete-time blocks (Phase 7, S8): UnitDelay, ZeroOrderHold, DiscreteTransferFcn,
DiscreteIntegrator.

Each runs at its own ``SampleTime`` (seconds, offset 0). Between sample hits the outputs are
held. At a hit the runner first calls ``sample`` (Zero-Order Hold takes the new input), then
evaluates all outputs, then calls ``update`` (state update x[k+1]). Differences from Simulink:
no sample-time offsets and no inherited (-1) sample times yet; DiscreteIntegrator is
forward Euler only.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, BlockType, ParamSpec, register
from engstudio.sim.blocks_continuous import tf_to_ss

__all__ = ["DISCRETE_TYPES"]

_TS = ParamSpec("SampleTime", 0.1, positive=True, doc="seconds")


class _Discrete(BlockImpl):
    def __init__(self, p):
        super().__init__(p)
        self.sample_time = float(p["SampleTime"])

    def memory(self):
        return np.array(self.xd, copy=True)

    def restore(self, snapshot):
        self.xd = np.array(snapshot, copy=True)


class _UnitDelay(_Discrete):
    def __init__(self, p):
        super().__init__(p)
        self.xd = np.atleast_1d(p["InitialCondition"]).astype(float)

    def outputs(self, t, x, u):
        return [self.xd.copy()]

    def update(self, t, u):
        self.xd = np.atleast_1d(u[0]).astype(float).copy()


class _ZeroOrderHold(_Discrete):
    def __init__(self, p):
        super().__init__(p)
        self.xd = np.zeros(1)

    def sample(self, t, u):
        self.xd = np.atleast_1d(u[0]).astype(float).copy()

    def outputs(self, t, x, u):
        return [self.xd.copy()]


class _DiscreteTF(_Discrete):
    def __init__(self, p):
        super().__init__(p)
        self.A, self.B, self.C, self.D = tf_to_ss(p["Num"], p["Den"])
        self.xd = np.zeros(self.A.shape[0])
        self._u = np.zeros(1)

    def sample(self, t, u):
        self._u = np.atleast_1d(u[0]).astype(float)

    def outputs(self, t, x, u):
        return [self.C @ self.xd + self.D @ self._u[:1]]

    def update(self, t, u):
        self.xd = self.A @ self.xd + self.B @ np.atleast_1d(u[0]).astype(float)[:1]

    def memory(self):
        return (self.xd.copy(), self._u.copy())

    def restore(self, snapshot):
        self.xd, self._u = (np.array(s, copy=True) for s in snapshot)


class _DiscreteIntegrator(_Discrete):
    def __init__(self, p):
        super().__init__(p)
        self.xd = np.atleast_1d(p["InitialCondition"]).astype(float)
        self.k = float(p["Gain"])

    def outputs(self, t, x, u):
        return [self.xd.copy()]

    def update(self, t, u):  # forward Euler: y[k+1] = y[k] + K*T*u[k]
        self.xd = self.xd + self.k * self.sample_time * np.atleast_1d(u[0]).astype(float)


def _check_dtf(block: str, p: dict) -> None:
    try:
        tf_to_ss(p["Num"], p["Den"])
    except ValidationError as exc:
        raise ValidationError(f"block {block}: {exc}") from None


def _dtf_feedthrough(p: dict) -> bool:
    num = np.trim_zeros(np.asarray(p["Num"], dtype=float), "f")
    den = np.trim_zeros(np.asarray(p["Den"], dtype=float), "f")
    return num.size == den.size and num.size > 0


DISCRETE_TYPES = tuple(register(bt) for bt in (
    BlockType("UnitDelay", "Discrete", "discrete",
              (ParamSpec("InitialCondition", 0.0, "vector"), _TS),
              lambda p: 1, lambda p: 1, False, _UnitDelay,
              "Output = input of the previous sample (z^-1)."),
    BlockType("ZeroOrderHold", "Discrete", "discrete", (_TS,), lambda p: 1, lambda p: 1, True,
              _ZeroOrderHold, "Samples its input every SampleTime and holds it."),
    BlockType("DiscreteTransferFcn", "Discrete", "discrete",
              (ParamSpec("Num", [1.0], "vector"), ParamSpec("Den", [1.0, -0.5], "vector"), _TS),
              lambda p: 1, lambda p: 1, _dtf_feedthrough, _DiscreteTF,
              "Num(z)/Den(z), coefficients in descending powers of z.", _check_dtf),
    BlockType("DiscreteIntegrator", "Discrete", "discrete",
              (ParamSpec("Gain", 1.0), ParamSpec("InitialCondition", 0.0, "vector"), _TS),
              lambda p: 1, lambda p: 1, False, _DiscreteIntegrator,
              "Forward-Euler accumulator: y[k+1] = y[k] + Gain*T*u[k]."),
))
