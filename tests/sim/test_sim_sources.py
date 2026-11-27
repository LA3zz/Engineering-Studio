"""Source blocks (Phase 7, S3)."""

import math

import numpy as np
import pytest

import engstudio.sim.blocks_sources  # noqa: F401  (registers the source blocks)
from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import block_type, ports, resolve
from engstudio.sim.model import Block


def make(btype, **params):
    block = Block("b1", btype, params=params)
    return block_type(btype).impl(resolve(block)), block


def out(impl, t):
    return impl.outputs(t, np.zeros(0), [])[0].tolist()


def test_step():
    impl, block = make("Step", StepTime=2, Initial=-1, Final=3)
    assert ports(block) == (0, 1)
    assert (out(impl, 1.999), out(impl, 2.0), out(impl, 5)) == ([-1], [3], [3])
    assert impl.breakpoints(0, 10) == [2] and impl.breakpoints(3, 10) == []


def test_sine_ramp_clock():
    s, _ = make("SineWave", Amplitude=2, Frequency=3, Phase=0.5, Bias=1)
    assert out(s, 0.7) == pytest.approx([2 * math.sin(3 * 0.7 + 0.5) + 1])
    r, _ = make("Ramp", Slope=2, StartTime=1, InitialOutput=5)
    assert (out(r, 0.5), out(r, 3)) == ([5], [9]) and r.breakpoints(0, 2) == [1]
    c, _ = make("Clock")
    assert out(c, 4.25) == [4.25]


def test_pulse_generator():
    p, _ = make("PulseGenerator", Amplitude=5, Period=2, PulseWidth=25, PhaseDelay=1)
    assert out(p, 0.5) == [0] and out(p, 1.0) == [5] and out(p, 1.49) == [5]
    assert out(p, 1.6) == [0] and out(p, 3.2) == [5]
    assert p.breakpoints(0, 5) == pytest.approx([1, 1.5, 3, 3.5])


def test_from_workspace_interpolates_and_holds():
    f, _ = make("FromWorkspace", Data=[[0, 0, 10], [1, 2, 20], [3, 2, 0]])
    assert out(f, 0.5) == pytest.approx([1, 15])
    assert out(f, 2) == pytest.approx([2, 10]) and out(f, 9) == pytest.approx([2, 0])


@pytest.mark.parametrize("btype, params, text", [
    ("PulseGenerator", {"PulseWidth": 0}, "between 0 and 100"),
    ("PulseGenerator", {"Period": -1}, "positive"),
    ("FromWorkspace", {"Data": [[0, 1], [0, 2]]}, "must increase"),
    ("FromWorkspace", {"Data": "abc"}, "matrix"),
    ("FromWorkspace", {"Data": [[0], [1]]}, "time column"),
])
def test_bad_parameters(btype, params, text):
    with pytest.raises(ValidationError, match=text):
        resolve(Block("b1", btype, params=params))
