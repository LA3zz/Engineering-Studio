"""Mechanical vibrations: single-degree-of-freedom (SDOF) systems and multi-degree-of-freedom
(MDOF) modal analysis. Model: m x'' + c x' + k x = F(t). Units SI (kg, N*s/m, N/m, rad/s);
frequencies are returned in rad/s (w*) and Hz (f*). Torsional systems work the same way with
J, ct, kt in place of m, c, k.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import scipy.linalg

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

__all__ = ["log_decrement", "modes", "sdof", "sdof_forced", "sdof_free", "transmissibility"]

CAT = "mechanical"


@dataclass(frozen=True)
class Sdof:
    wn: float  # natural frequency, rad/s
    fn: float  # Hz
    Tn: float  # natural period, s
    zeta: float  # damping ratio
    wd: float  # damped natural frequency, rad/s (0 if not underdamped)
    fd: float
    ccr: float  # critical damping coefficient
    regime: str  # 'undamped' | 'underdamped' | 'critically damped' | 'overdamped'


@tb_function("sdof", CAT, args=[Arg("m", unit="kg", positive=True),
                                 Arg("c", unit="N*s/m", nonnegative=True),
                                 Arg("k", unit="N/m", positive=True)], returns=[Ret("props")])
def sdof(m: float, c: float, k: float) -> Sdof:
    """Natural frequency, damping ratio, damped frequency and regime of m x'' + c x' + k x = 0."""
    wn = math.sqrt(k / m)
    ccr = 2 * math.sqrt(k * m)
    zeta = c / ccr
    if zeta == 0:
        regime = "undamped"
    elif abs(zeta - 1) < 1e-12:
        regime = "critically damped"
    elif zeta < 1:
        regime = "underdamped"
    else:
        regime = "overdamped"
    wd = wn * math.sqrt(1 - zeta ** 2) if zeta < 1 else 0.0
    return Sdof(wn, wn / (2 * math.pi), 2 * math.pi / wn, zeta, wd, wd / (2 * math.pi), ccr,
                regime)


@tb_function("sdof_free", CAT, args=[Arg("m", unit="kg", positive=True),
                                      Arg("c", unit="N*s/m", nonnegative=True),
                                      Arg("k", unit="N/m", positive=True), Arg("x0", unit="m"),
                                      Arg("v0", unit="m/s"), Arg("t", unit="s")],
             returns=[Ret("x", unit="m"), Ret("v", unit="m/s")])
def sdof_free(m: float, c: float, k: float, x0: float, v0: float,
              t: np.ndarray | float) -> tuple[np.ndarray, np.ndarray]:
    """Exact free response x(t), v(t) from x(0) = x0, x'(0) = v0 (all damping regimes)."""
    t = np.asarray(t, dtype=float)
    p = sdof(m, c, k)
    wn, z = p.wn, p.zeta
    if z < 1 - 1e-12:
        wd = p.wd
        e = np.exp(-z * wn * t)
        A, B = x0, (v0 + z * wn * x0) / wd
        x = e * (A * np.cos(wd * t) + B * np.sin(wd * t))
        v = e * ((-z * wn * A + wd * B) * np.cos(wd * t) + (-z * wn * B - wd * A) * np.sin(wd * t))
    elif z <= 1 + 1e-12:
        e = np.exp(-wn * t)
        A, B = x0, v0 + wn * x0
        x = e * (A + B * t)
        v = e * (B - wn * (A + B * t))
    else:
        s = wn * math.sqrt(z ** 2 - 1)
        r1, r2 = -z * wn + s, -z * wn - s
        C1 = (v0 - r2 * x0) / (r1 - r2)
        C2 = x0 - C1
        x = C1 * np.exp(r1 * t) + C2 * np.exp(r2 * t)
        v = C1 * r1 * np.exp(r1 * t) + C2 * r2 * np.exp(r2 * t)
    return x, v


@dataclass(frozen=True)
class Forced:
    X: float  # steady-state amplitude
    phase: float  # lag of x behind the force, degrees (0..180)
    r: float  # frequency ratio w/wn
    MF: float  # magnification factor X / (F0/k)
    TR: float  # force transmissibility to the base
    X_static: float  # F0 / k


@tb_function("sdof_forced", CAT, args=[Arg("m", unit="kg", positive=True),
                                        Arg("c", unit="N*s/m", nonnegative=True),
                                        Arg("k", unit="N/m", positive=True),
                                        Arg("F0", unit="N"), Arg("w", unit="rad/s",
                                                                 nonnegative=True)],
             returns=[Ret("result")])
def sdof_forced(m: float, c: float, k: float, F0: float, w: float) -> Forced:
    """Steady-state response to F0 cos(w t): amplitude, phase lag, magnification factor and
    transmitted-force ratio."""
    p = sdof(m, c, k)
    r, z = w / p.wn, p.zeta
    den = math.hypot(1 - r ** 2, 2 * z * r)
    if den == 0:
        raise ValidationError("sdof_forced: undamped system excited at resonance (infinite "
                              "amplitude)")
    mf = 1 / den
    phase = math.degrees(math.atan2(2 * z * r, 1 - r ** 2))
    return Forced(abs(F0) / k * mf, phase, r, mf, transmissibility(z, r), F0 / k)


@tb_function("transmissibility", CAT, args=[Arg("zeta", nonnegative=True),
                                             Arg("r", nonnegative=True)],
             returns=[Ret("TR")])
def transmissibility(zeta: float | np.ndarray, r: float | np.ndarray) -> float | np.ndarray:
    """Displacement/force transmissibility sqrt(1+(2 zeta r)^2) / sqrt((1-r^2)^2+(2 zeta r)^2).
    ``r`` may be a vector (for plots)."""
    zeta, r = np.asarray(zeta, dtype=float), np.asarray(r, dtype=float)
    with np.errstate(divide="ignore"):
        out = np.sqrt(1 + (2 * zeta * r) ** 2) / np.sqrt((1 - r ** 2) ** 2 + (2 * zeta * r) ** 2)
    return float(out) if out.ndim == 0 else out


@dataclass(frozen=True)
class Decrement:
    delta: float  # logarithmic decrement
    zeta: float


@tb_function("log_decrement", CAT, args=[Arg("x1"), Arg("xn"), Arg("n", positive=True,
                                                                     integer=True)],
             returns=[Ret("result")])
def log_decrement(x1: float, xn: float, n: int = 1) -> Decrement:
    """Damping from two peaks n cycles apart: delta = ln(x1/x(1+n)) / n,
    zeta = delta / sqrt(4 pi^2 + delta^2)."""
    if x1 <= 0 or xn <= 0 or xn >= x1:
        raise ValidationError("log_decrement: need peak amplitudes 0 < xn < x1")
    delta = math.log(x1 / xn) / n
    return Decrement(delta, delta / math.sqrt(4 * math.pi ** 2 + delta ** 2))


@dataclass(frozen=True)
class Modes:
    wn: np.ndarray  # natural frequencies, rad/s (ascending; 0 for rigid-body modes)
    fn: np.ndarray  # Hz
    shapes: np.ndarray  # columns = mode shapes, largest component scaled to 1
    shapes_mass: np.ndarray  # mass-normalised (phi' M phi = I)


@tb_function("modes", CAT, args=[Arg("M", shape=(None, None)), Arg("K", shape=(None, None))],
             returns=[Ret("result")])
def modes(M: np.ndarray, K: np.ndarray) -> Modes:
    """Undamped modal analysis of M x'' + K x = 0: generalized symmetric eigenproblem
    K phi = w^2 M phi. M must be symmetric positive definite, K symmetric (semi-definite
    allowed: rigid-body modes give w = 0)."""
    if M.shape != K.shape or M.shape[0] != M.shape[1]:
        raise DimensionError("modes: M and K must be square matrices of the same size")
    for name, A in (("M", M), ("K", K)):
        if not np.allclose(A, A.T, rtol=1e-10, atol=1e-12 * max(1.0, float(np.abs(A).max()))):
            raise ValidationError(f"modes: {name} must be symmetric")
    try:
        lam, phi = scipy.linalg.eigh(K, M)
    except np.linalg.LinAlgError:
        raise ValidationError("modes: M must be positive definite") from None
    scale = max(1.0, float(np.abs(lam).max()))
    lam = np.where(np.abs(lam) < 1e-10 * scale, 0.0, lam)
    if np.any(lam < 0):
        raise ValidationError("modes: K has negative eigenvalues (unstable system)")
    wn = np.sqrt(lam)
    shapes = phi.copy()
    for j in range(shapes.shape[1]):
        col = shapes[:, j]
        shapes[:, j] = col / col[int(np.argmax(np.abs(col)))]
    return Modes(wn, wn / (2 * math.pi), shapes, phi)
