"""Block-diagram editor (Phase 7, S13-S16). Headless (offscreen)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math

import numpy as np
import pytest
from PySide6.QtWidgets import QComboBox, QLineEdit

from engstudio.app.sim_service import format_param, parse_param
from engstudio.gui.sim_editor import BlockItem, LineItem, ParamDialog, SettingsDialog, SimEditor
from engstudio.sim import serialization as ser


@pytest.fixture
def editor(qtbot):
    ed = SimEditor()
    ed.ask_to_save = False  # no modal prompt when the test closes the window
    qtbot.addWidget(ed)
    return ed


def build_lag(ed: SimEditor) -> tuple[str, str, str]:
    step = ed.add_block("Step", (0, 0))
    tf = ed.add_block("TransferFcn", (150, 0))
    scope = ed.add_block("Scope", (300, 0))
    assert ed.connect(step, 1, tf, 1) and ed.connect(tf, 1, scope, 1)
    ed.set_block(ed.model.block(step).with_params(StepTime=0.0))
    return step, tf, scope


def test_add_connect_and_canvas_items(editor):
    build_lag(editor)
    blocks = [i for i in editor.scene.items() if isinstance(i, BlockItem)]
    lines = [i for i in editor.scene.items() if isinstance(i, LineItem)]
    assert len(blocks) == 3 and len(lines) == 2
    assert [b.id for b in editor.model.blocks] == ["Step1", "TransferFcn1", "Scope1"]
    assert editor.modified and editor.windowTitle().startswith("*")


def test_new_wire_replaces_old_and_self_loop_refused(editor):
    s1 = editor.add_block("Constant", (0, 0))
    s2 = editor.add_block("Constant", (0, 100))
    g = editor.add_block("Gain", (150, 0))
    editor.connect(s1, 1, g, 1)
    editor.connect(s2, 1, g, 1)
    assert editor.model.inputs_of(g) == {1: (s2, 1)}
    assert not editor.connect(g, 1, g, 1)


def test_delete_undo_redo(editor):
    step, tf, scope = build_lag(editor)
    editor.delete([tf])
    assert tf not in [b.id for b in editor.model.blocks] and not editor.model.lines
    editor.undo()
    assert len(editor.model.lines) == 2
    editor.redo()
    assert len(editor.model.blocks) == 2


def test_run_shows_scope_figures(editor):
    build_lag(editor)
    editor.set_block(editor.model.block("Scope1").with_params(Title="Lag"))
    res = editor.run_blocking()
    t = res.scopes["Scope1"].t
    y = res.scopes["Scope1"].signals[0][:, 0]
    assert np.max(np.abs(y - (1 - np.exp(-t)))) < 1e-3
    assert len(editor.figures) == 1 and "Lag" in editor.figures[0].windowTitle()


def test_parameter_dialog_parses_and_validates(editor, qtbot, monkeypatch):
    tf = editor.add_block("TransferFcn", (0, 0))
    dlg = ParamDialog(editor.model.block(tf), editor._infos["TransferFcn"], editor)
    qtbot.addWidget(dlg)
    num_edit = dlg.fields["Num"][1]
    den_edit = dlg.fields["Den"][1]
    assert isinstance(num_edit, QLineEdit) and den_edit.text() == "[1 1]"
    num_edit.setText("[2 1]")
    den_edit.setText("[1 3 2]")
    dlg.try_accept()
    assert dlg.result_block.param("Den") == (1.0, 3.0, 2.0)
    warnings = []
    monkeypatch.setattr("engstudio.gui.sim_editor.QMessageBox.warning",
                        lambda *a: warnings.append(a[2]))
    den_edit.setText("[0 0]")
    dlg.result_block = None
    dlg.try_accept()
    assert dlg.result_block is None and "denominator" in warnings[-1]


def test_choice_parameters_use_a_combo_box(editor, qtbot):
    m = editor.add_block("MathFunction", (0, 0))
    dlg = ParamDialog(editor.model.block(m), editor._infos["MathFunction"], editor)
    qtbot.addWidget(dlg)
    assert isinstance(dlg.fields["Function"][1], QComboBox)


def test_settings_dialog(editor, qtbot):
    dlg = SettingsDialog(editor.model, editor)
    qtbot.addWidget(dlg)
    dlg.edits["stop_time"].setText("2.5")
    dlg.solver.setCurrentText("rk4")
    ch = dlg.changes()
    assert ch["stop_time"] == 2.5 and ch["solver"] == "rk4" and math.isinf(ch["max_step"])


def test_save_and_open(editor, tmp_path):
    build_lag(editor)
    assert editor.save_to(tmp_path / "lag")
    assert not editor.modified and (tmp_path / "lag.esmodel").exists()
    other = SimEditor()
    other.ask_to_save = False
    assert other.open_path(tmp_path / "lag.esmodel")
    assert other.model == editor.model and len(other.scene.items()) > 0
    other.modified = False
    other.close()


def test_subsystem_editing_flows_back(editor):
    sub = editor.add_block("Subsystem", (0, 0))
    child = editor.open_subsystem(sub)
    child.set_block(child.model.block("Gain1").with_params(K=5.0))
    assert editor.model.block(sub).subsystem.block("Gain1").param("K") == 5.0
    c = editor.add_block("Constant", (-150, 0))
    sc = editor.add_block("Scope", (150, 0))
    editor.connect(c, 1, sub, 1)
    editor.connect(sub, 1, sc, 1)
    res = editor.run_blocking()
    assert res.scopes[sc].signals[0][-1, 0] == 5.0
    child.close()


def test_failed_run_reports_block(editor, monkeypatch):
    editor.add_block("Gain", (0, 0))
    shown = []
    monkeypatch.setattr("engstudio.gui.sim_editor.QMessageBox.warning",
                        lambda *a: shown.append(a[2]))
    editor._failed("input 1 of block Gain1 (Gain) is not connected")
    assert shown and editor.scene.selectedItems()


def test_async_run_and_stop(editor, qtbot):
    build_lag(editor)
    editor.run_async()
    qtbot.waitUntil(lambda: editor.act_run.isEnabled(), timeout=20000)
    assert editor.last_result is not None


def test_param_text_round_trip():
    for kind, text in (("vector", "[1 2 3]"), ("matrix", "[0 1; -4 -0.4]"), ("number", "-inf"),
                       ("vector", "pi")):
        assert format_param(parse_param(kind, text)) in (text, "3.14159")


def test_main_window_simulation_menu(qtbot, tmp_path):
    from engstudio.app.kernel.stub import StubKernelClient
    from engstudio.gui.main_window import MainWindow
    from engstudio.gui.settings import UiSettings
    from engstudio.sim.model import Block, Model

    win = MainWindow(UiSettings(None), StubKernelClient())
    qtbot.addWidget(win)
    menus = {a.text(): a.menu() for a in win.menuBar().actions()}
    assert "&Simulation" in menus
    path = ser.save(Model("m").add_block(Block("c1", "Constant")), tmp_path / "m")
    ed = win.open_model(str(path))
    assert ed is not None and ed.model.block("c1").type == "Constant"
    ed.ask_to_save = False
    ed.close()
