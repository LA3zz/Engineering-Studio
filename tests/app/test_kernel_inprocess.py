"""Tests for app.kernel.inprocess (K1): KernelClient contract, errors, cancel, commands."""

import threading
import time

import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient, to_function_syntax
from engstudio.app.kernel.protocol import (
    Diagnostics,
    ExecutionFinished,
    Stdout,
    ToolboxList,
    VariableInfo,
    WorkspaceSummary,
)
from engstudio.core.errors import EngStudioError


def make(threaded=False):
    client = InProcessKernelClient(threaded=threaded)
    events = []
    client.subscribe(events.append)
    return client, events


def of(events, kind, rid=None):
    return [e for e in events if isinstance(e, kind) and (rid is None or e.request_id == rid)]


def text(events, rid=None):
    return "".join(e.text for e in of(events, Stdout, rid))


def diagnostics(events, rid=None):
    return [d for e in of(events, Diagnostics, rid) for d in e.items]


def status(events, rid):
    (finished,) = of(events, ExecutionFinished, rid)
    return finished.status


def variables(events, rid):
    (summary,) = of(events, WorkspaceSummary, rid)
    return {v.name: v for v in summary.variables}


class Waiter:
    """Collects events from the worker thread and lets a test wait for a request."""

    def __init__(self, client):
        self.events = []
        self._cond = threading.Condition()
        client.subscribe(self._on_event)

    def _on_event(self, event):
        with self._cond:
            self.events.append(event)
            self._cond.notify_all()

    def wait_finished(self, rid, timeout=15.0):
        end = time.monotonic() + timeout
        with self._cond:
            while not of(self.events, ExecutionFinished, rid):
                left = end - time.monotonic()
                assert left > 0, f"request {rid} did not finish"
                self._cond.wait(left)


def wait_running(client, rid, timeout=15.0):
    end = time.monotonic() + timeout
    while client._current != rid:
        assert time.monotonic() < end, "request never started"
        time.sleep(0.005)


# ------------------------------------------------------------------- contract
def test_event_order_for_a_simple_statement():
    client, events = make()
    rid = client.execute("x = 5")
    assert [type(e) for e in events] == [Stdout, WorkspaceSummary, ExecutionFinished]
    assert text(events) == "x = 5\n"
    assert variables(events, rid)["x"] == VariableInfo("x", "double", (1, 1), "5")
    assert status(events, rid) == "ok"
    assert isinstance(events[-1], ExecutionFinished)


def test_suppressed_output_and_request_ids():
    client, events = make()
    first = client.execute("x = 5;")
    second = client.execute("y = 6;")
    assert (first, second) == (1, 2)
    assert text(events) == ""
    assert set(variables(events, second)) == {"x", "y"}


def test_multi_line_code_and_display():
    client, events = make()
    client.execute("a = [1 2; 3 4]\nb = a';\ndisp(b)\nfprintf('%d\\n', 7)\na(1, :)")
    assert text(events) == (
        "a =\n\n     1     2\n     3     4\n\n"
        "     1     3\n     2     4\n7\n"
        "ans =\n\n     1     2\n\n"
    )


def test_workspace_persists_and_previews():
    client, events = make()
    rid = client.execute(
        "n = 5; v = [1 2 3]; M = eye(2); s = 'hello'; c = {1, 'a'}; t.a = 1; f = @(x) x + 1;"
        " z = 3 + 4i; e = [];")
    info = variables(events, rid)
    assert list(info) == sorted(info)
    assert (info["n"].cls, info["n"].size, info["n"].preview) == ("double", (1, 1), "5")
    assert (info["v"].size, info["v"].preview) == ((1, 3), "1x3 double")
    assert info["s"].cls == "char" and info["s"].preview == "'hello'"
    assert (info["c"].cls, info["c"].preview) == ("cell", "1x2 cell")
    assert (info["t"].cls, info["t"].preview) == ("struct", "1x1 struct")
    assert (info["f"].cls, info["f"].preview) == ("function_handle", "@(x) x + 1")
    assert info["z"].preview == "3 + 4i" and info["e"].preview == "[]"
    rid2 = client.execute("m = n * 2;")
    assert "n" in variables(events, rid2) and variables(events, rid2)["m"].preview == "10"


# --------------------------------------------------------------------- errors
def test_runtime_error_has_location_and_workspace_summary():
    client, events = make()
    rid = client.execute("a = 1;\ny = [1 2 3] * [4 5 6];")
    (diag,) = diagnostics(events, rid)
    assert (diag.severity, diag.code) == ("error", "E_EVAL")
    assert "matrix multiplication" in diag.message
    assert (diag.location.line, diag.location.col) == (2, 13)
    assert status(events, rid) == "error"
    assert "a" in variables(events, rid)
    assert isinstance(events[-1], ExecutionFinished)


def test_file_name_is_used_in_diagnostic_locations():
    client, events = make()
    rid = client.execute("x = 1;\ny = [1 2] * [3 4];", "demo.m")
    (diag,) = diagnostics(events, rid)
    assert (diag.location.file, diag.location.line) == ("demo.m", 2)
    rid = client.execute("x = * 3", "other.m")
    assert diagnostics(events, rid)[0].location.file == "other.m"
    rid = client.execute("q = [1 2] * [3 4];")
    assert diagnostics(events, rid)[0].location.file is None


def test_parse_and_lex_errors():
    client, events = make()
    rid = client.execute("x = * 3")
    (diag,) = diagnostics(events, rid)
    assert diag.code == "E_PARSE" and (diag.location.line, diag.location.col) == (1, 5)
    rid = client.execute("ok = 1;\nx = (1 + 2")
    (diag,) = diagnostics(events, rid)
    assert diag.code == "E_LEX" and diag.location.line == 2
    assert status(events, rid) == "error" and "ok" not in variables(events, rid)


def test_error_inside_functions_lists_the_call_stack():
    client, events = make()
    src = (
        "function a()\n  b();\nend\nfunction b()\n  c();\nend\n"
        "function c()\n  undefined_xyz;\nend\na();\n"
    )
    rid = client.execute(src)
    (diag,) = diagnostics(events, rid)
    assert "Undefined function or variable 'undefined_xyz'" in diag.message
    assert "in c (line 5)" in diag.message and "in a (line 10)" in diag.message
    assert diag.location.line == 8


def test_state_survives_an_error():
    client, events = make()
    client.execute("keep = 42;")
    client.execute("boom = nope + 1;")
    rid = client.execute("again = keep + 1")
    assert text(events, rid) == "again = 43\n" and status(events, rid) == "ok"


def test_warnings_are_forwarded_before_the_summary():
    client, events = make()
    rid = client.execute(
        "n = 10; H = zeros(n); for i = 1:n, for j = 1:n, H(i, j) = 1/(i+j-1); end; end;"
        " x = inv(H);")
    (diag,) = diagnostics(events, rid)
    assert (diag.severity, diag.code) == ("warning", "ILL_CONDITIONED")
    assert status(events, rid) == "ok"
    kinds = [type(e) for e in events]
    assert kinds.index(Diagnostics) < kinds.index(WorkspaceSummary)


def test_internal_errors_do_not_break_the_client():
    client, events = make()
    client._interp.functions["boom"] = lambda args, nargout: 1 / 0
    rid = client.execute("boom();")
    (diag,) = diagnostics(events, rid)
    assert diag.code == "E_INTERNAL" and "ZeroDivisionError" in diag.message
    assert status(events, rid) == "error"
    assert text(events, client.execute("x = 1")) == "x = 1\n"


# ------------------------------------------------------------------- commands
def test_to_function_syntax():
    assert to_function_syntax("clear x y") == "clear('x', 'y')"
    assert to_function_syntax("clc") == "clc()"
    assert to_function_syntax("  format long;") == "  format('long');"
    assert to_function_syntax("clear all % remove everything") == "clear('all')"
    assert to_function_syntax("clear a*") == "clear('a*')"
    for unchanged in ("clear = 5", "clear(1)", "x = 1; clear x", "clearly x", "more = [1 2]"):
        assert to_function_syntax(unchanged) == unchanged
    code = "x = 1\nclear x\ny = 2"
    assert to_function_syntax(code).count("\n") == code.count("\n")


def test_clear_variants():
    client, events = make()
    client.execute("a = 1; b = 2; ab = 3; ac = 4;")
    assert set(variables(events, client.execute("clear a"))) == {"b", "ab", "ac"}
    assert set(variables(events, client.execute("clear a*"))) == {"b"}
    client.execute("p = 1; q = 2;")
    assert set(variables(events, client.execute("clear p q % comment"))) == {"b"}
    assert variables(events, client.execute("clear")) == {}
    client.execute("function y = f(), y = 1; end")
    client.execute("r = 1;")
    assert variables(events, client.execute("clear all")) == {}
    rid = client.execute("f()")
    assert status(events, rid) == "error"  # user functions are cleared by 'clear all'


def test_clear_is_not_a_command_when_used_as_a_variable():
    client, events = make()
    rid = client.execute("clear = 5;")
    assert "clear" in variables(events, rid) and status(events, rid) == "ok"


def test_clc_format_more_who_whos_exist():
    client, events = make()
    rid = client.execute("clc\nmore\nformat short\nformat")
    assert status(events, rid) == "ok" and diagnostics(events, rid) == []
    rid = client.execute("format long")
    (diag,) = diagnostics(events, rid)
    assert diag.code == "W_FORMAT" and status(events, rid) == "ok"
    rid = client.execute("alpha = 1; beta = [1 2];\nwho")
    assert "Your variables are:" in text(events, rid) and "alpha  beta" in text(events, rid)
    rid = client.execute("whos")
    out = text(events, rid)
    assert "Name" in out and "1x2" in out and "double" in out
    rid = client.execute("r = [exist('alpha'), exist('sin'), exist('nonexistent')];")
    assert variables(events, rid)["r"].preview == "1x3 double"
    rid = client.execute("r(1)\nr(2)\nr(3)")
    assert text(events, rid).replace("\n", "").replace(" ", "").replace("ans=", "|") == "|1|5|0"


# -------------------------------------------------------------------- toolboxes
def test_eigenvalues_through_the_kernel():
    client, events = make()
    rid = client.execute("[V, D] = eig([2 1; 1 2]); e = eig([4 1; 2 3]);")
    info = variables(events, rid)
    assert info["V"].size == (2, 2) and info["D"].size == (2, 2) and info["e"].size == (2, 1)
    rid = client.execute("fprintf('%.4f %.4f\\n', e);")
    assert text(events, rid) == "2.0000 5.0000\n"


def test_b1b_functions_work_through_the_kernel():
    client, events = make()
    rid = client.execute("c = cellfun(@(x) x*2, {1,2,3}); s = struct('a', 1); t = upper('abc');"
                         " n = numel(strsplit('a b c'));")
    info = variables(events, rid)
    assert info["c"].preview == "1x3 double" and info["s"].preview == "1x1 struct"
    assert info["t"].preview == "'ABC'" and info["n"].preview == "3"
    rid = client.list_toolboxes()
    (listing,) = of(events, ToolboxList, rid)
    boxes = {tb.name: [f.name for f in tb.functions] for tb in listing.toolboxes}
    assert "cellfun" in boxes["functional"] and "strcmp" in boxes["text"]
    assert "other" not in boxes  # every function is categorised


def test_toolbox_list_reflects_real_functions():
    client, events = make()
    rid = client.list_toolboxes()
    (listing,) = of(events, ToolboxList, rid)
    names = [f.name for tb in listing.toolboxes for f in tb.functions]
    assert len(names) == len(set(names))
    assert {"inv", "sin", "zeros", "disp", "clear", "eig", "svd"} <= set(names)
    decomp_box = next(tb for tb in listing.toolboxes if tb.name == "decomp")
    assert [f.name for f in decomp_box.functions] == ["chol", "eig", "lu", "qr", "svd"]
    assert set(names) == set(client._interp.functions)
    for tb in listing.toolboxes:
        assert [f.name for f in tb.functions] == sorted(f.name for f in tb.functions)
    assert [tb.name for tb in listing.toolboxes][0] == "constants"


# ---------------------------------------------------------------------- threaded
def test_threaded_basic_flow_and_ids():
    client = InProcessKernelClient()
    waiter = Waiter(client)
    try:
        r1 = client.execute("x = 5")
        r2 = client.execute("y = x * 2;")
        waiter.wait_finished(r2)
        assert (r1, r2) == (1, 2)
        assert text(waiter.events, r1) == "x = 5\n"
        assert variables(waiter.events, r2)["y"].preview == "10"
        assert [e.request_id for e in waiter.events] == sorted(e.request_id for e in waiter.events)
    finally:
        client.shutdown()


def test_cancel_a_running_loop():
    client = InProcessKernelClient()
    waiter = Waiter(client)
    try:
        client.execute("keep = 1;")
        rid = client.execute("while 1, end")
        wait_running(client, rid)
        client.cancel(rid)
        waiter.wait_finished(rid)
        assert status(waiter.events, rid) == "cancelled"
        assert "keep" in variables(waiter.events, rid)
        assert isinstance(waiter.events[-1], ExecutionFinished)
        rid2 = client.execute("again = 2")
        waiter.wait_finished(rid2)
        assert status(waiter.events, rid2) == "ok"
    finally:
        client.shutdown()


def test_cancel_a_queued_request_and_ignore_unknown_ids():
    client = InProcessKernelClient()
    waiter = Waiter(client)
    try:
        long_run = client.execute("while 1, end")
        queued = client.execute("never_set = 1;")
        wait_running(client, long_run)
        client.cancel(queued)
        client.cancel(9999)
        client.cancel(long_run)
        waiter.wait_finished(queued)
        waiter.wait_finished(long_run)
        assert status(waiter.events, queued) == "cancelled"
        assert "never_set" not in variables(waiter.events, queued)
        done = client.execute("fine = 1;")
        waiter.wait_finished(done)
        client.cancel(done)  # finished request: no effect
        later = client.execute("also_fine = 1;")
        waiter.wait_finished(later)
        assert status(waiter.events, later) == "ok"
    finally:
        client.shutdown()


def test_shutdown_interrupts_a_running_loop_and_is_idempotent():
    client = InProcessKernelClient()
    rid = client.execute("while 1, end")
    wait_running(client, rid)
    client.shutdown()
    assert not client._thread.is_alive()
    client.shutdown()
    with pytest.raises(EngStudioError):
        client.execute("x = 1")
    with pytest.raises(EngStudioError):
        client.list_toolboxes()


def test_a_failing_handler_does_not_stop_the_worker():
    client = InProcessKernelClient()
    waiter = Waiter(client)

    def bad(event):
        raise RuntimeError("listener bug")

    client.subscribe(bad)
    try:
        rid = client.execute("x = 1")
        waiter.wait_finished(rid)
        assert status(waiter.events, rid) == "ok"
        rid2 = client.execute("y = 2;")
        waiter.wait_finished(rid2)
    finally:
        client.shutdown()


def test_synchronous_mode_propagates_handler_errors():
    client = InProcessKernelClient(threaded=False)

    def bad(event):
        raise RuntimeError("listener bug")

    client.subscribe(bad)
    with pytest.raises(RuntimeError):
        client.execute("x = 1")


def test_clear_all_keeps_the_running_scripts_local_functions():
    from engstudio.app.kernel.protocol import Diagnostics
    kernel = InProcessKernelClient(threaded=False)
    errors = []
    kernel._handlers.append(lambda e: errors.extend(
        d for d in e.items if d.severity == "error") if isinstance(e, Diagnostics) else None)
    kernel.execute("function r = old(x)\nr = x;\nend", None)
    kernel.execute("clear all\ny = twice(4);\nfunction r = twice(x)\nr = 2*x;\nend", None)
    assert not errors and kernel._interp.workspace["y"].item() == 8
    assert "old" not in kernel._interp.user_functions  # earlier functions are cleared
    kernel.shutdown()
