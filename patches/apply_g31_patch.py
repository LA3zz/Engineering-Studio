"""G3.1 patch: wire FolderPanel into panels.py and main_window.py (exact-match, idempotent).
Run from the project root: python patches\\apply_g31_patch.py"""

from __future__ import annotations

import sys
from pathlib import Path

GUI = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio/gui")

PANELS = [
    ("from engstudio.gui.command_window import CommandWindow\n"
     "from engstudio.gui.kernel_bridge import KernelBridge\n"
     "from engstudio.gui.workspace_panel import WorkspacePanel\n",
     "from engstudio.gui.command_window import CommandWindow\n"
     "from engstudio.gui.folder_panel import FolderPanel\n"
     "from engstudio.gui.kernel_bridge import KernelBridge\n"
     "from engstudio.gui.settings import UiSettings\n"
     "from engstudio.gui.workspace_panel import WorkspacePanel\n"),
    ("    history_items: list[str] = field(default_factory=list)\n",
     "    history_items: list[str] = field(default_factory=list)\n"
     "    settings: UiSettings | None = None\n"),
    ('_placeholder("Current Folder", "G3"),', "_folder,"),
    ("def default_panels() -> list[PanelSpec]:\n",
     "def _folder(ctx: PanelContext) -> QWidget:\n"
     "    return FolderPanel(ctx.settings)\n\n\n"
     "def default_panels() -> list[PanelSpec]:\n"),
]
MAIN = [
    ("from engstudio.gui.editor_tabs import ScriptTabs\n",
     "from engstudio.gui.editor_tabs import ScriptTabs\n"
     "from engstudio.gui.folder_panel import FolderPanel\n"),
    ("ctx = PanelContext(self.bridge, self._history_items())",
     "ctx = PanelContext(self.bridge, self._history_items(), self.settings)"),
    ("        self.command_window = widget if isinstance(widget, CommandWindow) else None\n",
     "        self.command_window = widget if isinstance(widget, CommandWindow) else None\n"
     "        folder = self.docks[\"folder\"].widget()\n"
     "        self.folder_panel = folder if isinstance(folder, FolderPanel) else None\n"
     "        if self.folder_panel is not None:\n"
     "            self.folder_panel.open_file_requested.connect(self.tabs.open_path)\n"),
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
