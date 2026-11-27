"""Compiler and runner (Phase 7, S5-S11): whole models against analytic solutions."""

import math

import numpy as np
import pytest

from engstudio.core.errors import ValidationError
from engstudio.sim.compiler import compile_model
from engstudio.sim.model import Block, Model, SolverSettings
from engstudio.sim.runner import SimulationCancelled, run


def chain(*blocks, settings=None, extra_lines=()):
    """Blocks wired output 1 -> input 1 in the given order, plus extra (src, sp, dst, dp)."""
    m = Model("t", settings=settings or SolverSettings(stop_time=5))
    for b in blocks:
        m = m.add_block(b)
    for a, b in zip(blocks, blocks[1:], strict=False):
        m = m.connect(a.id, 1, b.id, 1)
    for src, sp, dst, dp in extra_lines:
        m = m.connect(src, sp, dst, dp)
    return m


def scope(res, sid="scope1", k=0):
    d = res.scopes[sid]
    return d.t, d.signals[k][:, 0]


# ------------------------------------------------------------------------------ compiler
def test_unconnected_input_and_bad_ports():
    m = Model("x").add_block(Block("g1", "Gain")).add_block(Block("scope1", "Scope"))
    with pytest.raises(ValidationError, match="input 1 of block g1"):
        compile_model(m.connect("g1", 1, "scope1", 1))
    m2 = chain(Block("c1", "Constant"), Block("scope1", "Scope"))
    with pytest.raises(ValidationError, match="has 1 output"):
        compile_model(m2.disconnect("scope1", 1).connect("c1", 2, "scope1", 1))


def test_algebraic_loop_is_named():
    m = chain(Block("c1", "Constant"), Block("sum1", "Sum", params={"Signs": "+-"}),
              Block("g1", "Gain"), Block("scope1", "Scope"),
              extra_lines=[("g1", 1, "sum1", 2)])
    with pytest.raises(ValidationError, match="algebraic loop: .*(sum1.*g1|g1.*sum1)"):
        compile_model(m)


def test_order_respects_feedthrough():
    m = chain(Block("c1", "Constant"), Block("g1", "Gain"), Block("g2", "Gain"),
              Block("scope1", "Scope"))
    order = [b.id for b in compile_model(m).blocks]
    assert order.index("c1") < order.index("g1") < order.index("g2")  # sinks may go anywhere


# ------------------------------------------------------------------------- continuous
def test_first_order_step_response():
    m = chain(Block("step1", "Step", params={"StepTime": 1}),
              Block("tf1", "TransferFcn", params={"Num": [1], "Den": [1, 1]}),
              Block("scope1", "Scope"),
              settings=SolverSettings(stop_time=6, rel_tol=1e-8, abs_tol=1e-10))
    t, y = scope(run(m))
    exact = np.where(t >= 1, 1 - np.exp(-(t - 1)), 0.0)
    assert np.max(np.abs(y - exact)) < 1e-6
    assert 1.0 in t.tolist()  # the solver stopped exactly at the step


def msd_model(solver="ode45"):
    """x'' = (F - c x' - k x)/m with m=1, c=0.4, k=4, x(0)=0.1, F=0."""
    m = Model("msd", settings=SolverSettings(stop_time=5, solver=solver, rel_tol=1e-9,
                                             abs_tol=1e-11, fixed_step=0.001))
    for b in (Block("f", "Constant", params={"Value": 0}),
              Block("sum1", "Sum", params={"Signs": "+--"}), Block("inv_m", "Gain"),
              Block("v", "Integrator"), Block("x", "Integrator", params={"InitialCondition": 0.1}),
              Block("c", "Gain", params={"K": 0.4}), Block("k", "Gain", params={"K": 4}),
              Block("scope1", "Scope")):
        m = m.add_block(b)
    for src, dst, dp in (("f", "sum1", 1), ("sum1", "inv_m", 1), ("inv_m", "v", 1),
                         ("v", "x", 1), ("v", "c", 1), ("x", "k", 1), ("c", "sum1", 2),
                         ("k", "sum1", 3), ("x", "scope1", 1)):
        m = m.connect(src, 1, dst, dp)
    return m


@pytest.mark.parametrize("solver, tol", [("ode45", 1e-7), ("ode23", 1e-6), ("ode15s", 1e-5),
                                         ("ode113", 1e-6), ("rk4", 1e-9), ("euler", 3e-3)])
def test_mass_spring_damper_all_solvers(solver, tol):
    t, y = scope(run(msd_model(solver)))
    wn, z = 2.0, 0.1
    wd = wn * math.sqrt(1 - z ** 2)
    exact = 0.1 * np.exp(-z * wn * t) * (np.cos(wd * t) + z * wn / wd * np.sin(wd * t))
    assert np.max(np.abs(y - exact)) < tol


def test_stateless_model_on_a_grid():
    m = chain(Block("s1", "SineWave"), Block("scope1", "Scope"),
              settings=SolverSettings(stop_time=10, max_step=0.1))
    t, y = scope(run(m))
    assert len(t) == 101 and np.max(np.abs(y - np.sin(t))) < 1e-12


# --------------------------------------------------------------------------- discrete
def test_unit_delay_accumulator():
    m = chain(Block("c1", "Constant"), Block("sum1", "Sum"),
              Block("z1", "UnitDelay", params={"SampleTime": 1}), Block("scope1", "Scope"),
              extra_lines=[("z1", 1, "sum1", 2)], settings=SolverSettings(stop_time=5))
    t, y = scope(run(m))
    assert [y[t.tolist().index(k)] for k in range(6)] == [0, 1, 2, 3, 4, 5]


def test_zoh_and_discrete_tf():
    m = chain(Block("s1", "SineWave"), Block("zoh", "ZeroOrderHold",
                                             params={"SampleTime": 0.5}),
              Block("scope1", "Scope"), settings=SolverSettings(stop_time=3, max_step=0.05))
    t, y = scope(run(m))
    held = np.sin(np.floor(t / 0.5 + 1e-9) * 0.5)
    assert np.max(np.abs(y - held)) < 1e-12
    a = 0.5  # y[k+1] = a y[k] + u[k], step input from k = 0
    m2 = chain(Block("c1", "Constant"),
               Block("d1", "DiscreteTransferFcn", params={"Num": [1], "Den": [1, -a],
                                                          "SampleTime": 1}),
               Block("scope1", "Scope"), settings=SolverSettings(stop_time=6))
    t2, y2 = scope(run(m2))
    expect = [sum(a ** j for j in range(k)) for k in range(7)]
    assert [y2[t2.tolist().index(k)] for k in range(7)] == pytest.approx(expect)


def test_hybrid_sampled_feedback():
    """Continuous plant 1/(s+1) with a discrete proportional controller (ZOH)."""
    m = Model("h", settings=SolverSettings(stop_time=10, max_step=0.01))
    for b in (Block("r", "Constant"), Block("e", "Sum", params={"Signs": "+-"}),
              Block("zoh", "ZeroOrderHold", params={"SampleTime": 0.1}),
              Block("kp", "Gain", params={"K": 2}), Block("plant", "TransferFcn"),
              Block("scope1", "Scope")):
        m = m.add_block(b)
    for src, dst, dp in (("r", "e", 1), ("e", "zoh", 1), ("zoh", "kp", 1), ("kp", "plant", 1),
                         ("plant", "e", 2), ("plant", "scope1", 1)):
        m = m.connect(src, 1, dst, dp)
    t, y = scope(run(m))
    assert y[-1] == pytest.approx(2 / 3, rel=1e-3)  # steady state K/(1+K)


# --------------------------------------------------------------------- nonlinear, control
def test_saturation_fcn_switch():
    m = chain(Block("r", "Ramp", params={"Slope": 1}),
              Block("sat", "Saturation", params={"UpperLimit": 2, "LowerLimit": -1}),
              Block("f", "Fcn", params={"Expression": "u^2 + 1"}), Block("scope1", "Scope"),
              settings=SolverSettings(stop_time=4, max_step=0.1))
    t, y = scope(run(m))
    assert np.max(np.abs(y - (np.minimum(t, 2) ** 2 + 1))) < 1e-12
    sw = Model("s", settings=SolverSettings(stop_time=2, max_step=0.5))
    for b in (Block("a", "Constant", params={"Value": 5}), Block("clk", "Clock"),
              Block("b", "Constant", params={"Value": -5}),
              Block("sw", "Switch", params={"Threshold": 1}), Block("scope1", "Scope")):
        sw = sw.add_block(b)
    for src, dp in (("a", 1), ("clk", 2), ("b", 3)):
        sw = sw.connect(src, 1, "sw", dp)
    t, y = scope(run(sw.connect("sw", 1, "scope1", 1)))
    assert y.tolist() == [-5, -5, 5, 5, 5]


def test_pid_loop_tracks_step():
    m = Model("pid", settings=SolverSettings(stop_time=20, max_step=0.05))
    for b in (Block("r", "Step", params={"StepTime": 0}), Block("e", "Sum", params={"Signs": "+-"}),
              Block("pid", "PIDController", params={"P": 2, "I": 1, "D": 0.5, "N": 50}),
              Block("plant", "TransferFcn", params={"Num": [1], "Den": [1, 1, 0]}),
              Block("scope1", "Scope")):
        m = m.add_block(b)
    for src, dst, dp in (("r", "e", 1), ("e", "pid", 1), ("pid", "plant", 1), ("plant", "e", 2),
                         ("plant", "scope1", 1)):
        m = m.connect(src, 1, dst, dp)
    t, y = scope(run(m))
    assert y[-1] == pytest.approx(1, abs=2e-3) and np.max(y) < 1.6


def test_transport_delay_and_relay():
    m = chain(Block("st", "Step", params={"StepTime": 0.5}),
              Block("d", "TransportDelay", params={"DelayTime": 1}), Block("scope1", "Scope"),
              settings=SolverSettings(stop_time=3, max_step=0.01))
    t, y = scope(run(m))
    assert np.all(y[t < 1.49] == 0) and np.all(y[t > 1.52] == 1)
    # relay with hysteresis driving an integrator: a triangle wave between -1 and +1
    r = Model("relay", settings=SolverSettings(stop_time=10, max_step=0.001))
    for b in (Block("rel", "Relay", params={"OnPoint": 1, "OffPoint": -1, "OnValue": -1,
                                            "OffValue": 1}),
              Block("int", "Integrator"), Block("scope1", "Scope")):
        r = r.add_block(b)
    r = r.connect("rel", 1, "int", 1).connect("int", 1, "rel", 1).connect("int", 1, "scope1", 1)
    t, y = scope(run(r))
    assert y.max() == pytest.approx(1, abs=5e-3) and y.min() == pytest.approx(-1, abs=5e-3)


# ---------------------------------------------------------------------------- subsystems
def test_subsystem_flattens_and_matches():
    inner = Model("inner")
    for b in (Block("in1", "Inport"), Block("g", "Gain", params={"K": 3}),
              Block("out1", "Outport")):
        inner = inner.add_block(b)
    inner = inner.connect("in1", 1, "g", 1).connect("g", 1, "out1", 1)
    m = chain(Block("c1", "Constant", params={"Value": 2}),
              Block("sub1", "Subsystem", subsystem=inner), Block("scope1", "Scope"),
              settings=SolverSettings(stop_time=1, max_step=0.5))
    t, y = scope(run(m))
    assert y.tolist() == [6, 6, 6]
    assert "sub1__g" in [b.id for b in compile_model(m).blocks]


# -------------------------------------------------------------------- outputs, controls
def test_to_workspace_display_outport_and_progress():
    m = chain(Block("clk", "Clock"), Block("g", "Gain", params={"K": 2}),
              Block("tw", "ToWorkspace", params={"VariableName": "y"}),
              settings=SolverSettings(stop_time=2, max_step=0.5))
    m = m.add_block(Block("disp1", "Display")).connect("g", 1, "disp1", 1)
    seen = []
    res = run(m, progress=seen.append)
    assert res.workspace["y"][:, 0].tolist() == [0, 1, 2, 3, 4]
    assert res.displays["disp1"].tolist() == [4] and seen[-1] == 1.0


def test_cancel():
    with pytest.raises(SimulationCancelled):
        run(msd_model(), should_stop=lambda: True)
