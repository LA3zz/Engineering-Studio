"""Electrical circuits and electronics: resistor networks, dividers, RC/RL/RLC transients and
second-order parameters, AC impedance and power, three-phase power, op-amp gains, RC filters,
diode (Shockley), 555 timer. SI units (ohm, F, H, V, A, W, Hz)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "electrical"


@tb_function("resistors", CAT, args=[Arg("R", shape=(None,), positive=True),
                                      Arg("connection", choices=("series", "parallel"))],
             returns=[Ret("Req", unit="ohm")])
def resistors(R: np.ndarray, connection: str = "series") -> float:
    """Equivalent resistance of resistors in series (sum) or parallel (1/sum(1/R))."""
    return float(np.sum(R)) if connection == "series" else float(1 / np.sum(1 / R))


@tb_function("voltage_divider", CAT, args=[Arg("Vin", unit="V"), Arg("R1", positive=True),
                                            Arg("R2", positive=True),
                                            Arg("Rload", positive=True, optional=True)],
             returns=[Ret("Vout", unit="V")])
def voltage_divider(Vin: float, R1: float, R2: float, Rload: float | None = None) -> float:
    """Vout across R2 (optionally loaded by Rload in parallel with R2)."""
    r2 = R2 if Rload is None else R2 * Rload / (R2 + Rload)
    return Vin * r2 / (R1 + r2)


@dataclass(frozen=True)
class Rlc:
    wn: float  # undamped natural frequency, rad/s
    zeta: float
    alpha: float  # neper frequency, 1/s
    f0: float  # resonance, Hz
    Q: float  # quality factor
    bandwidth: float  # Hz
    response: str


@tb_function("rlc", CAT, args=[Arg("R", nonnegative=True), Arg("L", positive=True),
                                Arg("C", positive=True),
                                Arg("connection", choices=("series", "parallel"))],
             returns=[Ret("result")])
def rlc(R: float, L: float, C: float, connection: str = "series") -> Rlc:
    """Second-order RLC parameters: wn = 1/sqrt(LC); series zeta = R/2 sqrt(C/L), parallel
    zeta = 1/(2R) sqrt(L/C); Q = 1/(2 zeta), bandwidth = f0/Q."""
    wn = 1 / math.sqrt(L * C)
    if connection == "series":
        zeta = R / 2 * math.sqrt(C / L)
    else:
        if R == 0:
            raise ValidationError("rlc: a parallel RLC needs R > 0")
        zeta = 1 / (2 * R) * math.sqrt(L / C)
    q = math.inf if zeta == 0 else 1 / (2 * zeta)
    f0 = wn / (2 * math.pi)
    response = ("undamped" if zeta == 0 else "critically damped" if math.isclose(zeta, 1)
                else "underdamped" if zeta < 1 else "overdamped")
    return Rlc(wn, zeta, zeta * wn, f0, q, f0 / q if q != math.inf else 0.0, response)


@tb_function("rc_step", CAT, args=[Arg("R", positive=True), Arg("C", positive=True),
                                    Arg("V", unit="V"), Arg("t", unit="s"),
                                    Arg("V0", unit="V")],
             returns=[Ret("vC", unit="V"), Ret("i", unit="A")])
def rc_step(R: float, C: float, V: float, t: np.ndarray | float, V0: float = 0.0
            ) -> tuple[np.ndarray, np.ndarray]:
    """Capacitor charging from V0 towards V through R: vC = V + (V0 - V) e^(-t/RC)."""
    tt = np.atleast_1d(np.asarray(t, dtype=float))
    e = np.exp(-tt / (R * C))
    return V + (V0 - V) * e, (V - V0) / R * e


@tb_function("rl_step", CAT, args=[Arg("R", positive=True), Arg("L", positive=True),
                                    Arg("V", unit="V"), Arg("t", unit="s")],
             returns=[Ret("i", unit="A"), Ret("vL", unit="V")])
def rl_step(R: float, L: float, V: float, t: np.ndarray | float
            ) -> tuple[np.ndarray, np.ndarray]:
    """Current build-up in an RL circuit after a step V: i = V/R (1 - e^(-R t/L))."""
    tt = np.atleast_1d(np.asarray(t, dtype=float))
    e = np.exp(-R * tt / L)
    return V / R * (1 - e), V * e


@tb_function("impedance", CAT, args=[Arg("kind", choices=("R", "L", "C")),
                                      Arg("value", positive=True), Arg("f", unit="Hz",
                                                                       positive=True)],
             returns=[Ret("Z", unit="ohm")])
def impedance(kind: str, value: float, f: float) -> complex:
    """Complex impedance at frequency f: R, j w L or 1/(j w C)."""
    w = 2 * math.pi * f
    if kind == "R":
        return complex(value, 0)
    return complex(0, w * value) if kind == "L" else complex(0, -1 / (w * value))


@dataclass(frozen=True)
class AcPower:
    P: float  # real power, W
    Q: float  # reactive power, var
    S: float  # apparent power, VA
    pf: float  # power factor
    current: complex  # current phasor (rms), A


@tb_function("ac_power", CAT, args=[Arg("V", unit="V"), Arg("Z", complex_ok=True)],
             returns=[Ret("result")])
def ac_power(V: float, Z: complex) -> AcPower:
    """Power drawn by impedance Z from an rms voltage V (phase 0): S = V I*."""
    z = complex(Z)
    if z == 0:
        raise ValidationError("ac_power: Z must not be zero")
    i = V / z
    s = V * i.conjugate()
    return AcPower(s.real, s.imag, abs(s), s.real / abs(s) if abs(s) else 1.0, i)


@tb_function("three_phase_power", CAT, args=[Arg("VL", unit="V", positive=True),
                                              Arg("IL", unit="A", nonnegative=True),
                                              Arg("pf", min=-1.0, max=1.0)],
             returns=[Ret("P", unit="W"), Ret("Q", unit="W"), Ret("S", unit="W")])
def three_phase_power(VL: float, IL: float, pf: float = 1.0) -> tuple[float, float, float]:
    """Balanced three-phase: S = sqrt(3) VL IL, P = S pf, Q = S sin(acos pf)."""
    s = math.sqrt(3) * VL * IL
    return s * pf, s * math.sqrt(1 - pf ** 2), s


@tb_function("opamp_gain", CAT, args=[
    Arg("config", choices=("inverting", "noninverting", "follower", "differential")),
    Arg("Rf", positive=True, optional=True), Arg("Rin", positive=True, optional=True)],
    returns=[Ret("gain")])
def opamp_gain(config: str, Rf: float | None = None, Rin: float | None = None) -> float:
    """Ideal op-amp closed-loop gain: inverting -Rf/Rin, non-inverting 1 + Rf/Rin, follower 1,
    differential (matched resistors) Rf/Rin."""
    if config == "follower":
        return 1.0
    if Rf is None or Rin is None:
        raise ValidationError(f"opamp_gain: the {config} amplifier needs Rf and Rin")
    return {"inverting": -Rf / Rin, "noninverting": 1 + Rf / Rin,
            "differential": Rf / Rin}[config]


@tb_function("rc_filter", CAT, args=[Arg("R", positive=True), Arg("C", positive=True),
                                      Arg("kind", choices=("lowpass", "highpass")),
                                      Arg("f", unit="Hz", optional=True)],
             returns=[Ret("fc", unit="Hz"), Ret("H")])
def rc_filter(R: float, C: float, kind: str = "lowpass",
              f: np.ndarray | float | None = None) -> tuple[float, np.ndarray]:
    """First-order RC filter: cut-off fc = 1/(2 pi R C) and the complex response H(f)."""
    fc = 1 / (2 * math.pi * R * C)
    ff = np.atleast_1d(np.asarray(fc if f is None else f, dtype=float))
    s = 1j * ff / fc
    return fc, (1 / (1 + s) if kind == "lowpass" else s / (1 + s))


@tb_function("diode_current", CAT, args=[Arg("V", unit="V"), Arg("Is", unit="A",
                                                                  positive=True),
                                          Arg("n", positive=True), Arg("T", unit="K",
                                                                       positive=True)],
             returns=[Ret("I", unit="A")])
def diode_current(V: np.ndarray | float, Is: float = 1e-14, n: float = 1.0,
                  T: float = 300.0) -> np.ndarray | float:
    """Shockley diode equation I = Is (exp(V/(n VT)) - 1), VT = k T / q."""
    vt = 1.380649e-23 * T / 1.602176634e-19
    out = Is * np.expm1(np.asarray(V, dtype=float) / (n * vt))
    return float(out) if np.ndim(out) == 0 else out


@dataclass(frozen=True)
class Timer555:
    f: float  # Hz
    duty: float  # high fraction
    t_high: float
    t_low: float


@tb_function("timer555", CAT, args=[Arg("R1", positive=True), Arg("R2", positive=True),
                                     Arg("C", positive=True)], returns=[Ret("result")])
def timer555(R1: float, R2: float, C: float) -> Timer555:
    """Astable 555: t_high = ln2 (R1 + R2) C, t_low = ln2 R2 C."""
    th, tl = math.log(2) * (R1 + R2) * C, math.log(2) * R2 * C
    return Timer555(1 / (th + tl), th / (th + tl), th, tl)


FUNCTIONS = (resistors, voltage_divider, rlc, rc_step, rl_step, impedance, ac_power,
             three_phase_power, opamp_gain, rc_filter, diode_current, timer555)
