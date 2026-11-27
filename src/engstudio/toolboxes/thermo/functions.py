"""Thermodynamics: ideal gas, processes, cycles, COP, entropy. SI units (Pa, m^3, K, kg, J).

Air defaults: R = 287 J/(kg K), k = cp/cv = 1.4, so cp = 1004.5 and cv = 717.5 J/(kg K).
Temperatures in kelvin. Steam and refrigerant tables are not included (ideal-gas and
air-standard models only)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "thermodynamics"
R_AIR, K_AIR = 287.0, 1.4
CP_AIR = K_AIR * R_AIR / (K_AIR - 1)  # 1004.5, consistent with k = 1.4 (cv = 717.5)


@tb_function("ideal_gas", CAT, args=[Arg("p", unit="Pa", optional=True),
                                      Arg("V", unit="m^3", optional=True),
                                      Arg("m", unit="kg", optional=True),
                                      Arg("T", unit="K", optional=True),
                                      Arg("R", positive=True)], returns=[Ret("missing")])
def ideal_gas(p: float | None = None, V: float | None = None, m: float | None = None,
              T: float | None = None, R: float = R_AIR) -> float:
    """p V = m R T: give three of p, V, m, T (use [] for the unknown); returns the fourth."""
    vals = {"p": p, "V": V, "m": m, "T": T}
    missing = [k for k, v in vals.items() if v is None]
    if len(missing) != 1:
        raise ValidationError("ideal_gas: give exactly three of p, V, m, T ([] for the unknown)")
    for k, v in vals.items():
        if v is not None and v <= 0:
            raise ValidationError(f"ideal_gas: {k} must be positive")
    if missing[0] == "p":
        return m * R * T / V
    if missing[0] == "V":
        return m * R * T / p
    if missing[0] == "m":
        return p * V / (R * T)
    return p * V / (m * R)


@dataclass(frozen=True)
class Process:
    p2: float
    V2: float
    T2: float
    W: float  # boundary work done BY the gas, J
    Q: float  # heat added TO the gas, J
    dU: float


@tb_function("gas_process", CAT, args=[
    Arg("kind", choices=("isothermal", "isobaric", "isochoric", "isentropic", "polytropic")),
    Arg("p1", unit="Pa", positive=True), Arg("V1", unit="m^3", positive=True),
    Arg("V2", unit="m^3", positive=True), Arg("m", unit="kg", positive=True),
    Arg("n", positive=True), Arg("R", positive=True), Arg("cv", positive=True)],
    returns=[Ret("result")])
def gas_process(kind: str, p1: float, V1: float, V2: float, m: float = 1.0, n: float = 1.3,
                R: float = R_AIR, cv: float = CP_AIR - R_AIR) -> Process:
    """Closed-system ideal-gas process from (p1, V1) to volume V2 ("isochoric" has no volume
    change and is rejected). Returns the end state, work done by the gas, heat added and the
    internal-energy change (first law: Q = dU + W)."""
    T1 = p1 * V1 / (m * R)
    k = (cv + R) / cv
    if kind == "isothermal":
        p2, W = p1 * V1 / V2, p1 * V1 * math.log(V2 / V1)
    elif kind == "isobaric":
        p2, W = p1, p1 * (V2 - V1)
    elif kind == "isochoric":
        raise ValidationError("gas_process: an isochoric process has no volume change; heat "
                              "it with Q = m*cv*(T2 - T1)")
    else:
        nn = k if kind == "isentropic" else n
        p2 = p1 * (V1 / V2) ** nn
        W = (p2 * V2 - p1 * V1) / (1 - nn) if nn != 1 else p1 * V1 * math.log(V2 / V1)
    T2 = p2 * V2 / (m * R)
    dU = m * cv * (T2 - T1)
    return Process(p2, V2, T2, W, dU + W, dU)


@dataclass(frozen=True)
class Cycle:
    efficiency: float
    T_max: float  # K (air-standard cycles; 0 where not applicable)
    work_ratio: float  # net work / heat in, same as efficiency for these models


@tb_function("cycle_efficiency", CAT, args=[
    Arg("kind", choices=("carnot", "otto", "diesel", "brayton")),
    Arg("a", positive=True), Arg("b", positive=True), Arg("k", positive=True)],
    returns=[Ret("result")])
def cycle_efficiency(kind: str, a: float, b: float = 1.0, k: float = K_AIR) -> Cycle:
    """Thermal efficiency: 'carnot' (a = T_hot, b = T_cold in K), 'otto' (a = compression ratio
    r), 'diesel' (a = r, b = cut-off ratio rc), 'brayton' (a = pressure ratio rp)."""
    if kind == "carnot":
        if b >= a:
            raise ValidationError("cycle_efficiency: T_hot must exceed T_cold")
        eta = 1 - b / a
    elif kind == "otto":
        eta = 1 - a ** (1 - k)
    elif kind == "diesel":
        if b <= 1 or b >= a:
            raise ValidationError("cycle_efficiency: need 1 < cut-off ratio < compression ratio")
        eta = 1 - a ** (1 - k) * (b ** k - 1) / (k * (b - 1))
    else:
        eta = 1 - a ** ((1 - k) / k)
    return Cycle(eta, a if kind == "carnot" else 0.0, eta)


@tb_function("cop", CAT, args=[Arg("kind", choices=("refrigerator", "heat_pump")),
                                Arg("T_cold", unit="K", positive=True),
                                Arg("T_hot", unit="K", positive=True)], returns=[Ret("COP")])
def cop(kind: str, T_cold: float, T_hot: float) -> float:
    """Ideal (Carnot) coefficient of performance of a refrigerator or heat pump."""
    if T_hot <= T_cold:
        raise ValidationError("cop: T_hot must exceed T_cold")
    return T_cold / (T_hot - T_cold) if kind == "refrigerator" else T_hot / (T_hot - T_cold)


@tb_function("entropy_change", CAT, args=[
    Arg("T1", unit="K", positive=True), Arg("T2", unit="K", positive=True),
    Arg("p1", unit="Pa", positive=True), Arg("p2", unit="Pa", positive=True),
    Arg("m", unit="kg", positive=True), Arg("cp", positive=True), Arg("R", positive=True)],
    returns=[Ret("dS", unit="J/K")])
def entropy_change(T1: float, T2: float, p1: float, p2: float, m: float = 1.0,
                   cp: float = CP_AIR, R: float = R_AIR) -> float:
    """Ideal gas: dS = m (cp ln(T2/T1) - R ln(p2/p1))."""
    return m * (cp * math.log(T2 / T1) - R * math.log(p2 / p1))


@tb_function("isentropic_temperature", CAT, args=[
    Arg("T1", unit="K", positive=True), Arg("pressure_ratio", positive=True),
    Arg("k", positive=True)], returns=[Ret("T2", unit="K")])
def isentropic_temperature(T1: float, pressure_ratio: float, k: float = K_AIR) -> float:
    """T2 = T1 (p2/p1)^((k-1)/k) for an isentropic ideal-gas process."""
    return T1 * pressure_ratio ** ((k - 1) / k)


FUNCTIONS = (ideal_gas, gas_process, cycle_efficiency, cop, entropy_change,
             isentropic_temperature)
