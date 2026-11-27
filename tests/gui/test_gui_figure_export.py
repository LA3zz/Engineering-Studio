"""Save As in the Figure window (headless). Dialogs are replaced so no test can block."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from engstudio.app.kernel.stub import StubKernelClient
from engstudio.gui import figure_window
from engstudio.gui.figure_window import FigureWindow
from engstudio.gui.main_window import MainWindow
from engstudio.gui.settings import UiSettings
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec


def spec(number=1):
    s = SeriesSpec("line", [0, 1, 2], [0, 1, 4])
    return FigureSpec(number=number, axes=(AxesSpec(series=(s,), title="T"),))


@pytest.fixture
def warnings(monkeypatch):
    seen = []
    monkeypatch.setattr(figure_window.QMessageBox, "warning",
                        staticmethod(lambda *args, **kw: seen.append(args[1:3])))
    return seen


@pytest.fixture
def win():
    w = FigureWindow(1)
    w.set_figure(spec())
    yield w
    w.hide()
    w.deleteLater()


def choose(monkeypatch, name):
    monkeypatch.setattr(figure_window.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *args, **kw: (str(name) if name else "", "")))


def test_save_action_exists_with_shortcut(win):
    assert win.save_action.shortcut().toString() == "Ctrl+S"
    assert win.save_action.text().replace("&", "") == "Save As..."


def test_save_to_writes_each_format(win, tmp_path, warnings):
    assert win.save_to(tmp_path / "a.png")
    assert (tmp_path / "a.png").read_bytes()[:4] == b"\x89PNG"
    assert win.save_to(tmp_path / "a.svg") and b"<svg" in (tmp_path / "a.svg").read_bytes()[:2000]
    assert win.save_to(tmp_path / "a.pdf") and (tmp_path / "a.pdf").read_bytes()[:5] == b"%PDF-"
    assert warnings == []
    assert win.statusBar().currentMessage().startswith("Saved ")


def test_missing_extension_defaults_to_png(win, tmp_path):
    assert win.save_to(tmp_path / "noext")
    assert (tmp_path / "noext.png").exists() and not (tmp_path / "noext").exists()


def test_unsupported_extension_shows_a_warning_and_writes_nothing(win, tmp_path, warnings):
    assert not win.save_to(tmp_path / "a.jpg")
    assert len(warnings) == 1 and "supported" in warnings[0][1]
    assert list(tmp_path.iterdir()) == []


def test_unwritable_location_shows_a_warning(win, tmp_path, warnings):
    assert not win.save_to(tmp_path / "missing" / "a.png")
    assert len(warnings) == 1 and "cannot write" in warnings[0][1]


def test_save_as_uses_the_chosen_file(win, tmp_path, monkeypatch, warnings):
    choose(monkeypatch, tmp_path / "chosen.png")
    assert win.save_as()
    assert (tmp_path / "chosen.png").exists()


def test_save_as_cancelled_does_nothing(win, tmp_path, monkeypatch, warnings):
    choose(monkeypatch, None)
    assert not win.save_as()
    assert list(tmp_path.iterdir()) == [] and warnings == []


def test_nothing_to_save_before_a_figure_arrives(tmp_path, monkeypatch, warnings):
    w = FigureWindow(2)
    try:
        choose(monkeypatch, tmp_path / "x.png")
        assert not w.save_as() and not w.save_to(tmp_path / "x.png")
        assert list(tmp_path.iterdir()) == []
    finally:
        w.deleteLater()


def test_main_window_figure_can_be_saved(tmp_path):
    main = MainWindow(UiSettings(None), StubKernelClient())
    try:
        main.bridge.execute("demo_plot")
        assert main.figures[1].save_to(tmp_path / "demo.png")
        assert (tmp_path / "demo.png").stat().st_size > 1000
    finally:
        main.tabs.current_editor().document().setModified(False)
        main.close()
        main.deleteLater()
