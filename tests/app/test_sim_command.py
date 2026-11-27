"""sim() and open_system() from scripts (Phase 7, S12)."""

import math

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics, ExecutionFinished, FigureUpdate, OpenModel
from engstudio.sim import serialization as ser
from engstudio.sim.model import Block, Model, SolverSettings


def first_order_model(path):
    m = Model("lag", settings=SolverSettings(stop_time=5, rel_tol=1e-8, abs_tol=1e-10))
    for b in (Block("step1", "Step", params={"StepTime": 0}),
              Block("tf1", "TransferFcn", params={"Num": [1], "Den": [1, 1]}),
              Block("scope1", "Scope", params={"Title": "Lag response"}),
              Block("tw", "ToWorkspace", params={"VariableName": "y"}),
              Block("out1", "Outport")):
        m = m.add_block(b)
    m = (m.connect("step1", 1, "tf1", 1).connect("tf1", 1, "scope1", 1)
         .connect("tf1", 1, "tw", 1).connect("tf1", 1, "out1", 1))
    return ser.save(m, path)


@pytest.fixture
def kernel():
    k = InProcessKernelClient(threaded=False)
    events = []
    k.subscribe(events.append)
    yield k, events
    k.shutdown()


def test_sim_with_output(kernel, tmp_path, monkeypatch):
    k, events = kernel
    first_order_model(tmp_path / "lag.esmodel")
    monkeypatch.chdir(tmp_path)
    k.execute("out = sim('lag'); t = out.tout; y = out.y; yo = out.yout;", None)
    assert [e.status for e in events if isinstance(e, ExecutionFinished)] == ["ok"]
    ws = k._interp.workspace
    t, y = ws["t"][:, 0], ws["y"][:, 0]
    assert np.max(np.abs(y - (1 - np.exp(-t)))) < 1e-6 and ws["yo"].shape[1] == 1
    assert not any(isinstance(e, FigureUpdate) for e in events)  # data form: no plots


def test_sim_without_output_plots_scopes_and_sets_out(kernel, tmp_path, monkeypatch):
    k, events = kernel
    first_order_model(tmp_path / "lag.esmodel")
    monkeypatch.chdir(tmp_path)
    k.execute("sim('lag.esmodel', 'StopTime', 2, 'Solver', 'ode23')", None)
    ws = k._interp.workspace
    assert ws["out"].get("tout")[-1, 0] == pytest.approx(2)
    figs = [e.figure for e in events if isinstance(e, FigureUpdate)]
    assert figs and figs[-1].name == "Lag response"
    s = figs[-1].axes[0].series[0]
    assert s.y[-1] == pytest.approx(1 - math.exp(-2), rel=1e-3)


def test_open_system_event_and_errors(kernel, tmp_path, monkeypatch):
    k, events = kernel
    first_order_model(tmp_path / "lag.esmodel")
    monkeypatch.chdir(tmp_path)
    k.execute("open_system('lag')", None)
    opened = [e.path for e in events if isinstance(e, OpenModel)]
    assert opened and opened[0].endswith("lag.esmodel")
    k.execute("sim('missing')", None)
    k.execute("sim('lag', 'Bogus', 1)", None)
    msgs = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
    assert any("not found" in m for m in msgs) and any("unknown option" in m for m in msgs)
