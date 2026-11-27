"""Every script in examples/ runs from start to end without an error (Phase 9 integration).

Scripts run as F5 does: with the script's own path, from an empty working folder (so files a
script writes land in a temporary folder and data files are found next to the script)."""

from pathlib import Path

import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics, ExecutionFinished, Stdout

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
SCRIPTS = sorted(EXAMPLES.glob("*.m"))


def test_examples_exist():
    names = {p.name for p in SCRIPTS}
    assert {"mechanical_example.m", "thermo_fluids_example.m", "electrical_example.m",
            "fea_example.m", "lab_data_example.m", "robotics_aero_example.m",
            "simulation_example.m", "control_pid_example.m"} <= names


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_example_runs_clean(script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    k = InProcessKernelClient(threaded=False)
    events = []
    k.subscribe(events.append)
    try:
        k.execute(script.read_text(encoding="utf-8"), str(script))
    finally:
        k.shutdown()
    errors = [f"line {d.line}: {d.message}" if getattr(d, "line", None) else d.message
              for e in events if isinstance(e, Diagnostics) for d in e.items
              if getattr(d, "severity", "error") == "error"]
    assert not errors, f"{script.name}: {errors}"
    status = [e.status for e in events if isinstance(e, ExecutionFinished)]
    assert status == ["ok"], f"{script.name}: finished with {status}"
    out = "".join(e.text for e in events if isinstance(e, Stdout))
    failed = [line for line in out.splitlines() if line.strip().startswith("FAIL")]
    assert not failed, f"{script.name}: {failed}"  # full_feature_test reports its own checks
