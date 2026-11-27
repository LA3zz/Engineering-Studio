"""Stub kernel + protocol tests (no Qt). The stub is not an interpreter; these tests pin the
KernelClient event contract that the GUI relies on."""

from __future__ import annotations

import dataclasses

import pytest

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import (
    PROTOCOL_VERSION,
    Diagnostics,
    ExecutionFinished,
    Stdout,
    VariableInfo,
    WorkspaceSummary,
)
from engstudio.app.kernel.stub import StubKernelClient, format_double
from engstudio.core.errors import EngStudioError


def run(code, client=None):
    c = client or StubKernelClient()
    events = []
    c.subscribe(events.append)
    rid = c.execute(code)
    return c, rid, events


def out_text(events):
    return "".join(e.text for e in events if isinstance(e, Stdout))


def test_protocol_version_and_frozen():
    assert PROTOCOL_VERSION == 1
    v = VariableInfo("x", "double", (1, 1), "5")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.name = "y"


def test_stub_is_kernel_client():
    assert isinstance(StubKernelClient(), KernelClient)


def test_assignment_echo_and_summary():
    _, rid, ev = run("x = 5")
    assert out_text(ev) == "x =\n\n     5\n\n"
    assert isinstance(ev[-1], ExecutionFinished) and ev[-1].status == "ok"
    assert ev[-1].request_id == rid
    summary = [e for e in ev if isinstance(e, WorkspaceSummary)][0]
    assert summary.variables == (VariableInfo("x", "double", (1, 1), "5"),)


def test_event_order_summary_before_finished():
    _, _, ev = run("a = 1\nb = 2")
    kinds = [type(e).__name__ for e in ev]
    assert kinds == ["Stdout", "Stdout", "WorkspaceSummary", "ExecutionFinished"]


def test_semicolon_suppresses_echo():
    _, _, ev = run("x = 5;")
    assert out_text(ev) == ""
    assert [e for e in ev if isinstance(e, WorkspaceSummary)][0].variables[0].name == "x"


def test_reassign_and_state_persists_across_calls():
    c, _, _ = run("x = 1;")
    _, _, ev = run("x = 2.5;\ny = -3e2;", c)
    s = [e for e in ev if isinstance(e, WorkspaceSummary)][0]
    assert [(v.name, v.preview) for v in s.variables] == [("x", "2.5000"), ("y", "-300")]


def test_variables_sorted_by_name():
    _, _, ev = run("b = 1;\nA = 2;\na = 3;")
    s = [e for e in ev if isinstance(e, WorkspaceSummary)][0]
    assert [v.name for v in s.variables] == ["A", "a", "b"]


@pytest.mark.parametrize("value,text", [
    (5.0, "5"), (-2.0, "-2"), (2.5, "2.5000"), (0.001, "0.0010"), (1e-5, "1.0000e-05"),
    (123456.0, "123456"), (1e10, "1.0000e+10"), (123456.5, "1.2346e+05"),
])
def test_format_double(value, text):
    assert format_double(value) == text


def test_show_existing_variable_and_undefined():
    c, _, _ = run("x = 7;")
    _, _, ev = run("x", c)
    assert out_text(ev) == "x =\n\n     7\n\n"
    _, _, ev = run("nothere", c)
    d = [e for e in ev if isinstance(e, Diagnostics)][0]
    assert d.items[0].code == "E_STUB" and "nothere" in d.items[0].message
    assert ev[-1].status == "error"


def test_clear_all_and_named():
    c, _, _ = run("a = 1;\nb = 2;\nc = 3;")
    _, _, ev = run("clear a c unknown", c)
    s = [e for e in ev if isinstance(e, WorkspaceSummary)][0]
    assert [v.name for v in s.variables] == ["b"]
    _, _, ev = run("clear", c)
    assert [e for e in ev if isinstance(e, WorkspaceSummary)][0].variables == ()
    assert ev[-1].status == "ok"


def test_unsupported_statement_error_with_location():
    _, _, ev = run("x = 1;\ny = x + 1;\nz = 3;")
    d = [e for e in ev if isinstance(e, Diagnostics)][0].items[0]
    assert d.severity == "error" and d.code == "E_STUB"
    assert d.location.line == 2
    s = [e for e in ev if isinstance(e, WorkspaceSummary)][0]
    assert [v.name for v in s.variables] == ["x"]  # stopped at first error; z not defined
    assert ev[-1].status == "error"


@pytest.mark.parametrize("code", ["1x = 3", "end = 3", "x == 3", "x = ", "= 3", "x = 3 4"])
def test_invalid_statements(code):
    _, _, ev = run(code)
    assert ev[-1].status == "error"
    assert any(isinstance(e, Diagnostics) for e in ev)


def test_comments_and_blank_lines():
    _, _, ev = run("\n% nothing\nx = 4; % trailing comment\n   \n")
    assert ev[-1].status == "ok"
    assert [e for e in ev if isinstance(e, WorkspaceSummary)][0].variables[0].preview == "4"


def test_empty_code_ok():
    _, _, ev = run("")
    assert [type(e).__name__ for e in ev] == ["WorkspaceSummary", "ExecutionFinished"]
    assert ev[-1].status == "ok"


def test_request_ids_increment():
    c = StubKernelClient()
    assert c.execute("x = 1;") == 1 and c.execute("x = 2;") == 2


def test_subscribe_unsubscribe_multiple_handlers():
    c = StubKernelClient()
    a, b = [], []
    off_a = c.subscribe(a.append)
    c.subscribe(b.append)
    c.execute("x = 1;")
    assert len(a) == len(b) == 2
    off_a()
    off_a()  # idempotent
    c.execute("x = 2;")
    assert len(a) == 2 and len(b) == 4


def test_handler_exception_propagates():
    c = StubKernelClient()

    def boom(_e):
        raise RuntimeError("listener bug")

    c.subscribe(boom)
    with pytest.raises(RuntimeError):
        c.execute("x = 1;")


def test_shutdown_blocks_execute_and_cancel_is_noop():
    c = StubKernelClient()
    c.cancel(99)
    c.shutdown()
    with pytest.raises(EngStudioError):
        c.execute("x = 1;")
