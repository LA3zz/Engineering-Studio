"""Machine elements and mechanisms: helical springs, gear pairs, shafts, four-bar linkage."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

__all__ = ["fourbar", "gear_pair", "shaft_diameter", "shaft_power", "spring_helical"]

CAT = "mechanical"


@dataclass(frozen=True)
class Spring:
    k: float  # spring rate, N/m
    C: float  # spring index D/d
    Kw: float  # Wahl correction factor
    tau: float  # max shear stress at load F (0 if F not given), Pa
    deflection: float  # deflection at load F, m


@tb_function("spring_helical", CAT, args=[
    Arg("d", unit="m", positive=True), Arg("D", unit="m", positive=True),
    Arg("n", positive=True), Arg("G", unit="Pa", positive=True), Arg("F", unit="N")],
    returns=[Ret("result")])
def spring_helical(d: float, D: float, n: float, G: float, F: float = 0.0) -> Spring:
    """Helical compression spring: wire diameter d, mean coil diameter D, n active coils,
    shear modulus G. k = G d^4 / (8 D^3 n); tau = Kw 8 F D / (pi d^3)."""
    C = D / d
    if C <= 1:
        raise ValidationError("spring_helical: the mean diameter must exceed the wire diameter")
    k = G * d ** 4 / (8 * D ** 3 * n)
    kw = (4 * C - 1) / (4 * C - 4) + 0.615 / C
    return Spring(k, C, kw, kw * 8 * F * D / (math.pi * d ** 3), F / k)


@dataclass(frozen=True)
class GearPair:
    ratio: float  # N2 / N1 (speed reduction)
    d1: float  # pitch diameters, m
    d2: float
    center_distance: float
    w2: float  # output speed for input speed w1 (same units as w1)
    T2: float  # output torque for input torque T1 (ideal, no losses)


@tb_function("gear_pair", CAT, args=[
    Arg("N1", positive=True, integer=True), Arg("N2", positive=True, integer=True),
    Arg("module", unit="m", positive=True), Arg("w1"), Arg("T1", unit="N*m")],
    returns=[Ret("result")])
def gear_pair(N1: int, N2: int, module: float, w1: float = 0.0, T1: float = 0.0) -> GearPair:
    """Spur gear pair: pitch diameters d = m N, center distance, speed and torque ratio."""
    ratio = N2 / N1
    d1, d2 = module * N1, module * N2
    return GearPair(ratio, d1, d2, (d1 + d2) / 2, w1 / ratio, T1 * ratio)


@tb_function("shaft_power", CAT, args=[Arg("T", unit="N*m"), Arg("rpm")],
             returns=[Ret("P", unit="W")])
def shaft_power(T: float, rpm: float) -> float:
    """Power transmitted P = T * omega with omega = 2 pi rpm / 60 (W)."""
    return T * 2 * math.pi * rpm / 60


@tb_function("shaft_diameter", CAT, args=[Arg("T", unit="N*m", positive=True),
                                           Arg("tau_allow", unit="Pa", positive=True)],
             returns=[Ret("d", unit="m")])
def shaft_diameter(T: float, tau_allow: float) -> float:
    """Minimum solid shaft diameter for torque T: d = (16 T / (pi tau_allow))^(1/3)."""
    return (16 * T / (math.pi * tau_allow)) ** (1 / 3)


@dataclass(frozen=True)
class FourBar:
    theta3: float  # coupler angle, degrees
    theta4: float  # rocker/output angle, degrees
    omega3: float  # angular velocities for input speed omega2 (rad/s)
    omega4: float
    grashof: str  # 'crank-rocker', 'double-crank', 'rocker-crank', 'double-rocker',
    # 'change-point' or 'triple-rocker' (non-Grashof)
    x: np.ndarray  # joint x coordinates [O2 A B O4]: plot(r.x, r.y, '-o') draws the linkage
    y: np.ndarray


def _grashof(a: float, b: float, c: float, d: float) -> str:
    links = sorted([a, b, c, d])
    s, l_ = links[0], links[3]
    p_q = links[1] + links[2]
    if s + l_ > p_q:
        return "triple-rocker"
    if math.isclose(s + l_, p_q):
        return "change-point"
    if s == d:
        return "double-crank"
    if s == a:
        return "crank-rocker"
    if s == c:
        return "rocker-crank"
    return "double-rocker"


@tb_function("fourbar", CAT, args=[
    Arg("a", positive=True), Arg("b", positive=True), Arg("c", positive=True),
    Arg("d", positive=True), Arg("theta2", unit="deg"), Arg("omega2", unit="rad/s"),
    Arg("branch", choices=("open", "crossed"))], returns=[Ret("result")])
def fourbar(a: float, b: float, c: float, d: float, theta2: float, omega2: float = 0.0,
            branch: str = "open") -> FourBar:
    """Four-bar linkage position and velocity analysis (Norton's notation): ground d, input
    crank a at angle theta2 (degrees), coupler b, output rocker c."""
    t2 = math.radians(theta2)
    k1, k2, k3 = d / a, d / c, (a ** 2 - b ** 2 + c ** 2 + d ** 2) / (2 * a * c)
    A = math.cos(t2) - k1 - k2 * math.cos(t2) + k3
    B = -2 * math.sin(t2)
    C = k1 - (k2 + 1) * math.cos(t2) + k3
    disc = B ** 2 - 4 * A * C
    if disc < -1e-12:
        raise ValidationError("fourbar: the linkage cannot be assembled at this input angle")
    disc = max(disc, 0.0)
    sign = -1 if branch == "open" else 1
    t4 = 2 * math.atan2(-B + sign * math.sqrt(disc), 2 * A)
    k4, k5 = d / b, (c ** 2 - d ** 2 - a ** 2 - b ** 2) / (2 * a * b)
    D_ = math.cos(t2) - k1 + k4 * math.cos(t2) + k5
    E = -2 * math.sin(t2)
    F = k1 + (k4 - 1) * math.cos(t2) + k5
    disc3 = max(E ** 2 - 4 * D_ * F, 0.0)
    t3 = 2 * math.atan2(-E + sign * math.sqrt(disc3), 2 * D_)
    denom3 = b * math.sin(t4 - t3)
    w3 = a * omega2 / b * math.sin(t4 - t2) / math.sin(t3 - t4) if denom3 else math.nan
    w4 = a * omega2 / c * math.sin(t2 - t3) / math.sin(t4 - t3) if denom3 else math.nan
    norm = lambda ang: (math.degrees(ang) + 360) % 360  # noqa: E731
    x = np.array([0.0, a * math.cos(t2), d + c * math.cos(t4), d])
    y = np.array([0.0, a * math.sin(t2), c * math.sin(t4), 0.0])
    return FourBar(norm(t3), norm(t4), w3, w4, _grashof(a, b, c, d), x, y)
