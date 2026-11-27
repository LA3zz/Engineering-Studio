import os
import re
import subprocess
import sys
from pathlib import Path

from engstudio.__main__ import main
from engstudio.version import APP_NAME, __version__

SRC = Path(__file__).resolve().parents[2] / "src"


def test_version_format():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_main_version_prints(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"{APP_NAME} {__version__}"


def test_python_dash_m_version():
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-m", "engstudio", "--version"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout