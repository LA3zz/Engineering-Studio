"""The shipped example models load, run and give the physically expected results, and match
the generator script (tools/make_example_models.py)."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from engstudio.sim import serialization as ser
from engstudio.sim.runner import run

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "examples" / "models"


def _generator():
    spec = importlib.util.spec_from_file_location("make_models",
                                                  ROOT / "tools" / "make_example_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", ["mass_spring_damper", "pid_position_loop", "sampled_control"])
def test_files_match_generator(name):
    assert ser.load(MODELS / f"{name}.esmodel") == _generator().MODELS[name]()


def test_mass_spring_damper_matches_exact_solution():
    res = run(ser.load(MODELS / "mass_spring_damper.esmodel"))
    t, x = res.tout, res.workspace["x"][:, 0]
    wn, z = 2.0, 0.1
    wd = wn * math.sqrt(1 - z ** 2)
    tau = np.clip(t - 1, 0, None)
    exact = np.where(t >= 1, 0.25 * (1 - np.exp(-z * wn * tau)
                                    * (np.cos(wd * tau) + z * wn / wd * np.sin(wd * tau))), 0)
    assert np.max(np.abs(x - exact)) < 1e-5


def test_pid_and_sampled_loops_settle():
    pid = run(ser.load(MODELS / "pid_position_loop.esmodel"))
    assert pid.workspace["theta"][-1, 0] == pytest.approx(1.0, abs=0.02)
    sampled = run(ser.load(MODELS / "sampled_control.esmodel"))
    assert next(iter(sampled.scopes.values())).signals[0][-1, 0] == pytest.approx(0.75, rel=1e-3)
