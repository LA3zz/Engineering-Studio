"""Thermodynamics, fluid mechanics and heat transfer toolboxes against textbook values."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.toolboxes.fluids import functions as fl
from engstudio.toolboxes.heat import functions as ht
from engstudio.toolboxes.thermo import functions as th


# ------------------------------------------------------------------------ thermodynamics
def test_ideal_gas_each_unknown():
    p, V, m, T = 101325.0, 1.0, 101325 / (287 * 300), 300.0
    assert th.ideal_gas(None, V, m, T) == pytest.approx(p)
    assert th.ideal_gas(p, None, m, T) == pytest.approx(V)
    assert th.ideal_gas(p, V, None, T) == pytest.approx(m)
    assert th.ideal_gas(p, V, m, None) == pytest.approx(T)
    with pytest.raises(EngStudioError, match="exactly three"):
        th.ideal_gas(p, V, None, None)


def test_processes_first_law():
    iso = th.gas_process("isothermal", 2e5, 0.1, 0.2)
    assert iso.p2 == pytest.approx(1e5) and iso.W == pytest.approx(2e4 * math.log(2))
    assert iso.dU == pytest.approx(0, abs=1e-9) and iso.Q == pytest.approx(iso.W)
    s = th.gas_process("isentropic", 1e5, 1.0, 0.5, m=1.0)
    assert s.p2 == pytest.approx(1e5 * 2 ** 1.4) and s.Q == pytest.approx(0, abs=1e-6)
    b = th.gas_process("isobaric", 1e5, 0.1, 0.3)
    assert b.W == pytest.approx(2e4) and b.Q == pytest.approx(b.dU + b.W)
    with pytest.raises(EngStudioError, match="isochoric"):
        th.gas_process("isochoric", 1e5, 0.1, 0.1)


def test_cycles_and_cop():
    assert th.cycle_efficiency("carnot", 800, 300).efficiency == pytest.approx(0.625)
    assert th.cycle_efficiency("otto", 8).efficiency == pytest.approx(1 - 8 ** -0.4)
    d = th.cycle_efficiency("diesel", 18, 2).efficiency
    assert d == pytest.approx(1 - 18 ** -0.4 * (2 ** 1.4 - 1) / (1.4 * 1), rel=1e-12)
    assert d < th.cycle_efficiency("otto", 18).efficiency  # Otto > Diesel at equal r
    assert th.cycle_efficiency("brayton", 10).efficiency == pytest.approx(
        1 - 10 ** (-0.4 / 1.4))
    assert th.cop("refrigerator", 270, 300) == pytest.approx(9)
    assert th.cop("heat_pump", 270, 300) == pytest.approx(10)


def test_entropy_and_isentropic():
    T2 = th.isentropic_temperature(300, 8)
    assert th.entropy_change(300, T2, 1e5, 8e5) == pytest.approx(0, abs=1e-9)
    assert th.entropy_change(300, 600, 1e5, 1e5) == pytest.approx(1004.5 * math.log(2))


# ----------------------------------------------------------------------------- fluids
def test_reynolds_and_friction():
    assert fl.reynolds(1, 0.1, 1000, 1e-3) == pytest.approx(1e5)
    assert fl.friction_factor(1000) == pytest.approx(0.064)
    f = fl.friction_factor(1e5, 1e-4)
    assert 1 / math.sqrt(f) == pytest.approx(
        -2 * math.log10(1e-4 / 3.7 + 2.51 / (1e5 * math.sqrt(f))))
    assert fl.friction_factor(1e5, 1e-4, "swamee-jain") == pytest.approx(f, rel=0.02)
    assert fl.friction_factor(1e5, 1e-4, "haaland") == pytest.approx(f, rel=0.02)
    assert fl.friction_factor(1e5) == pytest.approx(0.0180, abs=2e-4)  # Moody chart, smooth


def test_pipe_loss_darcy_weisbach():
    r = fl.pipe_loss(0.01, 0.1, 100, 0.0)
    V = 0.01 / (math.pi * 0.0025)
    assert r.V == pytest.approx(V) and r.regime == "turbulent"
    assert r.hf == pytest.approx(r.f * 1000 * V ** 2 / (2 * 9.81))
    assert r.dp == pytest.approx(998 * 9.81 * r.hf)


def test_bernoulli_hydrostatic_pump_drag():
    p2 = fl.bernoulli(2e5, 1, 0, 3, 2)
    assert p2 == pytest.approx(2e5 + 998 * (1 - 9) / 2 - 998 * 9.81 * 2)
    assert fl.hydrostatic(10) == pytest.approx(998 * 9.81 * 10)
    assert fl.pump_power(0.05, 20, 0.8) == pytest.approx(998 * 9.81 * 0.05 * 20 / 0.8)
    assert fl.drag_force(0.5, 1, 10) == pytest.approx(0.5 * 0.5 * 1.225 * 100)
    v = fl.terminal_velocity(80, 1.0, 0.7)
    assert fl.drag_force(1.0, 0.7, v) == pytest.approx(80 * 9.81)
    assert fl.orifice_flow(0.6, 0.01, 1000) == pytest.approx(0.6 * 0.01 * math.sqrt(2000 / 998))
    assert fl.manning(0.013, 2, 4, 0.001) == pytest.approx(2 * 0.5 ** (2 / 3) * 0.001 ** 0.5
                                                           / 0.013)


# ---------------------------------------------------------------------- heat transfer
def test_resistances_and_composite_wall():
    assert ht.conduction_resistance("plane", 0.5, 0.1, 2) == pytest.approx(0.1)
    assert ht.conduction_resistance("cylinder", 15, 0.01, 0.02, 2) == pytest.approx(
        math.log(2) / (2 * math.pi * 15 * 2))
    assert ht.conduction_resistance("sphere", 1, 0.1, 0.2) == pytest.approx(5 / (4 * math.pi))
    q = (100 - 20) / (ht.convection_resistance(10, 2) + ht.conduction_resistance("plane", 0.5,
                                                                                 0.1, 2))
    assert q == pytest.approx(80 / 0.15)


def test_radiation_nusselt_fin():
    q, h = ht.radiation(0.8, 1.0, 400, 300)
    assert q == pytest.approx(0.8 * 5.670374419e-8 * (400 ** 4 - 300 ** 4))
    assert h * (400 - 300) == pytest.approx(q)
    assert ht.nusselt("dittus-boelter", 1e5, 7) == pytest.approx(0.023 * 1e5 ** 0.8 * 7 ** 0.4)
    assert ht.nusselt("flat-plate-laminar", 1e5, 0.7) == pytest.approx(
        0.664 * 1e5 ** 0.5 * 0.7 ** (1 / 3))
    assert ht.nusselt("laminar-tube", 100, 1) == 3.66
    f = ht.fin(25, 200, 0.02, 1e-5, 0.05, 80)
    m = math.sqrt(25 * 0.02 / (200 * 1e-5))
    assert f.m == pytest.approx(m) and 0 < f.efficiency < 1


def test_heat_exchangers():
    d = ht.lmtd(150, 100, 30, 80)
    assert d == pytest.approx(70)  # equal end differences
    d2 = ht.lmtd(150, 90, 30, 70, "counter")
    assert d2 == pytest.approx((80 - 60) / math.log(80 / 60))
    assert ht.effectiveness_ntu(1, 0) == pytest.approx(1 - math.exp(-1))
    assert ht.effectiveness_ntu(2, 1) == pytest.approx(2 / 3)
    assert ht.effectiveness_ntu(1, 0.5, "parallel") == pytest.approx((1 - math.exp(-1.5)) / 1.5)
    with pytest.raises(EngStudioError, match="cross"):
        ht.lmtd(100, 50, 60, 120, "parallel")


def test_lumped_capacitance():
    r = ht.lumped(500, 300, 50, 0.01, 1e-5, 8000, 500, 50, np.array([0.0, 1.0, 1e9]))
    assert r.tau == pytest.approx(8000 * 1e-5 * 500 / (50 * 0.01))
    assert r.T[0] == 500 and r.T[-1] == pytest.approx(300) and r.valid
