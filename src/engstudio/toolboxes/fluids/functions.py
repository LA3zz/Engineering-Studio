"""Fluid mechanics: Reynolds number, friction factor, pipe losses, Bernoulli, hydrostatics,
pumps, drag, orifice flow, open channels. SI units; water at 20 C: rho = 998 kg/m^3,
mu = 1.002e-3 Pa s; g = 9.81 m/s^2."""

from __future__ import annotations

import math
from dataclasses import dataclass

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "fluids"
G = 9.81
RHO_W, MU_W = 998.0, 1.002e-3


@tb_function("reynolds", CAT, args=[Arg("V", unit="m/s", nonnegative=True),
                                     Arg("D", unit="m", positive=True),
                                     Arg("rho", unit="kg/m^3", positive=True),
                                     Arg("mu", unit="Pa*s", positive=True)],
             returns=[Ret("Re")])
def reynolds(V: float, D: float, rho: float = RHO_W, mu: float = MU_W) -> float:
    """Reynolds number Re = rho V D / mu (water at 20 C by default)."""
    return rho * V * D / mu


@tb_function("friction_factor", CAT, args=[Arg("Re", positive=True),
                                            Arg("rel_roughness", nonnegative=True),
                                            Arg("method", choices=("colebrook", "swamee-jain",
                                                                   "haaland"))],
             returns=[Ret("f")])
def friction_factor(Re: float, rel_roughness: float = 0.0, method: str = "colebrook") -> float:
    """Darcy friction factor: 64/Re for laminar flow (Re < 2300), else Colebrook-White (solved
    iteratively), Swamee-Jain or Haaland. rel_roughness = epsilon / D."""
    if Re < 2300:
        return 64 / Re
    e = rel_roughness
    if method == "swamee-jain":
        return 0.25 / math.log10(e / 3.7 + 5.74 / Re ** 0.9) ** 2
    if method == "haaland":
        return (-1.8 * math.log10((e / 3.7) ** 1.11 + 6.9 / Re)) ** -2
    f = 0.25 / math.log10(e / 3.7 + 5.74 / Re ** 0.9) ** 2
    for _ in range(50):
        new = (-2 * math.log10(e / 3.7 + 2.51 / (Re * math.sqrt(f)))) ** -2
        if abs(new - f) < 1e-14:
            break
        f = new
    return f


@dataclass(frozen=True)
class PipeFlow:
    Re: float
    f: float
    hf: float  # head loss, m
    dp: float  # pressure drop, Pa
    V: float  # mean velocity, m/s
    regime: str


@tb_function("pipe_loss", CAT, args=[
    Arg("Q", unit="m^3/s", positive=True), Arg("D", unit="m", positive=True),
    Arg("L", unit="m", positive=True), Arg("roughness", unit="m", nonnegative=True),
    Arg("K_minor", nonnegative=True), Arg("rho", unit="kg/m^3", positive=True),
    Arg("mu", unit="Pa*s", positive=True)], returns=[Ret("result")])
def pipe_loss(Q: float, D: float, L: float, roughness: float = 0.0, K_minor: float = 0.0,
              rho: float = RHO_W, mu: float = MU_W) -> PipeFlow:
    """Darcy-Weisbach head loss hf = (f L/D + sum K) V^2/(2g) for flow Q in a round pipe."""
    V = Q / (math.pi * D ** 2 / 4)
    Re = reynolds(V, D, rho, mu)
    f = friction_factor(Re, roughness / D)
    hf = (f * L / D + K_minor) * V ** 2 / (2 * G)
    regime = "laminar" if Re < 2300 else ("transitional" if Re < 4000 else "turbulent")
    return PipeFlow(Re, f, hf, rho * G * hf, V, regime)


@tb_function("bernoulli", CAT, args=[
    Arg("p1", unit="Pa"), Arg("V1", unit="m/s"), Arg("z1", unit="m"), Arg("V2", unit="m/s"),
    Arg("z2", unit="m"), Arg("rho", unit="kg/m^3", positive=True),
    Arg("head_loss", unit="m", nonnegative=True)], returns=[Ret("p2", unit="Pa")])
def bernoulli(p1: float, V1: float, z1: float, V2: float, z2: float, rho: float = RHO_W,
              head_loss: float = 0.0) -> float:
    """p2 from p1 + rho V1^2/2 + rho g z1 = p2 + rho V2^2/2 + rho g z2 + rho g hL."""
    return p1 + rho * (V1 ** 2 - V2 ** 2) / 2 + rho * G * (z1 - z2 - head_loss)


@tb_function("hydrostatic", CAT, args=[Arg("h", unit="m"), Arg("rho", unit="kg/m^3",
                                                                positive=True),
                                        Arg("p0", unit="Pa")], returns=[Ret("p", unit="Pa")])
def hydrostatic(h: float, rho: float = RHO_W, p0: float = 0.0) -> float:
    """Pressure at depth h: p = p0 + rho g h (gauge pressure when p0 = 0)."""
    return p0 + rho * G * h


@tb_function("pump_power", CAT, args=[Arg("Q", unit="m^3/s", nonnegative=True),
                                       Arg("H", unit="m", nonnegative=True),
                                       Arg("efficiency", positive=True, max=1.0),
                                       Arg("rho", unit="kg/m^3", positive=True)],
             returns=[Ret("P", unit="W")])
def pump_power(Q: float, H: float, efficiency: float = 1.0, rho: float = RHO_W) -> float:
    """Shaft power P = rho g Q H / efficiency."""
    return rho * G * Q * H / efficiency


@tb_function("drag_force", CAT, args=[Arg("Cd", positive=True), Arg("A", unit="m^2",
                                                                     positive=True),
                                       Arg("V", unit="m/s"), Arg("rho", unit="kg/m^3",
                                                                 positive=True)],
             returns=[Ret("F", unit="N")])
def drag_force(Cd: float, A: float, V: float, rho: float = 1.225) -> float:
    """Drag F = Cd A rho V^2 / 2 (air at sea level by default)."""
    return 0.5 * Cd * A * rho * V * abs(V)


@tb_function("orifice_flow", CAT, args=[Arg("Cd", positive=True), Arg("A", unit="m^2",
                                                                       positive=True),
                                         Arg("dp", unit="Pa", nonnegative=True),
                                         Arg("rho", unit="kg/m^3", positive=True),
                                         Arg("beta", nonnegative=True, max=0.9)],
             returns=[Ret("Q", unit="m^3/s")])
def orifice_flow(Cd: float, A: float, dp: float, rho: float = RHO_W, beta: float = 0.0
                 ) -> float:
    """Q = Cd A sqrt(2 dp / (rho (1 - beta^4))), beta = d/D (0 for a tank orifice)."""
    return Cd * A * math.sqrt(2 * dp / (rho * (1 - beta ** 4)))


@tb_function("manning", CAT, args=[Arg("n", positive=True), Arg("A", unit="m^2",
                                                                 positive=True),
                                    Arg("P", unit="m", positive=True),
                                    Arg("S", nonnegative=True)], returns=[Ret("Q",
                                                                             unit="m^3/s")])
def manning(n: float, A: float, P: float, S: float) -> float:
    """Open-channel flow (SI): Q = (1/n) A R^(2/3) S^(1/2), R = A / P (hydraulic radius)."""
    return A * (A / P) ** (2 / 3) * math.sqrt(S) / n


@tb_function("terminal_velocity", CAT, args=[Arg("m", unit="kg", positive=True),
                                              Arg("Cd", positive=True),
                                              Arg("A", unit="m^2", positive=True),
                                              Arg("rho", unit="kg/m^3", positive=True)],
             returns=[Ret("V", unit="m/s")])
def terminal_velocity(m: float, Cd: float, A: float, rho: float = 1.225) -> float:
    """Falling body: m g = Cd A rho V^2 / 2."""
    if rho <= 0:
        raise ValidationError("terminal_velocity: rho must be positive")
    return math.sqrt(2 * m * G / (Cd * A * rho))


FUNCTIONS = (reynolds, friction_factor, pipe_loss, bernoulli, hydrostatic, pump_power,
             drag_force, orifice_flow, manning, terminal_velocity)
