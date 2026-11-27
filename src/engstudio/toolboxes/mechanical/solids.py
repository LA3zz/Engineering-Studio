"""Mechanics of materials: section properties, stresses, failure criteria, buckling, beams.

SI units throughout (m, N, Pa, N*m); any consistent unit system works since the formulas are
homogeneous. Sign conventions: tension positive; beam loads positive downward, deflection
positive upward (so a downward load gives a negative deflection), sagging moment positive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

__all__ = ["beam", "buckling_euler", "mohr", "section_circle", "section_ibeam",
           "section_rect", "section_tube", "safety_factor", "stress_axial", "stress_bending",
           "stress_torsion", "von_mises"]

CAT = "mechanical"


@dataclass(frozen=True)
class Section:
    A: float  # area
    Ix: float  # second moment about the horizontal centroidal axis
    Iy: float
    J: float  # polar moment (circles) or torsion constant (other shapes)
    Sx: float  # elastic section modulus Ix / c
    Sy: float
    rx: float  # radius of gyration
    ry: float
    c: float  # distance from the centroid to the extreme fibre (bending about x)


def _section(A: float, Ix: float, Iy: float, J: float, cx: float, cy: float) -> Section:
    return Section(A, Ix, Iy, J, Ix / cx, Iy / cy, math.sqrt(Ix / A), math.sqrt(Iy / A), cx)


@tb_function("section_rect", CAT, args=[Arg("b", unit="m", positive=True),
                                         Arg("h", unit="m", positive=True)],
             returns=[Ret("props")])
def section_rect(b: float, h: float) -> Section:
    """Rectangle b (width) x h (height): A, Ix, Iy, J (torsion constant), Sx, Sy, rx, ry, c."""
    a, t = max(b, h), min(b, h)
    j = a * t ** 3 * (1 / 3 - 0.21 * t / a * (1 - t ** 4 / (12 * a ** 4)))  # Roark
    return _section(b * h, b * h ** 3 / 12, h * b ** 3 / 12, j, h / 2, b / 2)


@tb_function("section_circle", CAT, args=[Arg("d", unit="m", positive=True)],
             returns=[Ret("props")])
def section_circle(d: float) -> Section:
    """Solid circle of diameter d: A, I = pi d^4/64, J = pi d^4/32, ..."""
    i = math.pi * d ** 4 / 64
    return _section(math.pi * d ** 2 / 4, i, i, 2 * i, d / 2, d / 2)


@tb_function("section_tube", CAT, args=[Arg("do", unit="m", positive=True),
                                         Arg("di", unit="m", nonnegative=True)],
             returns=[Ret("props")])
def section_tube(do: float, di: float) -> Section:
    """Hollow circle (outer do, inner di)."""
    if di >= do:
        raise ValidationError("section_tube: the inner diameter must be smaller than the outer")
    i = math.pi * (do ** 4 - di ** 4) / 64
    return _section(math.pi * (do ** 2 - di ** 2) / 4, i, i, 2 * i, do / 2, do / 2)


@tb_function("section_ibeam", CAT, args=[Arg("bf", unit="m", positive=True),
                                          Arg("tf", unit="m", positive=True),
                                          Arg("h", unit="m", positive=True),
                                          Arg("tw", unit="m", positive=True)],
             returns=[Ret("props")])
def section_ibeam(bf: float, tf: float, h: float, tw: float) -> Section:
    """Symmetric I-section: flange width bf and thickness tf, overall height h, web tw."""
    if 2 * tf >= h or tw > bf:
        raise ValidationError("section_ibeam: need 2*tf < h and tw <= bf")
    hw = h - 2 * tf
    area = 2 * bf * tf + hw * tw
    ix = (bf * h ** 3 - (bf - tw) * hw ** 3) / 12
    iy = 2 * tf * bf ** 3 / 12 + hw * tw ** 3 / 12
    j = (2 * bf * tf ** 3 + (h - tf) * tw ** 3) / 3  # thin-walled open section
    return _section(area, ix, iy, j, h / 2, bf / 2)


@tb_function("stress_axial", CAT, args=[Arg("F", unit="N"), Arg("A", unit="m^2", positive=True)],
             returns=[Ret("sigma", unit="Pa")])
def stress_axial(F: float, A: float) -> float:
    """Normal stress sigma = F / A (tension positive)."""
    return F / A


@tb_function("stress_bending", CAT, args=[Arg("M", unit="N*m"), Arg("c", unit="m"),
                                           Arg("I", unit="m^4", positive=True)],
             returns=[Ret("sigma", unit="Pa")])
def stress_bending(M: float, c: float, I: float) -> float:  # noqa: E741 (engineering symbol)
    """Bending stress sigma = M c / I."""
    return M * c / I


@tb_function("stress_torsion", CAT, args=[Arg("T", unit="N*m"), Arg("r", unit="m"),
                                           Arg("J", unit="m^4", positive=True)],
             returns=[Ret("tau", unit="Pa")])
def stress_torsion(T: float, r: float, J: float) -> float:
    """Shear stress from torsion tau = T r / J (circular shafts)."""
    return T * r / J


@dataclass(frozen=True)
class Mohr:
    s1: float  # major principal stress
    s2: float  # minor principal stress
    tau_max: float  # maximum in-plane shear stress
    theta_p: float  # angle to the s1 plane, degrees (counter-clockwise from x)
    center: float
    radius: float


@tb_function("mohr", CAT, args=[Arg("sx", unit="Pa"), Arg("sy", unit="Pa"),
                                 Arg("txy", unit="Pa")], returns=[Ret("result")])
def mohr(sx: float, sy: float, txy: float) -> Mohr:
    """Plane stress: principal stresses, max in-plane shear and principal angle (Mohr's
    circle)."""
    center = (sx + sy) / 2
    radius = math.hypot((sx - sy) / 2, txy)
    theta = 0.5 * math.degrees(math.atan2(2 * txy, sx - sy))
    return Mohr(center + radius, center - radius, radius, theta, center, radius)


@tb_function("von_mises", CAT, args=[Arg("sx", unit="Pa"), Arg("sy", unit="Pa"),
                                      Arg("txy", unit="Pa"), Arg("sz", unit="Pa"),
                                      Arg("tyz", unit="Pa"), Arg("tzx", unit="Pa")],
             returns=[Ret("sigma_vm", unit="Pa")])
def von_mises(sx: float, sy: float = 0.0, txy: float = 0.0, sz: float = 0.0, tyz: float = 0.0,
              tzx: float = 0.0) -> float:
    """Von Mises equivalent stress (3-D; plane stress when the z terms are omitted)."""
    return math.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
                     + 3 * (txy ** 2 + tyz ** 2 + tzx ** 2))


@tb_function("safety_factor", CAT, args=[Arg("stress", unit="Pa", positive=True),
                                          Arg("strength", unit="Pa", positive=True)],
             returns=[Ret("n")])
def safety_factor(stress: float, strength: float) -> float:
    """Factor of safety n = strength / stress (e.g. yield strength / von Mises stress)."""
    return strength / stress


@tb_function("buckling_euler", CAT, args=[Arg("E", unit="Pa", positive=True),
                                           Arg("I", unit="m^4", positive=True),
                                           Arg("L", unit="m", positive=True),
                                           Arg("K", positive=True)],
             returns=[Ret("Pcr", unit="N")])
def buckling_euler(E: float, I: float, L: float, K: float = 1.0) -> float:  # noqa: E741
    """Euler critical load Pcr = pi^2 E I / (K L)^2. K: 1 pinned-pinned, 0.5 fixed-fixed,
    0.699 fixed-pinned, 2 fixed-free."""
    return math.pi ** 2 * E * I / (K * L) ** 2


# --------------------------------------------------------------------------------- beams
@dataclass(frozen=True)
class BeamResult:
    x: np.ndarray
    V: np.ndarray  # shear force
    M: np.ndarray  # bending moment (sagging positive)
    slope: np.ndarray  # rad
    deflection: np.ndarray  # positive upward
    reactions: np.ndarray  # simply: [R_left, R_right]; cantilever: [R, M_wall]
    max_deflection: float  # largest magnitude, signed
    x_max_deflection: float
    max_moment: float  # largest magnitude, signed
    x_max_moment: float


@tb_function("beam", CAT, args=[
    Arg("L", unit="m", positive=True), Arg("E", unit="Pa", positive=True),
    Arg("I", unit="m^4", positive=True), Arg("support", choices=("simply", "cantilever")),
    Arg("P", unit="N", shape=(None,), optional=True),
    Arg("a", unit="m", shape=(None,), optional=True),
    Arg("w", unit="N/m")], returns=[Ret("result")])
def beam(L: float, E: float, I: float, support: str = "simply",  # noqa: E741
         P: np.ndarray | None = None, a: np.ndarray | None = None, w: float = 0.0
         ) -> BeamResult:
    """Statically determinate beam: point loads P at positions a (downward positive) and a
    uniform load w over the whole span. 'simply' = pinned at 0, roller at L; 'cantilever' =
    fixed at x = 0, free at L. Returns shear, moment, slope, deflection along x."""
    P = np.zeros(0) if P is None else np.atleast_1d(np.asarray(P, dtype=float))
    a = np.zeros(0) if a is None else np.atleast_1d(np.asarray(a, dtype=float))
    if P.size != a.size:
        raise ValidationError("beam: P and a must have the same number of entries")
    if np.any((a < 0) | (a > L)):
        raise ValidationError("beam: load positions must lie on the beam (0 <= a <= L)")
    x = np.unique(np.concatenate([np.linspace(0, L, 2001), a]))
    if support == "simply":
        rb = (float(np.sum(P * a)) + w * L ** 2 / 2) / L
        ra = float(np.sum(P)) + w * L - rb
        V = ra - w * x - np.array([np.sum(P[a < xi]) for xi in x])
        M = ra * x - w * x ** 2 / 2 - np.array([np.sum(P[a < xi] * (xi - a[a < xi])) for xi in x])
        reactions = np.array([ra, rb])
    else:
        r = float(np.sum(P)) + w * L
        m_wall = -(float(np.sum(P * a)) + w * L ** 2 / 2)  # hogging moment at the wall
        V = r - w * x - np.array([np.sum(P[a < xi]) for xi in x])
        M = m_wall + r * x - w * x ** 2 / 2 - np.array(
            [np.sum(P[a < xi] * (xi - a[a < xi])) for xi in x])
        reactions = np.array([r, m_wall])
    # EI y'' = M; integrate twice (trapezoid on a fine grid), then apply boundary conditions.
    k = M / (E * I)
    theta = np.concatenate([[0.0], np.cumsum((k[1:] + k[:-1]) / 2 * np.diff(x))])
    y = np.concatenate([[0.0], np.cumsum((theta[1:] + theta[:-1]) / 2 * np.diff(x))])
    if support == "simply":  # y(0) = y(L) = 0: add a linear term c*x
        c = -y[-1] / L
        theta, y = theta + c, y + c * x
    i_d, i_m = int(np.argmax(np.abs(y))), int(np.argmax(np.abs(M)))
    return BeamResult(x, V, M, theta, y, reactions, float(y[i_d]), float(x[i_d]),
                      float(M[i_m]), float(x[i_m]))
