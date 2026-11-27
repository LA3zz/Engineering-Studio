"""Call tips while typing and the Toolbox browser details pane."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from engstudio.app.kernel.protocol import ToolboxFunction, ToolboxInfo  # noqa: E402
from engstudio.gui.calltip import (  # noqa: E402
    CallTipController,
    FunctionCatalog,
    call_context,
    render_tip,
)
from engstudio.gui.editor_tabs import ScriptEditor  # noqa: E402
from engstudio.gui.toolbox_panel import ToolboxPanel  # noqa: E402

PLOT = ToolboxFunction("plot", "2-D lines.", "plot(y) | plot(x, y) | plot(x, y, 'r--o')")
FIN = ToolboxFunction("fin", "Straight fin.", "result = fin(h, k, P, Ac, L, dT)",
                      "full help text", ("h", "k", "P", "Ac", "L", "dT"),
                      ("convection coefficient [W/(m^2*K)]; > 0", "fin conductivity",
                       "fin perimeter", "area", "length", "base minus fluid temperature"))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("text, expected", [
    ("plot(", ("plot", 0)), ("plot(x, ", ("plot", 1)), ("y = plot([1, 2], ", ("plot", 1)),
    ("plot(x, y, 'r,--", ("plot", 2)), ("plot(x', ", ("plot", 1)),
    ("disp('a(b, ", ("disp", 0)), ("f(g(1, 2), ", ("f", 1)), ("f(g(1, ", ("g", 1)),
    ("x = (a + ", None), ("plot(x, y) ", None), ("% plot(", None), ("x = 3", None),
    ("plot(x, {1, 2", ("plot", 1)), ("s.plot(", None),
])
def test_call_context(text, expected):
    assert call_context(text) == expected


def test_render_bolds_the_current_argument():
    tip = render_tip(PLOT, 1)
    assert "<b><u>y</u></b>" in tip and "2-D lines." in tip
    assert tip.index("plot(x, ") < tip.index("color:gray")  # plot(y) has no 2nd input: dimmed
    fin = render_tip(FIN, 0)
    assert "<b><u>h</u></b>" in fin and "<b>h</b>: convection coefficient" in fin
    assert "at most 6 inputs" in render_tip(FIN, 7)


def test_tip_follows_typing_in_the_command_line(app, qtbot):
    catalog = FunctionCatalog()
    catalog.update([ToolboxInfo("x", "X", (PLOT, FIN))])
    line = QLineEdit()
    qtbot.addWidget(line)
    tip = CallTipController(line, catalog, above=True)
    line.show()
    line.setFocus()
    qtbot.waitUntil(line.hasFocus)
    line.setText("fin(25, ")
    assert tip.label.isVisible() and "fin conductivity" in tip.label.text()
    line.setText("fin(25, 200)")
    assert not tip.label.isVisible()
    line.setText("unknown(1, ")
    assert not tip.label.isVisible()


def test_tip_in_the_script_editor(app, qtbot):
    catalog = FunctionCatalog()
    catalog.update([ToolboxInfo("x", "X", (PLOT,))])
    ed = ScriptEditor()
    qtbot.addWidget(ed)
    ed.calltip._catalog = catalog
    ed.show()
    ed.setFocus()
    qtbot.waitUntil(ed.hasFocus)
    ed.setPlainText("t = 0:0.1:1;\nplot(t, ")
    cur = ed.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    ed.setTextCursor(cur)
    assert ed.calltip.label.isVisible() and "<b><u>y</u></b>" in ed.calltip.label.text()
    ed.document().setModified(False)


def test_toolbox_panel_shows_details(app, qtbot):
    p = ToolboxPanel()
    qtbot.addWidget(p)
    p.populate([ToolboxInfo("heat", "Heat Transfer", (FIN,)),
                ToolboxInfo("plotting", "Plotting", (PLOT,))])
    top = p.tree.topLevelItem(0)
    assert not top.isExpanded()
    p.tree.setCurrentItem(top.child(0))
    assert p.details.toPlainText() == "full help text"
    p.tree.setCurrentItem(p.tree.topLevelItem(1).child(0))
    assert "plot(x, y)" in p.details.toPlainText() and "2-D lines." in p.details.toPlainText()
    p.tree.setCurrentItem(top)
    assert p.details.toPlainText() == ""
