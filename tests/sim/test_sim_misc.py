"""Fcn expressions (safety), subsystem rules and nested .esmodel files."""

import math

import pytest

from engstudio.core.errors import ValidationError
from engstudio.sim import serialization as ser
from engstudio.sim.blocks import ports
from engstudio.sim.blocks_nonlinear import compile_expression
from engstudio.sim.compiler import compile_model, load_library
from engstudio.sim.model import Block, Model

load_library()


@pytest.mark.parametrize("expr, u, t, expected", [
    ("u^2 + 1", 3.0, 0, 10), ("u(1)*u(2)", [2.0, 5.0], 0, 10), ("sin(t) + pi", 0, 0.5,
                                                                math.sin(0.5) + math.pi),
    ("max(u(1), u(2))", [1.0, 4.0], 0, 4), ("-u./2", 4.0, 0, -2), ("atan2(u(2), u(1))",
                                                                   [1.0, 1.0], 0, math.pi / 4),
])
def test_fcn_expressions(expr, u, t, expected):
    import numpy as np
    assert compile_expression(expr)(t, np.atleast_1d(u)) == pytest.approx(expected)


@pytest.mark.parametrize("expr, text", [
    ("__import__('os')", "not allowed|unknown name|only these functions"),
    ("u.real", "not allowed"),
    ("open('x')", "only these functions"), ("lambda: 1", "not allowed"),
    ("u(1) +", "cannot read"), ("'text'", "numbers"), ("x + 1", "unknown name"), ("", "empty"),
])
def test_fcn_rejects_unsafe_or_wrong_input(expr, text):
    with pytest.raises(ValidationError, match=text):
        compile_expression(expr)


def inner(gain=2.0):
    m = Model("inner")
    for b in (Block("in1", "Inport"), Block("g", "Gain", params={"K": gain}),
              Block("out1", "Outport")):
        m = m.add_block(b)
    return m.connect("in1", 1, "g", 1).connect("g", 1, "out1", 1)


def test_subsystem_ports_and_nested_file(tmp_path):
    sub = Block("sub1", "Subsystem", subsystem=inner())
    assert ports(sub) == (1, 1)
    m = (Model("top").add_block(Block("c", "Constant")).add_block(sub)
         .add_block(Block("scope1", "Scope")).connect("c", 1, "sub1", 1)
         .connect("sub1", 1, "scope1", 1))
    back = ser.load(ser.save(m, tmp_path / "nested"))
    assert back == m and back.block("sub1").subsystem.block("g").param("K") == 2.0


def test_subsystem_rules():
    with pytest.raises(ValidationError, match="needs an inner model"):
        Block("s", "Subsystem")
    bad = inner().add_block(Block("in2", "Inport", params={"Port": 3}))
    with pytest.raises(ValidationError, match="numbered"):
        ports(Block("s", "Subsystem", subsystem=bad))
    unwired = Model("u").add_block(Block("out1", "Outport"))
    m = Model("top").add_block(Block("s", "Subsystem", subsystem=unwired)).add_block(
        Block("scope1", "Scope")).connect("s", 1, "scope1", 1)
    with pytest.raises(ValidationError, match="Outport 1 of subsystem s is not connected"):
        compile_model(m)
