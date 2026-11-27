"""G6.1 patch: put the Diagnostics panel into panels.py and main_window.py (exact-match,
idempotent). Run from the project root: python patches\\apply_g61_patch.py"""

from __future__ import annotations

import sys
from pathlib import Path

GUI = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio/gui")

PANELS = [
    ("from engstudio.gui.command_window import CommandWindow\n",
     "from engstudio.gui.command_window import CommandWindow\n"
     "from engstudio.gui.diagnostics_panel import DiagnosticsPanel\n"),
    ('_placeholder("Diagnostics", "G6"),', "_diagnostics,"),
    ("def _toolboxes(ctx: PanelContext) -> QWidget:\n    return ToolboxPanel(ctx.bridge)\n",
     "def _toolboxes(ctx: PanelContext) -> QWidget:\n    return ToolboxPanel(ctx.bridge)\n\n\n"
     "def _diagnostics(ctx: PanelContext) -> QWidget:\n    return DiagnosticsPanel(ctx.bridge)\n"),
]
_CONNECT = (
    "        if self.bridge is not None:\n"
    "            self.bridge.event.connect(self._on_kernel_event)\n"
)
MAIN = [
    ("from engstudio.gui.command_window import CommandWindow\n",
     "from engstudio.gui.command_window import CommandWindow\n"
     "from engstudio.gui.diagnostics_panel import DiagnosticsPanel\n"),
    (_CONNECT,
     _CONNECT +
     '        diagnostics = self.docks["diagnostics"].widget()\n'
     "        self.diagnostics_panel = (\n"
     "            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None\n"
     "        )\n"),
    ("        for window in self.figures.values():\n            window.set_theme(name)\n",
     "        for window in self.figures.values():\n            window.set_theme(name)\n"
     "        if self.diagnostics_panel is not None:\n"
     "            self.diagnostics_panel.set_theme(name)\n"),
]


def patch(name: str, edits: list[tuple[str, str]]) -> None:
    path = GUI / name
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in edits:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue  # already applied
        if text.count(old) != 1:
            sys.exit(f"{name}: expected text not found exactly once:\n{old}")
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"patched {name}")


patch("panels.py", PANELS)
patch("main_window.py", MAIN)
