"""cd / pwd and the FolderChanged event (Phase 9: Current Folder = working folder)."""

import os
from pathlib import Path

from engstudio.app.kernel.inprocess import InProcessKernelClient, to_function_syntax
from engstudio.app.kernel.protocol import Diagnostics, FolderChanged, Stdout


def run(code):
    k = InProcessKernelClient(threaded=False)
    events = []
    k.subscribe(events.append)
    k.execute(code, None)
    k.shutdown()
    return k, events


def test_command_syntax_rewrites_paths():
    assert to_function_syntax("cd ..") == "cd('..')"
    assert to_function_syntax("cd C:\\my data;") == "cd('C:\\my data');"
    assert to_function_syntax("cd sub % go") == "cd('sub') % go"
    assert to_function_syntax("cd('x')") == "cd('x')"
    assert to_function_syntax("cd = 3;") == "cd = 3;"


def test_cd_changes_folder_and_reports_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "d.csv").write_text("1,2\n3,4\n")
    k, events = run("cd sub\nA = readmatrix('d.csv'); p = pwd; old = cd('..'); cd")
    assert not [d for e in events if isinstance(e, Diagnostics) for d in e.items]
    ws = k._interp.workspace
    assert ws["A"].tolist() == [[1, 2], [3, 4]]
    assert Path(ws["p"].to_str()) == tmp_path / "sub"
    assert Path(ws["old"].to_str()) == tmp_path / "sub" and Path.cwd() == tmp_path
    moved = [e.path for e in events if isinstance(e, FolderChanged)]
    assert [Path(p) for p in moved] == [tmp_path / "sub", tmp_path]
    out = "".join(e.text for e in events if isinstance(e, Stdout))
    assert str(tmp_path) in out  # bare ``cd`` prints the folder


def test_cd_to_missing_folder_is_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, events = run("cd no_such_folder")
    msgs = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
    assert msgs and "cannot change" in msgs[0] and os.getcwd() == str(tmp_path)
