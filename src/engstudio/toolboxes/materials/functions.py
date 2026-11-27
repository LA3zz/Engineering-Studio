"""Materials and lab data: a small property database, tensile-test analysis (modulus, 0.2 %
offset yield, UTS, elongation, toughness), thermal stress, fatigue (Goodman/Soderberg/Gerber,
Basquin) and composite rule of mixtures. SI units (Pa, kg/m^3, 1/K)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "materials"


@dataclass(frozen=True)
class Material:
    name: str
    E: float  # Young's modulus, Pa
    nu: float  # Poisson's ratio
    G: float  # shear modulus, Pa
    rho: float  # density, kg/m^3
    Sy: float  # yield strength, Pa
    Su: float  # ultimate strength, Pa
    alpha: float  # thermal expansion, 1/K
    k: float  # thermal conductivity, W/(m K)
    cp: float  # specific heat, J/(kg K)


# Typical room-temperature values (handbook averages; check a datasheet for design work).
_DB = {
    "steel": ("Structural steel (S275/A36)", 200e9, 0.30, 7850, 250e6, 400e6, 12e-6, 50, 490),
    "stainless": ("Stainless steel 304", 193e9, 0.29, 8000, 215e6, 505e6, 17.3e-6, 16.2, 500),
    "aluminium": ("Aluminium 6061-T6", 69e9, 0.33, 2700, 276e6, 310e6, 23.6e-6, 167, 896),
    "copper": ("Copper (annealed)", 117e9, 0.34, 8960, 70e6, 220e6, 16.5e-6, 401, 385),
    "brass": ("Brass C360", 97e9, 0.31, 8500, 310e6, 385e6, 20.5e-6, 115, 380),
    "titanium": ("Titanium Ti-6Al-4V", 114e9, 0.34, 4430, 880e6, 950e6, 8.6e-6, 6.7, 526),
    "cast_iron": ("Grey cast iron", 110e9, 0.26, 7200, 130e6, 200e6, 10.8e-6, 52, 460),
    "concrete": ("Concrete (C30)", 30e9, 0.20, 2400, 3e6, 30e6, 10e-6, 1.7, 880),
    "wood": ("Pine (along grain)", 10e9, 0.30, 500, 40e6, 70e6, 5e-6, 0.12, 1600),
    "glass": ("Soda-lime glass", 70e9, 0.22, 2500, 50e6, 50e6, 9e-6, 1.0, 840),
    "abs": ("ABS plastic", 2.3e9, 0.35, 1050, 40e6, 45e6, 90e-6, 0.17, 1400),
    "nylon": ("Nylon 6/6", 2.8e9, 0.39, 1140, 70e6, 85e6, 80e-6, 0.25, 1700),
}


@tb_function("material", CAT, args=[Arg("name", choices=tuple(_DB))], returns=[Ret("props")])
def material(name: str) -> Material:
    """Typical properties of a common engineering material (E, nu, G, rho, Sy, Su, alpha, k,
    cp). Names: steel, stainless, aluminium, copper, brass, titanium, cast_iron, concrete,
    wood, glass, abs, nylon."""
    full, E, nu, rho, sy, su, alpha, k, cp = _DB[name]
    return Material(full, E, nu, E / (2 * (1 + nu)), rho, sy, su, alpha, k, cp)


@dataclass(frozen=True)
class Tensile:
    E: float  # modulus from the linear part, Pa
    Sy: float  # 0.2 % offset yield, Pa
    Su: float  # ultimate tensile strength, Pa
    elongation: float  # strain at fracture (last point)
    toughness: float  # area under the curve, J/m^3
    resilience: float  # Sy^2 / (2E), J/m^3
    strain_at_Su: float


@tb_function("tensile_test", CAT, args=[
    Arg("strain", shape=(None,)), Arg("stress", shape=(None,), unit="Pa"),
    Arg("elastic_limit", positive=True, optional=True), Arg("offset", positive=True)],
    returns=[Ret("result")])
def tensile_test(strain: np.ndarray, stress: np.ndarray, elastic_limit: float | None = None,
                 offset: float = 0.002) -> Tensile:
    """Analyse a stress-strain curve (e.g. lab data from readmatrix). E is the least-squares
    slope through the points with stress <= elastic_limit (default 40 % of the peak); the yield
    point is where the curve crosses the line of slope E offset by ``offset`` (0.2 %)."""
    e, s = np.asarray(strain, float).ravel(), np.asarray(stress, float).ravel()
    if e.size != s.size or e.size < 5:
        raise ValidationError("tensile_test: strain and stress need the same length (>= 5)")
    ok = ~(np.isnan(e) | np.isnan(s))
    e, s = e[ok], s[ok]
    i_max = int(np.argmax(s))
    limit = 0.4 * s[i_max] if elastic_limit is None else elastic_limit
    lin = (s <= limit) & (np.arange(e.size) <= i_max)
    if lin.sum() < 2:
        raise ValidationError("tensile_test: fewer than two points in the elastic part")
    E, b = np.polyfit(e[lin], s[lin], 1)
    if E <= 0:
        raise ValidationError("tensile_test: the elastic part has no positive slope")
    gap = s - (E * (e - offset) + b)  # > 0 while the curve is above the offset line
    sy = math.nan
    for k in range(1, e.size):
        if gap[k - 1] > 0 >= gap[k]:
            f = gap[k - 1] / (gap[k - 1] - gap[k])
            sy = float(s[k - 1] + f * (s[k] - s[k - 1]))
            break
    tough = float(np.sum((s[1:] + s[:-1]) * np.diff(e)) / 2)
    res = sy ** 2 / (2 * E) if not math.isnan(sy) else math.nan
    return Tensile(float(E), sy, float(s[i_max]), float(e[-1]), tough, res, float(e[i_max]))


@tb_function("thermal_stress", CAT, args=[Arg("E", unit="Pa", positive=True),
                                           Arg("alpha", positive=True), Arg("dT", unit="K"),
                                           Arg("restraint", min=0.0, max=1.0)],
             returns=[Ret("sigma", unit="Pa")])
def thermal_stress(E: float, alpha: float, dT: float, restraint: float = 1.0) -> float:
    """Stress in a bar restrained against thermal growth: sigma = -restraint E alpha dT
    (compressive when heated)."""
    return -restraint * E * alpha * dT


@tb_function("fatigue_sf", CAT, args=[
    Arg("sa", unit="Pa", nonnegative=True), Arg("sm", unit="Pa"), Arg("Se", unit="Pa",
                                                                         positive=True),
    Arg("Su", unit="Pa", positive=True), Arg("Sy", unit="Pa", positive=True, optional=True),
    Arg("criterion", choices=("goodman", "soderberg", "gerber"))],
    returns=[Ret("n")])
def fatigue_sf(sa: float, sm: float, Se: float, Su: float, Sy: float | None = None,
               criterion: str = "goodman") -> float:
    """Fatigue safety factor for alternating sa and mean sm stress: Goodman 1/n = sa/Se + sm/Su,
    Soderberg (needs Sy) 1/n = sa/Se + sm/Sy, Gerber n sa/Se + (n sm/Su)^2 = 1."""
    sm = max(sm, 0.0)  # compressive mean stress taken as zero (conservative)
    if criterion == "soderberg":
        if Sy is None:
            raise ValidationError("fatigue_sf: Soderberg needs Sy")
        inv = sa / Se + sm / Sy
    elif criterion == "goodman":
        inv = sa / Se + sm / Su
    else:
        if sm == 0:
            return math.inf if sa == 0 else Se / sa
        a, bq = (sm / Su) ** 2, sa / Se  # a n^2 + bq n - 1 = 0
        return (-bq + math.sqrt(bq ** 2 + 4 * a)) / (2 * a)
    return math.inf if inv == 0 else 1 / inv


@tb_function("basquin_life", CAT, args=[Arg("sa", unit="Pa", positive=True),
                                         Arg("sf", unit="Pa", positive=True),
                                         Arg("b", max=0.0)],
             returns=[Ret("N")])
def basquin_life(sa: float, sf: float, b: float = -0.085) -> float:
    """Cycles to failure from Basquin's law sa = sf' (2N)^b."""
    if b == 0:
        raise ValidationError("basquin_life: the exponent b must be negative")
    return 0.5 * (sa / sf) ** (1 / b)


@tb_function("rule_of_mixtures", CAT, args=[Arg("Ef", unit="Pa", positive=True),
                                             Arg("Em", unit="Pa", positive=True),
                                             Arg("Vf", min=0.0, max=1.0)],
             returns=[Ret("E_long", unit="Pa"), Ret("E_trans", unit="Pa")])
def rule_of_mixtures(Ef: float, Em: float, Vf: float) -> tuple[float, float]:
    """Composite moduli: along fibres Vf Ef + (1-Vf) Em (Voigt), across 1/(Vf/Ef + (1-Vf)/Em)
    (Reuss)."""
    return Vf * Ef + (1 - Vf) * Em, 1 / (Vf / Ef + (1 - Vf) / Em)


FUNCTIONS = (material, tensile_test, thermal_stress, fatigue_sf, basquin_life,
             rule_of_mixtures)
