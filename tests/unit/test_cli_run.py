"""``engstudio --run script.m``: run a script headless (used by the frozen-build check)."""

from engstudio.__main__ import main


def test_run_ok_prints_output(tmp_path, capsys):
    script = tmp_path / "ok.m"
    script.write_text("x = 2 + 3\nfprintf('done %d\\n', x);\n", encoding="utf-8")
    assert main(["--run", str(script)]) == 0
    out = capsys.readouterr().out
    assert "x = 5" in out and "done 5" in out


def test_run_error_returns_1(tmp_path, capsys):
    script = tmp_path / "bad.m"
    script.write_text("y = undefined_thing + 1;\n", encoding="utf-8")
    assert main(["--run", str(script)]) == 1
    assert "undefined_thing" in capsys.readouterr().err


def test_run_missing_file_returns_2(tmp_path, capsys):
    assert main(["--run", str(tmp_path / "nope.m")]) == 2
