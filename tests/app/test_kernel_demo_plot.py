"""demo_plot command of the stub kernel (emits a sample FigureUpdate)."""

from __future__ import annotations

import numpy as np

from engstudio.app.kernel.protocol import Diagnostics, ExecutionFinished, FigureUpdate
from engstudio.app.kernel.stub import StubKernelClient, demo_figure


def run(code: str):
    client = StubKernelClient()
    got = []
    client.subscribe(got.append)
    client.execute(code)
    return got


def kinds(events):
    return [type(e).__name__ for e in events]


def test_demo_plot_emits_one_figure_update_before_the_summary():
    ev = run("demo_plot")
    assert kinds(ev) == ["FigureUpdate", "WorkspaceSummary", "ExecutionFinished"]
    assert ev[-1].status == "ok"
    assert isinstance(ev[0], FigureUpdate) and ev[0].figure.number == 1


def test_figure_number_argument_and_trailing_semicolon():
    assert [e for e in run("demo_plot 3") if isinstance(e, FigureUpdate)][0].figure.number == 3
    assert [e for e in run("demo_plot;") if isinstance(e, FigureUpdate)][0].figure.number == 1


def test_invalid_figure_number_is_an_error():
    ev = run("demo_plot 0")
    assert not any(isinstance(e, FigureUpdate) for e in ev)
    assert any(isinstance(e, Diagnostics) for e in ev)
    assert [e for e in ev if isinstance(e, ExecutionFinished)][0].status == "error"


def test_bad_arguments_are_errors():
    for line in ("demo_plot x", "demo_plot 1 2", "demo_plot()"):
        ev = run(line)
        assert [e for e in ev if isinstance(e, ExecutionFinished)][0].status == "error", line
        assert not any(isinstance(e, FigureUpdate) for e in ev), line


def test_demo_data_is_computed_not_hard_coded():
    fig = demo_figure(2)
    assert fig.number == 2 and "sample" in fig.title.lower()
    assert (fig.rows, fig.cols, len(fig.axes)) == (1, 2, 2)
    sin_s, cos_s = fig.axes[0].series
    assert np.allclose(sin_s.y, np.sin(sin_s.x)) and np.allclose(cos_s.y, np.cos(cos_s.x))
    assert sin_s.x[0] == 0.0 and abs(sin_s.x[-1] - 2 * np.pi) < 1e-12
    kinds_ = [s.kind for s in fig.axes[1].series]
    assert kinds_ == ["bar", "scatter"]
    assert fig.axes[1].series[0].y.tolist() == [3.0, 5.0, 2.0, 4.0]


def test_variables_still_work_next_to_demo_plot():
    ev = run("x = 5;\ndemo_plot\ny = 2;")
    summary = [e for e in ev if type(e).__name__ == "WorkspaceSummary"][0]
    assert [v.name for v in summary.variables] == ["x", "y"]
