"""Simulation model data and .esmodel files (Phase 7, S1)."""

import json
import math

import pytest

from engstudio.core.errors import ValidationError
from engstudio.sim import serialization as ser
from engstudio.sim.model import Block, Line, Model, SolverSettings


def msd_model() -> Model:
    """Mass-spring-damper wiring: Step -> Sum -> Gain(1/m) -> Integrator -> Integrator."""
    m = Model("msd", settings=SolverSettings(stop_time=5, solver="ode45"))
    m = m.add_block(Block("step1", "Step", params={"StepTime": 1.0, "Final": 1.0}))
    m = m.add_block(Block("sum1", "Sum", params={"Signs": "+--"}, position=(100, 0)))
    m = m.add_block(Block("gain1", "Gain", params={"K": 0.5}, position=(200, 0)))
    m = m.add_block(Block("int1", "Integrator", params={"InitialCondition": 0.0}))
    m = m.add_block(Block("int2", "Integrator", params={"InitialCondition": 0.0,
                                                        "UpperLimit": math.inf}))
    m = m.add_block(Block("scope1", "Scope"))
    m = (m.connect("step1", 1, "sum1", 1).connect("sum1", 1, "gain1", 1)
         .connect("gain1", 1, "int1", 1).connect("int1", 1, "int2", 1)
         .connect("int1", 1, "sum1", 2).connect("int2", 1, "sum1", 3)
         .connect("int2", 1, "scope1", 1))
    return m


def test_build_and_query():
    m = msd_model()
    assert len(m.blocks) == 6 and len(m.lines) == 7
    assert m.inputs_of("sum1") == {1: ("step1", 1), 2: ("int1", 1), 3: ("int2", 1)}
    assert m.block("gain1").param("K") == 0.5 and m.block("gain1").name == "gain1"


def test_edits_return_new_models():
    m = msd_model()
    m2 = m.set_params("gain1", K=2).move_block("gain1", (10, 20))
    assert m.block("gain1").param("K") == 0.5 and m2.block("gain1").param("K") == 2.0
    assert m2.block("gain1").position == (10.0, 20.0)
    m3 = m2.remove_block("int1")
    assert all("int1" not in (ln.src, ln.dst) for ln in m3.lines) and len(m3.lines) == 4
    assert m3.disconnect("scope1", 1).inputs_of("scope1") == {}
    assert m.new_id("Gain") == "Gain1" and msd_model().new_id("gain") == "gain2"


def test_params_normalised_and_immutable():
    b = Block("t1", "TransferFcn", params={"Num": [1, 2], "Den": [1, 3, 2]})
    assert b.param("Num") == (1.0, 2.0) and hash(b)
    assert b.with_params(Num=[5]).param("Num") == (5.0,) and b.param("Num") == (1.0, 2.0)


@pytest.mark.parametrize("make, text", [
    (lambda: Block("1bad", "Gain"), "letters"),
    (lambda: Block("ok", ""), "type"),
    (lambda: Block("ok", "Gain", params={"K": float("nan")}), "NaN"),
    (lambda: Block("ok", "Gain", size=(0, 10)), "positive"),
    (lambda: Line("a", 0, "b", 1), "src_port"),
    (lambda: Model(blocks=(Block("a", "Gain"), Block("a", "Gain"))), "duplicate"),
    (lambda: Model(blocks=(Block("a", "Gain"),), lines=(Line("a", 1, "zz", 1),)), "unknown"),
    (lambda: msd_model().connect("step1", 1, "gain1", 1), "two lines"),
    (lambda: SolverSettings(start_time=5, stop_time=1), "after the start"),
    (lambda: SolverSettings(solver="magic"), "solver must be"),
    (lambda: msd_model().block("nope"), "no block"),
])
def test_validation(make, text):
    with pytest.raises(ValidationError, match=text):
        make()


def test_json_round_trip_and_atomic_save(tmp_path):
    m = msd_model().with_settings(max_step=0.1)
    path = ser.save(m, tmp_path / "msd")
    assert path.suffix == ".esmodel" and not (tmp_path / "msd.esmodel.tmp").exists()
    back = ser.load(path)
    assert back == m
    assert back.block("int2").param("UpperLimit") == math.inf
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == ser.SCHEMA_VERSION and data["format"] == "engstudio-model"


def test_infinite_max_step_survives_json():
    m = Model("x")
    assert ser.loads(ser.dumps(m)).settings.max_step == math.inf


@pytest.mark.parametrize("text, msg", [
    ("not json", "valid JSON"),
    ('{"format": "other"}', "not an Engineering Studio"),
    ('{"format": "engstudio-model", "schema_version": 99}', "newer version"),
    ('{"format": "engstudio-model", "schema_version": 1, "blocks": [{"type": "Gain"}]}',
     "damaged"),
])
def test_bad_files(text, msg):
    with pytest.raises(ValidationError, match=msg):
        ser.loads(text)
