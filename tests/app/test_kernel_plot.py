"""Kernel integration for plot commands (P5.1): command syntax, events, toolbox listing."""

import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient, to_function_syntax
from engstudio.app.kernel.protocol import FigureClosed, FigureUpdate, ToolboxList


@pytest.mark.parametrize("code, expected", [
    ("hold on", "hold('on')"),
    ("bar(v, 0.6); hold on", "bar(v, 0.6); hold('on')"),
    ("x = A'; hold off, y = 2", "x = A'; hold('off'), y = 2"),
    ("s = 'a; hold on'; z = 1", "s = 'a; hold on'; z = 1"),
    ("if a, hold on, end", "if a, hold('on'), end"),
    ("figure", "figure()"),
    ("figure('Name', 'x'); hold on", "figure('Name', 'x'); hold('on')"),
    ("close all", "close('all')"),
    ("plot(x, y, 'k-')", "plot(x, y, 'k-')"),
    ("x = 1; clc", "x = 1; clc"),  # old behaviour kept
    ("x = 1; clear x", "x = 1; clear x"),
    ("figure(3); close all", "figure(3); close('all')"),
])
def test_command_syntax(code, expected):
    assert to_function_syntax(code) == expected


def test_events_for_plot_and_close():
    kernel = InProcessKernelClient(threaded=False)
    events = []
    kernel._handlers.append(events.append)  # same list that _emit/_safe_emit iterate
    kernel.execute("figure(2); plot([1 2 3]); hold on; plot([3 2 1]); close all", None)
    updates = [e for e in events if isinstance(e, FigureUpdate)]
    assert updates and {u.figure.number for u in updates} == {2}  # throttled: first frame
    assert [e.number for e in events if isinstance(e, FigureClosed)] == [2]
    assert not any(isinstance(e, FigureUpdate) for e in events[events.index(
        next(e for e in events if isinstance(e, FigureClosed))):])  # nothing after close
    kernel.shutdown()


def test_throttled_updates_end_with_the_final_frame():
    kernel = InProcessKernelClient(threaded=False)
    events = []
    kernel._handlers.append(events.append)
    kernel.execute("for k = 1:200, plot(1:k); drawnow limitrate; end", None)
    updates = [e for e in events if isinstance(e, FigureUpdate)]
    assert 1 <= len(updates) < 200  # far fewer frames than loop iterations
    assert updates[-1].figure.axes[0].series[0].n_points == 200  # the last state is shown
    kernel.shutdown()


def test_plotting_toolbox_listed():
    kernel = InProcessKernelClient(threaded=False)
    events = []
    kernel._handlers.append(events.append)
    kernel.list_toolboxes()
    (listing,) = [e for e in events if isinstance(e, ToolboxList)]
    box = {b.name: {f.name for f in b.functions} for b in listing.toolboxes}
    assert {"figure", "plot", "hold", "close"} <= box["plotting"]
    assert "close" not in box.get("workspace", set())
    kernel.shutdown()


def test_user_closing_a_window_resets_that_figure():
    kernel = InProcessKernelClient(threaded=False)
    events = []
    kernel._handlers.append(events.append)
    kernel.execute("figure(1); plot(1:3); hold on; title('old')", None)
    kernel.figure_closed(1)
    kernel.figure_closed(1)  # twice, or for an unknown figure: harmless
    kernel.figure_closed(42)
    events.clear()
    kernel.execute("figure(1); a = ishold;", None)
    update = [e for e in events if isinstance(e, FigureUpdate)][-1]
    assert update.figure.axes == () and update.figure.number == 1
    kernel.shutdown()


def test_threaded_figure_closed_runs_between_requests():
    kernel = InProcessKernelClient(threaded=True)
    done = []
    kernel._handlers.append(lambda e: done.append(e) if type(e).__name__ ==
                            "ExecutionFinished" else None)
    kernel.execute("figure(3); plot(1:2)", None)
    kernel.figure_closed(3)
    kernel.execute("n = numel(get(gcf, 'Number'));", None)
    import time
    t0 = time.monotonic()
    while len(done) < 2 and time.monotonic() - t0 < 10:
        time.sleep(0.01)
    assert len(done) == 2 and kernel._figures.numbers() == [1]  # gcf created a new figure 1
    kernel.shutdown()


def test_drawnow_paces_but_limitrate_skips():
    import time
    kernel = InProcessKernelClient(threaded=False)
    events = []
    kernel._handlers.append(events.append)
    t0 = time.monotonic()
    kernel.execute("for k = 1:10, plot(1:k); drawnow; end", None)
    paced = time.monotonic() - t0
    n_paced = sum(isinstance(e, FigureUpdate) for e in events)
    events.clear()
    t0 = time.monotonic()
    kernel.execute("for k = 1:10, plot(1:k); drawnow limitrate; end", None)
    fast = time.monotonic() - t0
    n_fast = sum(isinstance(e, FigureUpdate) for e in events)
    assert n_paced >= 10 and paced >= 9 * 0.03  # every frame drawn, at the frame rate
    assert n_fast < n_paced and fast < paced
    kernel.shutdown()
