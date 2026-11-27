"""Heat transfer: conduction resistances, convection correlations, radiation, fins, heat
exchangers (LMTD, effectiveness-NTU), lumped-capacitance transients. SI units (W, m, K)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "heat_transfer"
SIGMA = 5.670374419e-8


@tb_function("conduction_resistance", CAT, args=[
    Arg("geometry", choices=("plane", "cylinder", "sphere")), Arg("k", positive=True),
    Arg("a", unit="m", positive=True), Arg("b", unit="m", positive=True),
    Arg("L", unit="m", positive=True)], returns=[Ret("R", unit="K/W")])
def conduction_resistance(geometry: str, k: float, a: float, b: float, L: float = 1.0) -> float:
    """Thermal resistance. plane: thickness a, area b. cylinder: radii a < b, length L.
    sphere: radii a < b."""
    if geometry == "plane":
        return a / (k * b)
    if b <= a:
        raise ValidationError("conduction_resistance: the outer radius must exceed the inner")
    if geometry == "cylinder":
        return math.log(b / a) / (2 * math.pi * k * L)
    return (1 / a - 1 / b) / (4 * math.pi * k)


@tb_function("convection_resistance", CAT, args=[Arg("h", positive=True),
                                                  Arg("A", unit="m^2", positive=True)],
             returns=[Ret("R", unit="K/W")])
def convection_resistance(h: float, A: float) -> float:
    """R = 1 / (h A)."""
    return 1 / (h * A)


@tb_function("radiation", CAT, args=[Arg("emissivity", positive=True, max=1.0),
                                      Arg("A", unit="m^2", positive=True),
                                      Arg("Ts", unit="K", positive=True),
                                      Arg("Tsur", unit="K", positive=True)],
             returns=[Ret("q", unit="W"), Ret("h_rad")])
def radiation(emissivity: float, A: float, Ts: float, Tsur: float) -> tuple[float, float]:
    """Net radiation q = eps sigma A (Ts^4 - Tsur^4) and the radiation coefficient h_rad."""
    q = emissivity * SIGMA * A * (Ts ** 4 - Tsur ** 4)
    h = emissivity * SIGMA * (Ts + Tsur) * (Ts ** 2 + Tsur ** 2)
    return q, h


@tb_function("nusselt", CAT, args=[
    Arg("correlation", choices=("dittus-boelter", "laminar-tube", "flat-plate-laminar",
                                "flat-plate-turbulent", "churchill-bernstein")),
    Arg("Re", positive=True), Arg("Pr", positive=True),
    Arg("heating", choices=("heating", "cooling"))], returns=[Ret("Nu")])
def nusselt(correlation: str, Re: float, Pr: float, heating: str = "heating") -> float:
    """Average Nusselt number: tube flow (Dittus-Boelter, n = 0.4 heating / 0.3 cooling;
    laminar fully developed constant wall temperature 3.66), flat plate (laminar
    0.664 Re^1/2 Pr^1/3, turbulent 0.037 Re^4/5 Pr^1/3), cylinder in cross flow
    (Churchill-Bernstein)."""
    if correlation == "dittus-boelter":
        return 0.023 * Re ** 0.8 * Pr ** (0.4 if heating == "heating" else 0.3)
    if correlation == "laminar-tube":
        return 3.66
    if correlation == "flat-plate-laminar":
        return 0.664 * Re ** 0.5 * Pr ** (1 / 3)
    if correlation == "flat-plate-turbulent":
        return 0.037 * Re ** 0.8 * Pr ** (1 / 3)
    return 0.3 + (0.62 * Re ** 0.5 * Pr ** (1 / 3) / (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25
                  * (1 + (Re / 282000) ** (5 / 8)) ** (4 / 5))


@dataclass(frozen=True)
class Fin:
    efficiency: float
    q: float  # heat rate, W
    m: float  # fin parameter sqrt(h P / (k Ac)), 1/m


@tb_function("fin", CAT, args=[Arg("h", positive=True), Arg("k", positive=True),
                                Arg("P", unit="m", positive=True),
                                Arg("Ac", unit="m^2", positive=True),
                                Arg("L", unit="m", positive=True), Arg("dT", unit="K")],
             returns=[Ret("result")])
def fin(h: float, k: float, P: float, Ac: float, L: float, dT: float) -> Fin:
    """Straight fin with an adiabatic tip (corrected length Lc = L + Ac/P): efficiency
    tanh(m Lc)/(m Lc) and heat rate sqrt(h P k Ac) tanh(m Lc) dT, dT = T_base - T_inf."""
    m = math.sqrt(h * P / (k * Ac))
    lc = L + Ac / P
    q = math.sqrt(h * P * k * Ac) * math.tanh(m * lc) * dT
    return Fin(math.tanh(m * lc) / (m * lc), q, m)


@tb_function("lmtd", CAT, args=[Arg("Th_in", unit="K"), Arg("Th_out", unit="K"),
                                 Arg("Tc_in", unit="K"), Arg("Tc_out", unit="K"),
                                 Arg("flow", choices=("counter", "parallel"))],
             returns=[Ret("dTlm", unit="K")])
def lmtd(Th_in: float, Th_out: float, Tc_in: float, Tc_out: float, flow: str = "counter"
         ) -> float:
    """Log-mean temperature difference for counter- or parallel-flow exchangers."""
    if flow == "counter":
        d1, d2 = Th_in - Tc_out, Th_out - Tc_in
    else:
        d1, d2 = Th_in - Tc_in, Th_out - Tc_out
    if d1 <= 0 or d2 <= 0:
        raise ValidationError("lmtd: temperature cross; check the inlet/outlet temperatures")
    return d1 if math.isclose(d1, d2) else (d1 - d2) / math.log(d1 / d2)


@tb_function("effectiveness_ntu", CAT, args=[Arg("NTU", nonnegative=True),
                                              Arg("Cr", nonnegative=True, max=1.0),
                                              Arg("flow", choices=("counter", "parallel"))],
             returns=[Ret("effectiveness")])
def effectiveness_ntu(NTU: float, Cr: float, flow: str = "counter") -> float:
    """epsilon(NTU, Cr = Cmin/Cmax) for counter- or parallel-flow exchangers."""
    if Cr == 0:
        return 1 - math.exp(-NTU)
    if flow == "parallel":
        return (1 - math.exp(-NTU * (1 + Cr))) / (1 + Cr)
    if math.isclose(Cr, 1.0):
        return NTU / (1 + NTU)
    e = math.exp(-NTU * (1 - Cr))
    return (1 - e) / (1 - Cr * e)


@dataclass(frozen=True)
class Lumped:
    T: np.ndarray  # temperature history, K
    tau: float  # time constant rho V c / (h A), s
    Bi: float  # Biot number (lumped model valid for Bi < 0.1)
    valid: bool


@tb_function("lumped", CAT, args=[Arg("T0", unit="K"), Arg("Tinf", unit="K"),
                                   Arg("h", positive=True), Arg("A", unit="m^2", positive=True),
                                   Arg("V", unit="m^3", positive=True),
                                   Arg("rho", positive=True), Arg("c", positive=True),
                                   Arg("k", positive=True), Arg("t", unit="s")],
             returns=[Ret("result")])
def lumped(T0: float, Tinf: float, h: float, A: float, V: float, rho: float, c: float,
           k: float, t: np.ndarray | float) -> Lumped:
    """Lumped-capacitance cooling/heating T(t) = Tinf + (T0 - Tinf) exp(-t/tau); Bi = h (V/A)/k."""
    tau = rho * V * c / (h * A)
    bi = h * (V / A) / k
    tt = np.atleast_1d(np.asarray(t, dtype=float))
    return Lumped(Tinf + (T0 - Tinf) * np.exp(-tt / tau), tau, bi, bi < 0.1)


FUNCTIONS = (conduction_resistance, convection_resistance, radiation, nusselt, fin, lmtd,
             effectiveness_ntu, lumped)
