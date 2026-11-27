"""Explicit unit conversion. SI is the base system; nothing is converted implicitly.

Conversion factors are exact rational numbers (from the definitions of each unit) and are
rounded to float only once per conversion. Unit names are case-sensitive and ASCII
(``ohm``, ``um``, ``degC``); a few aliases such as ``°C`` and ``Ω`` are accepted.

Compound expressions are supported: ``kg*m/s^2``, ``W/(m*K)``, ``m^3``, ``1/s``.
Temperature scales with an offset (``degC``, ``degF``) can only be converted on their
own; use ``delta_degC`` / ``delta_degF`` for temperature differences.

Angle is a separate base dimension so that ``Hz`` and ``rad/s`` are never silently
interchanged (they differ by a factor of 2*pi).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import get_close_matches
from fractions import Fraction
from functools import lru_cache

import numpy as np

from engstudio.core.errors import UnitError, ValidationError

__all__ = [
    "convert", "conversion_factor", "dimension_of", "is_compatible",
    "format_dimension", "known_units",
]

_BASE = ("m", "kg", "s", "A", "K", "mol", "cd", "rad")
Dim = tuple[int, ...]


def _dim(**exponents: int) -> Dim:
    return tuple(exponents.get(b, 0) for b in _BASE)


@dataclass(frozen=True)
class _Unit:
    scale: Fraction   # SI = value * scale + offset
    dim: Dim
    offset: Fraction = Fraction(0)

    @property
    def affine(self) -> bool:
        return self.offset != 0


_TABLE: dict[str, _Unit] = {}


def _add(name: str, scale: str | Fraction, dim: Dim, offset: str | Fraction = "0") -> None:
    _TABLE[name] = _Unit(Fraction(scale), dim, Fraction(offset))


def _build_table() -> None:
    g0 = Fraction("9.80665")
    inch, foot = Fraction("0.0254"), Fraction("0.3048")
    lb = Fraction("0.45359237")
    lbf = lb * g0
    pi = Fraction(math.pi)

    length, mass, time = _dim(m=1), _dim(kg=1), _dim(s=1)
    for n, s in [("m", "1"), ("km", "1000"), ("cm", "1e-2"), ("mm", "1e-3"), ("um", "1e-6"),
                 ("nm", "1e-9"), ("in", inch), ("ft", foot), ("yd", "0.9144"),
                 ("mi", "1609.344"), ("nmi", "1852")]:
        _add(n, s, length)
    for n, s in [("kg", "1"), ("g", "1e-3"), ("mg", "1e-6"), ("t", "1000"), ("lb", lb),
                 ("oz", lb / 16), ("slug", lb * g0 / foot)]:
        _add(n, s, mass)
    for n, s in [("s", "1"), ("ms", "1e-3"), ("us", "1e-6"), ("min", "60"), ("h", "3600"),
                 ("day", "86400")]:
        _add(n, s, time)

    force = _dim(kg=1, m=1, s=-2)
    for n, s in [("N", "1"), ("kN", "1e3"), ("MN", "1e6"), ("lbf", lbf), ("kgf", g0),
                 ("dyn", "1e-5")]:
        _add(n, s, force)

    pressure = _dim(kg=1, m=-1, s=-2)
    for n, s in [("Pa", "1"), ("kPa", "1e3"), ("MPa", "1e6"), ("GPa", "1e9"), ("bar", "1e5"),
                 ("mbar", "100"), ("atm", "101325"), ("psi", lbf / inch**2),
                 ("ksi", 1000 * lbf / inch**2), ("torr", Fraction(101325, 760)),
                 ("mmHg", "133.322387415")]:
        _add(n, s, pressure)

    energy = _dim(kg=1, m=2, s=-2)
    for n, s in [("J", "1"), ("kJ", "1e3"), ("MJ", "1e6"), ("Wh", "3600"), ("kWh", "3.6e6"),
                 ("cal", "4.184"), ("kcal", "4184"), ("BTU", "1055.05585262"),
                 ("eV", "1.602176634e-19"), ("ftlbf", foot * lbf)]:
        _add(n, s, energy)

    power = _dim(kg=1, m=2, s=-3)
    for n, s in [("W", "1"), ("mW", "1e-3"), ("kW", "1e3"), ("MW", "1e6"),
                 ("hp", 550 * foot * lbf)]:
        _add(n, s, power)

    freq = _dim(s=-1)
    for n, s in [("Hz", "1"), ("kHz", "1e3"), ("MHz", "1e6")]:
        _add(n, s, freq)

    angle = _dim(rad=1)
    for n, s in [("rad", "1"), ("mrad", "1e-3"), ("deg", pi / 180), ("rev", 2 * pi)]:
        _add(n, s, angle)
    _add("rpm", 2 * pi / 60, _dim(rad=1, s=-1))

    temp = _dim(K=1)
    _add("K", "1", temp)
    _add("degC", "1", temp, "273.15")
    _add("degF", Fraction(5, 9), temp, Fraction("459.67") * 5 / 9)
    _add("degR", Fraction(5, 9), temp)
    _add("delta_degC", "1", temp)
    _add("delta_degF", Fraction(5, 9), temp)

    electrical = [
        ("A", _dim(A=1), [("A", "1"), ("mA", "1e-3"), ("uA", "1e-6"), ("kA", "1e3")]),
        ("V", _dim(kg=1, m=2, s=-3, A=-1), [("V", "1"), ("mV", "1e-3"), ("kV", "1e3")]),
        ("ohm", _dim(kg=1, m=2, s=-3, A=-2),
         [("ohm", "1"), ("mohm", "1e-3"), ("kohm", "1e3"), ("Mohm", "1e6")]),
        ("S", _dim(kg=-1, m=-2, s=3, A=2), [("S", "1"), ("mS", "1e-3")]),
        ("F", _dim(kg=-1, m=-2, s=4, A=2),
         [("F", "1"), ("mF", "1e-3"), ("uF", "1e-6"), ("nF", "1e-9"), ("pF", "1e-12")]),
        ("H", _dim(kg=1, m=2, s=-2, A=-2), [("H", "1"), ("mH", "1e-3"), ("uH", "1e-6")]),
        ("C", _dim(s=1, A=1), [("C", "1"), ("mC", "1e-3")]),
        ("Wb", _dim(kg=1, m=2, s=-2, A=-1), [("Wb", "1")]),
        ("T", _dim(kg=1, s=-2, A=-1), [("T", "1"), ("mT", "1e-3")]),
    ]
    for _, d, units in electrical:
        for n, s in units:
            _add(n, s, d)

    volume = _dim(m=3)
    for n, s in [("L", "1e-3"), ("mL", "1e-6"), ("gal", "0.003785411784")]:
        _add(n, s, volume)
    speed = _dim(m=1, s=-1)
    _add("kn", Fraction(1852, 3600), speed)
    _add("mph", "0.44704", speed)
    _add("g0", g0, _dim(m=1, s=-2))
    for n, s in [("mol", "1"), ("mmol", "1e-3"), ("kmol", "1e3")]:
        _add(n, s, _dim(mol=1))


_build_table()
_ALIASES = {"°C": "degC", "°F": "degF", "µm": "um", "μm": "um", "Ω": "ohm", "kΩ": "kohm",
            "MΩ": "Mohm"}
_ONE = _Unit(Fraction(1), _dim())

_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+)|(?P<name>[A-Za-z_°µμΩ][A-Za-z_0-9°µμΩ]*)|(?P<sym>[*/^()\-]))"
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    toks: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        if not text[pos:].strip():
            break
        m = _TOKEN.match(text, pos)
        if m is None:
            raise UnitError(f"unexpected character {text[pos:].strip()[0]!r} in unit {text!r}")
        kind = m.lastgroup or ""
        toks.append((kind, m.group(kind)))
        pos = m.end()
    return toks


def _lookup(name: str) -> _Unit:
    name = _ALIASES.get(name, name)
    unit = _TABLE.get(name)
    if unit is None:
        hint = get_close_matches(name, _TABLE, n=3)
        extra = f"; did you mean {', '.join(repr(h) for h in hint)}?" if hint else ""
        raise UnitError(f"unknown unit {name!r}{extra}")
    return unit


def _no_affine(*units: _Unit) -> None:
    if any(u.affine for u in units):
        raise UnitError(
            "temperature scales with an offset (degC, degF) cannot be combined with other "
            "units or powers; use delta_degC / delta_degF for temperature differences"
        )


def _mul(a: _Unit, b: _Unit) -> _Unit:
    _no_affine(a, b)
    return _Unit(a.scale * b.scale, tuple(x + y for x, y in zip(a.dim, b.dim, strict=True)))


def _div(a: _Unit, b: _Unit) -> _Unit:
    _no_affine(a, b)
    return _Unit(a.scale / b.scale, tuple(x - y for x, y in zip(a.dim, b.dim, strict=True)))


def _pow(a: _Unit, n: int) -> _Unit:
    if n != 1:
        _no_affine(a)
    return _Unit(a.scale**n, tuple(x * n for x in a.dim), a.offset if n == 1 else Fraction(0))


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self) -> tuple[str, str]:
        return self.toks[self.i] if self.i < len(self.toks) else ("end", "")

    def parse(self) -> _Unit:
        if not self.toks:
            raise UnitError("empty unit expression")
        unit = self.expr()
        if self.i != len(self.toks):
            raise UnitError(f"unexpected {self.peek()[1]!r} in unit {self.text!r}")
        return unit

    def expr(self) -> _Unit:
        unit = self.term()
        while self.peek()[0] == "sym" and self.peek()[1] in ("*", "/"):
            op = self.peek()[1]
            self.i += 1
            rhs = self.term()
            unit = _mul(unit, rhs) if op == "*" else _div(unit, rhs)
        return unit

    def term(self) -> _Unit:
        unit = self.atom()
        if self.peek() == ("sym", "^"):
            self.i += 1
            sign = 1
            if self.peek() == ("sym", "-"):
                sign = -1
                self.i += 1
            kind, val = self.peek()
            if kind != "num":
                raise UnitError(f"exponent must be an integer in unit {self.text!r}")
            self.i += 1
            unit = _pow(unit, sign * int(val))
        return unit

    def atom(self) -> _Unit:
        kind, val = self.peek()
        if kind == "name":
            self.i += 1
            return _lookup(val)
        if kind == "num":
            if val != "1":
                raise UnitError(f"only the number 1 is allowed in a unit (got {val!r})")
            self.i += 1
            return _ONE
        if (kind, val) == ("sym", "("):
            self.i += 1
            unit = self.expr()
            if self.peek() != ("sym", ")"):
                raise UnitError(f"missing ')' in unit {self.text!r}")
            self.i += 1
            return unit
        raise UnitError(f"incomplete unit expression {self.text!r}")


@lru_cache(maxsize=512)
def _parse(text: str) -> _Unit:
    if not isinstance(text, str):
        raise UnitError(f"unit must be a string, got {type(text).__name__}")
    return _Parser(text).parse()


def format_dimension(dim: Dim) -> str:
    parts = [f"{b}^{e}" for b, e in zip(_BASE, dim, strict=True) if e != 0]
    return " ".join(parts) if parts else "dimensionless"


def dimension_of(unit: str) -> Dim:
    """Exponents of (m, kg, s, A, K, mol, cd, rad) for a unit expression."""
    return _parse(unit).dim


def is_compatible(unit_a: str, unit_b: str) -> bool:
    return dimension_of(unit_a) == dimension_of(unit_b)


def known_units() -> list[str]:
    return sorted(_TABLE)


def _check_compatible(f: _Unit, t: _Unit, from_unit: str, to_unit: str) -> None:
    if f.dim != t.dim:
        raise UnitError(
            f"cannot convert {from_unit!r} [{format_dimension(f.dim)}] "
            f"to {to_unit!r} [{format_dimension(t.dim)}]"
        )


def conversion_factor(from_unit: str, to_unit: str) -> float:
    """Multiplicative factor; not defined for offset temperature scales."""
    f, t = _parse(from_unit), _parse(to_unit)
    _check_compatible(f, t, from_unit, to_unit)
    if f.affine or t.affine:
        raise UnitError("conversion with degC/degF is not a pure factor; use convert()")
    return float(f.scale / t.scale)


def convert(value, from_unit: str, to_unit: str):
    """Convert a number or array between compatible units.

    Returns a float for scalar input and a new float64 ndarray for array input.
    """
    f, t = _parse(from_unit), _parse(to_unit)
    _check_compatible(f, t, from_unit, to_unit)
    raw = np.asarray(value)
    if raw.dtype.kind not in "biuf":
        raise ValidationError(f"value must be numeric, got {raw.dtype}")
    a = float(f.scale / t.scale)
    b = float((f.offset - t.offset) / t.scale)
    out = raw.astype(float) * a
    if b != 0.0:
        out = out + b
    return float(out) if out.ndim == 0 else out
