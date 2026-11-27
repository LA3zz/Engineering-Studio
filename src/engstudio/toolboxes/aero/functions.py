"""Aerospace: ISA standard atmosphere, airspeed/Mach, lift and drag, stall speed, Breguet range
and endurance, rocket equation, and orbital mechanics (circular/escape speeds, Kepler period,
Hohmann transfer). SI units."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "aerospace"
G0 = 9.80665
R_AIR, GAMMA = 287.05287, 1.4
MU_EARTH = 3.986004418e14  # m^3/s^2
R_EARTH = 6.371e6


@tb_function("atmosisa", CAT, args=[Arg("h", unit="m")],
             returns=[Ret("T", unit="K"), Ret("a", unit="m/s"), Ret("p", unit="Pa"),
                      Ret("rho", unit="kg/m^3")])
def atmosisa(h: np.ndarray | float) -> tuple:
    """International Standard Atmosphere (geopotential altitude 0-84 km), as MATLAB's
    [T, a, P, rho] = atmosisa(h)."""
    layers = [(0, 288.15, -0.0065, 101325.0), (11000, 216.65, 0.0, 22632.06),
              (20000, 216.65, 0.001, 5474.889), (32000, 228.65, 0.0028, 868.0187),
              (47000, 270.65, 0.0, 110.9063), (51000, 270.65, -0.0028, 66.93887),
              (71000, 214.65, -0.002, 3.956420), (84852, 186.946, 0.0, 0.3734)]
    hh = np.atleast_1d(np.asarray(h, float))
    if np.any(hh < -2000) or np.any(hh > 86000):
        raise ValidationError("atmosisa: altitude must be between -2 km and 86 km")
    T, p = np.empty_like(hh), np.empty_like(hh)
    for k, x in enumerate(hh):
        hb, Tb, L, pb = next(ly for ly in reversed(layers) if x >= ly[0] or ly is layers[0])
        T[k] = Tb + L * (x - hb)
        p[k] = (pb * (T[k] / Tb) ** (-G0 / (L * R_AIR)) if L else
                pb * math.exp(-G0 * (x - hb) / (R_AIR * Tb)))
    rho = p / (R_AIR * T)
    a = np.sqrt(GAMMA * R_AIR * T)
    out = (T, a, p, rho)
    return tuple(float(v[0]) for v in out) if np.ndim(h) == 0 else out


@dataclass(frozen=True)
class Airspeed:
    mach: float
    q: float  # dynamic pressure, Pa
    eas: float  # equivalent airspeed, m/s
    T0: float  # stagnation temperature, K
    p0: float  # stagnation (pitot) pressure, Pa


@tb_function("airspeed", CAT, args=[Arg("V", unit="m/s", nonnegative=True),
                                     Arg("h", unit="m")], returns=[Ret("result")])
def airspeed(V: float, h: float = 0.0) -> Airspeed:
    """Mach number, dynamic pressure, EAS and isentropic stagnation conditions at altitude h."""
    T, a, p, rho = atmosisa(h)
    M = V / a
    k = 1 + (GAMMA - 1) / 2 * M * M
    return Airspeed(M, 0.5 * rho * V * V, V * math.sqrt(rho / 1.225), T * k,
                    p * k ** (GAMMA / (GAMMA - 1)))


@tb_function("lift_drag", CAT, args=[
    Arg("V", unit="m/s", nonnegative=True), Arg("S", unit="m^2", positive=True),
    Arg("CL"), Arg("CD0", nonnegative=True), Arg("AR", positive=True),
    Arg("e", positive=True, max=1.0), Arg("rho", unit="kg/m^3", positive=True)],
    returns=[Ret("L", unit="N"), Ret("D", unit="N"), Ret("CD")])
def lift_drag(V: float, S: float, CL: float, CD0: float = 0.02, AR: float = 8.0,
              e: float = 0.8, rho: float = 1.225) -> tuple[float, float, float]:
    """Lift and drag with the parabolic drag polar CD = CD0 + CL^2/(pi e AR)."""
    cd = CD0 + CL * CL / (math.pi * e * AR)
    q = 0.5 * rho * V * V
    return q * S * CL, q * S * cd, cd


@tb_function("stall_speed", CAT, args=[Arg("W", unit="N", positive=True),
                                        Arg("S", unit="m^2", positive=True),
                                        Arg("CLmax", positive=True),
                                        Arg("rho", unit="kg/m^3", positive=True)],
             returns=[Ret("Vs", unit="m/s")])
def stall_speed(W: float, S: float, CLmax: float, rho: float = 1.225) -> float:
    """Level-flight stall speed sqrt(2 W / (rho S CLmax))."""
    return math.sqrt(2 * W / (rho * S * CLmax))


@tb_function("breguet", CAT, args=[
    Arg("kind", choices=("jet-range", "jet-endurance", "prop-range", "prop-endurance")),
    Arg("LD", positive=True), Arg("W0", positive=True), Arg("W1", positive=True),
    Arg("c", positive=True), Arg("V", unit="m/s", positive=True, optional=True),
    Arg("eta", positive=True, max=1.0, optional=True)],
    returns=[Ret("value")])
def breguet(kind: str, LD: float, W0: float, W1: float, c: float, V: float | None = None,
            eta: float | None = None) -> float:
    """Breguet range (m) or endurance (s). Jets: c is TSFC in 1/s (range needs V). Propeller:
    c is SFC in 1/m (BSFC * g / ... in consistent units), range needs eta."""
    if W1 >= W0:
        raise ValidationError("breguet: the final weight W1 must be below W0")
    ln = math.log(W0 / W1)
    if kind == "jet-range":
        if V is None:
            raise ValidationError("breguet: jet range needs the cruise speed V")
        return V / c * LD * ln
    if kind == "jet-endurance":
        return LD / c * ln
    if eta is None:
        raise ValidationError("breguet: propeller aircraft need the efficiency eta")
    if kind == "prop-range":
        return eta / c * LD * ln
    if V is None:
        raise ValidationError("breguet: propeller endurance needs V")
    return eta / (c * V) * LD * ln


@tb_function("rocket_dv", CAT, args=[Arg("Isp", unit="s", positive=True),
                                      Arg("m0", unit="kg", positive=True),
                                      Arg("mf", unit="kg", positive=True)],
             returns=[Ret("dv", unit="m/s")])
def rocket_dv(Isp: float, m0: float, mf: float) -> float:
    """Tsiolkovsky rocket equation dv = Isp g0 ln(m0/mf)."""
    if mf > m0:
        raise ValidationError("rocket_dv: the final mass cannot exceed the initial mass")
    return Isp * G0 * math.log(m0 / mf)


@dataclass(frozen=True)
class Orbit:
    v_circular: float  # m/s
    v_escape: float
    period: float  # s
    radius: float  # m


@tb_function("orbit", CAT, args=[Arg("h", unit="m", nonnegative=True),
                                  Arg("mu", positive=True), Arg("R", unit="m", positive=True)],
             returns=[Ret("result")])
def orbit(h: float, mu: float = MU_EARTH, R: float = R_EARTH) -> Orbit:
    """Circular orbit at altitude h above a body (default Earth): speed sqrt(mu/r), escape
    speed sqrt(2 mu/r), period 2 pi sqrt(r^3/mu)."""
    r = R + h
    return Orbit(math.sqrt(mu / r), math.sqrt(2 * mu / r), 2 * math.pi * math.sqrt(r ** 3 / mu),
                 r)


@dataclass(frozen=True)
class Hohmann:
    dv1: float
    dv2: float
    dv_total: float
    transfer_time: float  # s (half the transfer ellipse)


@tb_function("hohmann", CAT, args=[Arg("r1", unit="m", positive=True),
                                    Arg("r2", unit="m", positive=True),
                                    Arg("mu", positive=True)],
             returns=[Ret("result")])
def hohmann(r1: float, r2: float, mu: float = MU_EARTH) -> Hohmann:
    """Hohmann transfer between circular orbits of radii r1 and r2 (from the body's centre)."""
    at = (r1 + r2) / 2
    dv1 = abs(math.sqrt(mu / r1) * (math.sqrt(2 * r2 / (r1 + r2)) - 1))
    dv2 = abs(math.sqrt(mu / r2) * (1 - math.sqrt(2 * r1 / (r1 + r2))))
    return Hohmann(dv1, dv2, dv1 + dv2, math.pi * math.sqrt(at ** 3 / mu))


FUNCTIONS = (atmosisa, airspeed, lift_drag, stall_speed, breguet, rocket_dv, orbit, hohmann)
