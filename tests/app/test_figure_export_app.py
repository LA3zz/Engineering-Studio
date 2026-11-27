"""app.figure_export: the GUI-facing wrapper (needs Matplotlib only when saving)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from engstudio.app.figure_export import EXPORT_FORMATS, save_figure
from engstudio.core.errors import EngStudioError, ValidationError
from engstudio.plotting import export
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec


def spec():
    return FigureSpec(axes=(AxesSpec(series=(SeriesSpec("line", [0, 1], [0, 1]),)),))


def test_formats_are_the_export_formats():
    assert EXPORT_FORMATS is export.EXPORT_FORMATS


def test_save_figure_writes_a_png(tmp_path):
    out = save_figure(spec(), tmp_path / "x.png", dpi=40)
    assert out.read_bytes()[:4] == b"\x89PNG"


def test_errors_pass_through(tmp_path):
    with pytest.raises(ValidationError):
        save_figure(spec(), tmp_path / "x.gif")
    with pytest.raises(EngStudioError):
        save_figure(spec(), tmp_path / "nodir" / "x.png")


def test_importing_the_wrapper_does_not_import_matplotlib():
    code = "import sys, engstudio.app.figure_export; print('matplotlib' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True).stdout.strip()
    assert out == "False"
