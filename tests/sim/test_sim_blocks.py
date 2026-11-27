"""Block framework and math blocks (Phase 7, S2)."""

import numpy as np
import pytest

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BLOCK_TYPES, block_type, ports, resolve
from engstudio.sim.model import Block


def run(block: Block, *inputs):
    bt = block_type(block.type)
    impl = bt.impl(resolve(block))
    return impl.outputs(0.0, impl.initial_state(), [np.atleast_1d(np.asarray(u, float))
                                                    for u in inputs])


def test_library_has_math_blocks():
    assert {"Constant", "Gain", "Sum", "Product", "Abs", "MathFunction"} <= set(BLOCK_TYPES)
    for bt in BLOCK_TYPES.values():
        assert bt.doc and bt.category


def test_defaults_and_ports():
    assert ports(Block("s1", "Sum")) == (2, 1)
    assert ports(Block("s1", "Sum", params={"Signs": "|+--"})) == (3, 1)
    assert ports(Block("c1", "Constant")) == (0, 1)
    assert ports(Block("p1", "Product", params={"Operations": "*/*"})) == (3, 1)
    assert resolve(Block("g1", "Gain"))["K"].tolist() == [1.0]


def test_block_outputs():
    assert run(Block("c", "Constant", params={"Value": [1, 2]}))[0].tolist() == [1, 2]
    assert run(Block("g", "Gain", params={"K": 2.5}), 4)[0].tolist() == [10]
    assert run(Block("s", "Sum", params={"Signs": "+-+"}), 5, 2, 1)[0].tolist() == [4]
    assert run(Block("p", "Product", params={"Operations": "*/"}), 6, 3)[0].tolist() == [2]
    assert run(Block("a", "Abs"), [-3, 2])[0].tolist() == [3, 2]
    assert run(Block("m", "MathFunction", params={"Function": "sqrt"}), 9)[0].tolist() == [3]
    assert run(Block("g", "Gain", params={"K": [1, 2]}), [3, 4])[0].tolist() == [3, 8]


def test_feedthrough_flags():
    assert block_type("Gain").feedthrough and not block_type("Constant").feedthrough


@pytest.mark.parametrize("block, text", [
    (Block("x", "Nope"), "unknown block type"),
    (Block("g", "Gain", params={"Gain": 2}), "unknown parameter"),
    (Block("g", "Gain", params={"K": "two"}), "finite numbers"),
    (Block("s", "Sum", params={"Signs": "+*"}), "only \\+ and -"),
    (Block("p", "Product", params={"Operations": ""}), "only \\* and /"),
    (Block("m", "MathFunction", params={"Function": "cube"}), "must be one of"),
])
def test_bad_parameters_reported_before_running(block, text):
    with pytest.raises(ValidationError, match=text):
        resolve(block)
