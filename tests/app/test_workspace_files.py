"""save / load in MATLAB .mat format."""

import numpy as np
import pytest
from scipy.io import loadmat, savemat

from engstudio.app.kernel.inprocess import InProcessKernelClient, to_function_syntax
from engstudio.app.kernel.protocol import Diagnostics


@pytest.fixture()
def kernel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    k = InProcessKernelClient(threaded=False)
    yield k
    k.shutdown()


def run(k, code):
    events = []
    k.subscribe(events.append)
    k.execute(code, None)
    diags = [d for e in events if isinstance(e, Diagnostics) for d in e.items]
    return k._interp.workspace, [d.message for d in diags if d.severity == "error"], \
        [d.message for d in diags if d.severity == "warning"]


def test_command_syntax():
    assert to_function_syntax("save results x y") == "save('results', 'x', 'y')"
    assert to_function_syntax("load data.mat") == "load('data.mat')"


def test_round_trip_of_every_storable_type(kernel, tmp_path):
    ws, errors, _ = run(kernel, "A = [1 2; 3 4]; z = 3 + 4i; s = 'steel'; "
                                "c = {1, 'two', [3 4]}; st.E = 200e9; st.name = 'beam'; "
                                "e = []; save('all.mat'); clear; load all")
    assert not errors and (tmp_path / "all.mat").exists()
    assert np.array_equal(ws["A"], [[1, 2], [3, 4]]) and ws["z"].item() == 3 + 4j
    assert ws["s"].to_str() == "steel" and ws["e"].shape == (0, 0)
    assert ws["c"].data[0, 1].to_str() == "two" and ws["c"].data[0, 2].tolist() == [[3, 4]]
    assert ws["st"].get("E").item() == 200e9 and ws["st"].get("name").to_str() == "beam"


def test_selected_variables_default_file_and_struct_output(kernel, tmp_path):
    ws, errors, _ = run(kernel, "a = 1; b = 2; c = 3; save part a c; save; clear; "
                                "S = load('part'); load b_missing_check.mat")
    assert errors and "not found" in errors[0]
    assert sorted(ws["S"].names()) == ["a", "c"]
    assert (tmp_path / "matlab.mat").exists()
    ws, errors, _ = run(kernel, "clear; load; load part c")
    assert not errors and {"a", "b", "c"} <= set(ws.names())


def test_unstorable_values_are_skipped_with_a_warning(kernel, tmp_path):
    ws, errors, warnings = run(kernel, "f = @(x) x.^2; G = tf(1, [1 1]); x = 5; save mix")
    assert not errors and warnings and "f (FunctionHandle)" in warnings[0]
    assert set(loadmat(tmp_path / "mix.mat")) >= {"x"}
    assert "f" not in loadmat(tmp_path / "mix.mat")


def test_loads_files_written_by_other_programs(kernel, tmp_path):
    savemat(tmp_path / "lab.mat", {"counts": np.array([[1, 2, 3]], dtype=np.int32),
                                   "names": np.array(["ab", "cd"]),
                                   "flag": np.array([[True]])})
    ws, errors, _ = run(kernel, "load lab")
    assert not errors
    assert ws["counts"].dtype == np.float64 and ws["counts"].tolist() == [[1, 2, 3]]
    assert ws["names"].data.shape == (2, 2) and ws["flag"].item() == 1


def test_bad_inputs(kernel, tmp_path):
    (tmp_path / "x.csv").write_text("1,2\n")
    _, errors, _ = run(kernel, "load x.csv")
    assert errors and "readmatrix" in errors[0]
    _, errors, _ = run(kernel, "a = 1; save('f.mat', '-ascii')")
    assert errors and "not supported" in errors[0]
    _, errors, _ = run(kernel, "save('g.mat', 'nope')")
    assert errors and "'nope' not found" in errors[0]
