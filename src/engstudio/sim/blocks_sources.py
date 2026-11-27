"""Source blocks (Phase 7, S3): Step, SineWave, Ramp, Clock, PulseGenerator, FromWorkspace.

Sources have no inputs. Times are in seconds and angular frequencies in rad/s (as Simulink's
Sine Wave). Blocks whose output jumps report ``breakpoints`` so the solver stops exactly there.

Differences from Simulink: FromWorkspace takes its data as the ``Data`` parameter (a matrix
whose first column is time); reading a workspace variable by name comes with the kernel
integration (S12). Pulse width is a percentage of the period, as in Simulink's time-based mode.
"""

from __future__ import annotations

import math

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, BlockType, ParamSpec, register

__all__ = ["SOURCE_TYPES"]


def _fixed(n: int):
    return lambda p: n


def _out(v: float | np.ndarray) -> list[np.ndarray]:
    return [np.atleast_1d(np.asarray(v, dtype=float))]


def _in(times: list[float], t0: float, t1: float) -> list[float]:
    return [t for t in times if t0 < t < t1]


class _Step(BlockImpl):
    def outputs(self, t, x, u):
        p = self.p
        return _out(p["Final"] if t >= p["StepTime"] else p["Initial"])

    def breakpoints(self, t0, t1):
        return _in([self.p["StepTime"]], t0, t1)  # type: ignore[list-item]


class _Sine(BlockImpl):
    def outputs(self, t, x, u):
        p = self.p
        return _out(p["Amplitude"] * math.sin(p["Frequency"] * t + p["Phase"]) + p["Bias"])


class _Ramp(BlockImpl):
    def outputs(self, t, x, u):
        p = self.p
        dt = max(0.0, t - p["StartTime"])
        return _out(p["InitialOutput"] + p["Slope"] * dt)

    def breakpoints(self, t0, t1):  # slope change
        return _in([self.p["StartTime"]], t0, t1)  # type: ignore[list-item]


class _Clock(BlockImpl):
    def outputs(self, t, x, u):
        return _out(t)


class _Pulse(BlockImpl):
    def _phase(self, t: float) -> tuple[float, float]:
        p = self.p
        period, delay = p["Period"], p["PhaseDelay"]
        return (t - delay) % period, period * p["PulseWidth"] / 100

    def outputs(self, t, x, u):
        p = self.p
        if t < p["PhaseDelay"]:
            return _out(0.0)
        pos, width = self._phase(t)
        return _out(p["Amplitude"] if pos < width else 0.0)

    def breakpoints(self, t0, t1):
        p = self.p
        period, delay = p["Period"], p["PhaseDelay"]
        width = period * p["PulseWidth"] / 100
        out: list[float] = []
        k = max(0, math.floor((t0 - delay) / period))
        while True:
            start = delay + k * period
            if start >= t1:
                break
            out += [start, start + width]
            k += 1
            if len(out) > 100_000:
                break
        return _in(out, t0, t1)


class _FromWorkspace(BlockImpl):
    def outputs(self, t, x, u):
        data = self.p["Data"]
        times, values = data[:, 0], data[:, 1:]  # type: ignore[index]
        return [np.array([np.interp(t, times, values[:, j]) for j in range(values.shape[1])])]


def _check_pulse(block: str, p: dict) -> None:
    if not 0 < p["PulseWidth"] < 100:
        raise ValidationError(f"block {block}: PulseWidth must be between 0 and 100 (%)")


def _check_data(block: str, p: dict) -> None:
    d = p["Data"]
    if d.shape[1] < 2 or d.shape[0] < 1:  # type: ignore[union-attr]
        raise ValidationError(f"block {block}: Data needs a time column and at least one "
                              "value column ([t y1 y2 ...])")
    if np.any(np.diff(d[:, 0]) <= 0):  # type: ignore[index]
        raise ValidationError(f"block {block}: Data times (first column) must increase")


SOURCE_TYPES = tuple(register(bt) for bt in (
    BlockType("Step", "Sources", "source",
              (ParamSpec("StepTime", 1.0), ParamSpec("Initial", 0.0), ParamSpec("Final", 1.0)),
              _fixed(0), _fixed(1), False, _Step,
              "Jumps from Initial to Final at StepTime."),
    BlockType("SineWave", "Sources", "source",
              (ParamSpec("Amplitude", 1.0), ParamSpec("Frequency", 1.0, doc="rad/s"),
               ParamSpec("Phase", 0.0, doc="rad"), ParamSpec("Bias", 0.0)),
              _fixed(0), _fixed(1), False, _Sine,
              "Amplitude*sin(Frequency*t + Phase) + Bias (Frequency in rad/s)."),
    BlockType("Ramp", "Sources", "source",
              (ParamSpec("Slope", 1.0), ParamSpec("StartTime", 0.0),
               ParamSpec("InitialOutput", 0.0)),
              _fixed(0), _fixed(1), False, _Ramp,
              "InitialOutput until StartTime, then rises with Slope."),
    BlockType("Clock", "Sources", "source", (), _fixed(0), _fixed(1), False, _Clock,
              "Outputs the simulation time."),
    BlockType("PulseGenerator", "Sources", "source",
              (ParamSpec("Amplitude", 1.0), ParamSpec("Period", 1.0, positive=True),
               ParamSpec("PulseWidth", 50.0, doc="% of period"), ParamSpec("PhaseDelay", 0.0)),
              _fixed(0), _fixed(1), False, _Pulse,
              "Rectangular pulses: Amplitude for PulseWidth % of each Period.", _check_pulse),
    BlockType("FromWorkspace", "Sources", "source",
              (ParamSpec("Data", [[0.0, 0.0], [1.0, 0.0]], "matrix"),),
              _fixed(0), lambda p: 1, False, _FromWorkspace,
              "Plays back [t y1 y2 ...] data, linearly interpolated, held after the end.",
              _check_data),
))
