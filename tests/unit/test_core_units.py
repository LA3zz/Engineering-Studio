"""Unit conversion tests. Reference values are exact definitions (NIST SP 811, SI brochure)
or simple identities; none are copied from unverified software output."""

import math
from collections import defaultdict

import numpy as np
import pytest

from engstudio.core import units
from engstudio.core.errors import UnitError, ValidationError

convert = units.convert


def close(a, b, rel=1e-12):
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-300)


# ---- exact length / mass / time definitions
def test_length_exact_definitions():
    assert convert(1, "in", "m") == 0.0254
    assert convert(1, "ft", "in") == 12.0
    assert convert(1, "mi", "ft") == 5280.0
    assert convert(1, "mi", "m") == 1609.344
    assert convert(1, "nmi", "m") == 1852.0
    assert close(convert(1, "in", "mm"), 25.4, 1e-15)


def test_mass_time_exact_definitions():
    assert convert(1, "lb", "kg") == 0.45359237
    assert convert(1, "lb", "oz") == 16.0
    assert convert(1, "h", "s") == 3600.0
    assert convert(1, "day", "min") == 1440.0
    assert close(convert(1, "slug", "kg"), 14.593902937206, 1e-12)


# ---- force, pressure, energy, power
def test_force_pressure():
    assert close(convert(1, "lbf", "N"), 4.4482216152605, 1e-14)
    assert convert(1, "kgf", "N") == 9.80665
    assert convert(1, "atm", "Pa") == 101325.0
    assert convert(1, "bar", "kPa") == 100.0
    assert close(convert(1, "psi", "Pa"), 6894.757293168, 1e-12)
    assert close(convert(1, "atm", "psi"), 14.6959487755, 1e-10)
    assert close(convert(760, "torr", "atm"), 1.0, 1e-15)


def test_energy_power():
    assert convert(1, "kWh", "J") == 3.6e6
    assert convert(1, "cal", "J") == 4.184
    assert close(convert(1, "BTU", "J"), 1055.05585262, 1e-14)
    assert close(convert(1, "eV", "J"), 1.602176634e-19, 1e-15)
    assert close(convert(1, "hp", "W"), 745.6998715822702, 1e-14)
    assert close(convert(1, "hp", "ftlbf/s"), 550.0, 1e-14)


# ---- temperature
def test_temperature_points():
    assert close(convert(0, "degC", "K"), 273.15, 1e-15)
    assert convert(0, "degC", "degF") == 32.0
    assert convert(100, "degC", "degF") == 212.0
    assert close(convert(-40, "degC", "degF"), -40.0, 1e-14)
    assert close(convert(32, "degF", "K"), 273.15, 1e-14)
    assert close(convert(491.67, "degR", "K"), 273.15, 1e-14)
    assert close(convert(0, "K", "degC"), -273.15, 1e-15)
    assert close(convert(212, "degF", "degC"), 100.0, 1e-14)


def test_temperature_differences():
    assert close(convert(10, "delta_degC", "delta_degF"), 18.0, 1e-15)
    assert convert(5, "delta_degC", "K") == 5.0


# ---- angle
def test_angle_and_rotation():
    assert close(convert(180, "deg", "rad"), math.pi, 1e-15)
    assert close(convert(1, "rev", "rad"), 2 * math.pi, 1e-15)
    assert close(convert(60, "rpm", "rad/s"), 2 * math.pi, 1e-15)


def test_hz_and_rad_per_s_never_interchangeable():
    with pytest.raises(UnitError, match="cannot convert"):
        convert(1, "Hz", "rad/s")


# ---- compound expressions
def test_compound_units():
    assert close(convert(36, "km/h", "m/s"), 10.0, 1e-15)
    assert close(convert(60, "mph", "km/h"), 96.56064, 1e-14)
    assert close(convert(1, "g0", "m/s^2"), 9.80665, 1e-15)
    assert convert(1, "N*m", "J") == 1.0
    assert convert(1, "kg*m/s^2", "N") == 1.0
    assert convert(1, "kg*m^2/s^3", "W") == 1.0
    assert close(convert(1, "mm^2", "m^2"), 1e-6, 1e-15)
    assert close(convert(1, "L", "m^3"), 1e-3, 1e-15)
    assert close(convert(1, "gal", "L"), 3.785411784, 1e-14)
    assert convert(1, "W/(m*K)", "W/m/K") == 1.0
    assert convert(5, "1/s", "Hz") == 5.0
    assert convert(1, "V/A", "ohm") == 1.0
    assert convert(1, "A*s", "C") == 1.0
    assert convert(1, "N/m^2", "Pa") == 1.0


def test_aliases():
    assert convert(100, "°C", "K") == convert(100, "degC", "K")
    assert convert(1, "kΩ", "ohm") == 1000.0


# ---- arrays and scalars
def test_array_input_and_no_mutation():
    x = np.array([0.0, 100.0])
    out = convert(x, "degC", "K")
    assert isinstance(out, np.ndarray)
    assert np.allclose(out, [273.15, 373.15], rtol=1e-15)
    assert np.array_equal(x, [0.0, 100.0])


def test_scalar_returns_float():
    assert type(convert(1, "m", "mm")) is float
    assert type(convert(np.float64(1), "m", "mm")) is float
    assert type(convert(np.array(1.0), "m", "mm")) is float


def test_identity_and_nan():
    assert convert(123.456, "m", "m") == 123.456
    assert math.isnan(convert(float("nan"), "m", "ft"))


def test_roundtrip_all_compatible_pairs():
    groups = defaultdict(list)
    for u in units.known_units():
        groups[units.dimension_of(u)].append(u)
    checked = 0
    for members in groups.values():
        for a in members:
            for b in members:
                back = convert(convert(123.456, a, b), b, a)
                assert close(back, 123.456, 1e-13), (a, b, back)
                checked += 1
    assert checked > 500


# ---- helpers
def test_conversion_factor():
    assert close(units.conversion_factor("in", "mm"), 25.4, 1e-15)
    with pytest.raises(UnitError, match="not a pure factor"):
        units.conversion_factor("degC", "K")


def test_dimension_helpers():
    assert units.dimension_of("N") == units.dimension_of("kg*m/s^2")
    assert units.is_compatible("psi", "Pa")
    assert not units.is_compatible("m", "s")
    assert units.format_dimension(units.dimension_of("m")) == "m^1"
    assert units.format_dimension(units.dimension_of("1")) == "dimensionless"
    assert "psi" in units.known_units()


# ---- errors
def test_unknown_unit_suggests():
    with pytest.raises(UnitError, match="unknown unit 'metre'"):
        convert(1, "metre", "m")
    with pytest.raises(UnitError, match="did you mean"):
        convert(1, "kpa", "Pa")


def test_incompatible_units():
    with pytest.raises(UnitError, match=r"cannot convert 'm'.*'s'"):
        convert(1, "m", "s")


def test_offset_temperature_not_combinable():
    for bad in ("degC/s", "degC^2", "degF*m"):
        with pytest.raises(UnitError, match="offset"):
            convert(1, bad, "K")


def test_syntax_errors():
    for bad in ("", "  ", "m//s", "(m", "m)", "m^", "m^x", "m^2.5", "2*m", "m $ s", "*m"):
        with pytest.raises(UnitError):
            convert(1, bad, "m")


def test_non_numeric_value_rejected():
    for bad in ("1.5", ["1"], None, 1 + 2j):
        with pytest.raises(ValidationError):
            convert(bad, "m", "m")


def test_unit_must_be_string():
    with pytest.raises(UnitError):
        convert(1, 5, "m")


def test_negative_exponents():
    assert convert(1, "1/s", "s^-1") == 1.0
    assert units.dimension_of("kg*m*s^-2") == units.dimension_of("N")
    assert close(convert(1, "m^-1", "1/mm"), 1e-3, 1e-15)
