import os
import subprocess
import sys
from pathlib import Path

from engstudio import selftest

SRC = Path(__file__).resolve().parents[2] / "src"


def _ok() -> None:
    pass


def _bad() -> None:
    raise AssertionError("boom")


def test_run_checks_reports_pass_and_fail():
    lines: list[str] = []
    assert selftest.run_checks([("a", _ok)], lines.append) is True
    assert selftest.run_checks([("a", _ok), ("b", _bad)], lines.append) is False
    assert any(line.startswith("PASS a") for line in lines)
    assert any(line.startswith("FAIL b") and "AssertionError: boom" in line for line in lines)


def test_run_selftest_exit_codes():
    assert selftest.run_selftest([("a", _ok)], out=lambda s: None) == 0
    assert selftest.run_selftest([("b", _bad)], out=lambda s: None) == 1


def test_run_selftest_prints_verdict():
    lines: list[str] = []
    selftest.run_selftest([("a", _ok)], out=lines.append)
    assert lines[0].startswith("Engineering Studio ")
    assert "ALL PASSED" in lines[-1]
    lines.clear()
    selftest.run_selftest([("b", _bad)], out=lines.append)
    assert "FAILURES" in lines[-1]


def test_all_checks_have_unique_names():
    names = [name for name, _ in selftest.CHECKS]
    assert len(names) == len(set(names)) >= 10


def test_selftest_cli_end_to_end():
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-m", "engstudio", "--selftest"],
        capture_output=True, text=True, env=env, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL PASSED" in result.stdout
