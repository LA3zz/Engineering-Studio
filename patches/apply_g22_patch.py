# ruff: noqa: E501
"""Applies the G2.2 edits to src/engstudio/gui/main_window.py and app_main.py.

Run from the project root:  python patches\\apply_g22_patch.py
Each edit must match exactly once, otherwise nothing is written (safe to re-run: it detects
an already patched file and skips it).
"""

from __future__ import annotations

import sys
from pathlib import Path

EDITS = {
    "src/engstudio/gui/main_window.py": [
        (
            "from engstudio.gui.editor_tabs import ScriptTabs\n"
            "from engstudio.gui.panels import PanelSpec, default_panels\n",
            "from engstudio.app.kernel.client import KernelClient\n"
            "from engstudio.gui.command_window import CommandWindow\n"
            "from engstudio.gui.editor_tabs import ScriptTabs\n"
            "from engstudio.gui.kernel_bridge import KernelBridge\n"
            "from engstudio.gui.panels import PanelContext, PanelSpec, default_panels\n",
        ),
        (
            "    def __init__(self, settings: UiSettings | None = None) -> None:\n",
            "    def __init__(\n"
            "        self,\n"
            "        settings: UiSettings | None = None,\n"
            "        kernel: KernelClient | None = None,\n"
            "    ) -> None:\n",
        ),
        (
            "        self._theme_actions: dict[str, QAction] = {}\n",
            "        self._theme_actions: dict[str, QAction] = {}\n"
            "        self.bridge = KernelBridge(kernel, self) if kernel is not None else None\n"
            "        self.command_window = None\n",
        ),
        (
            "        F = QDockWidget.DockWidgetFeature\n",
            "        F = QDockWidget.DockWidgetFeature\n"
            "        ctx = PanelContext(self.bridge, self._history_items())\n",
        ),
        (
            "            dock.setWidget(spec.create())\n",
            "            dock.setWidget(spec.create(ctx))\n",
        ),
        (
            "                dock.toggleViewAction().setShortcut(QKeySequence(spec.shortcut))\n",
            "                dock.toggleViewAction().setShortcut(QKeySequence(spec.shortcut))\n"
            "        widget = self.docks[\"command\"].widget()\n"
            "        self.command_window = widget if isinstance(widget, CommandWindow) else None\n",
        ),
        (
            "        self.act_fullscreen = self._action(",
            "        self.act_focus_cmd = self._action(\"Focus &Command Window\", self.focus_command,\n"
            "                                          \"Ctrl+0\")\n"
            "        self.act_clear_cmd = self._action(\"Clear Command &Window\", self.clear_command,\n"
            "                                          \"Ctrl+Shift+L\")\n"
            "        self.act_fullscreen = self._action(",
        ),
        (
            "        v.addAction(self.act_reset)\n",
            "        v.addAction(self.act_reset)\n"
            "        v.addActions([self.act_focus_cmd, self.act_clear_cmd])\n",
        ),
        (
            "        self._save_window()\n        event.accept()\n",
            "        if self.command_window is not None:\n"
            "            self.settings.set(\"command_history\", self.command_window.history.items())\n"
            "        self._save_window()\n"
            "        if self.bridge is not None:\n"
            "            self.bridge.shutdown()\n"
            "        event.accept()\n",
        ),
        (
            "    # -- actions ---------------------------------------------------------------\n",
            "    # -- command window ----------------------------------------------------------\n"
            "    def _history_items(self) -> list[str]:\n"
            "        raw = self.settings.get(\"command_history\", [])\n"
            "        return [s for s in raw if isinstance(s, str)] if isinstance(raw, list) else []\n"
            "\n"
            "    def focus_command(self) -> None:\n"
            "        if self.command_window is not None:\n"
            "            self.docks[\"command\"].show()\n"
            "            self.docks[\"command\"].raise_()\n"
            "            self.command_window.focus_input()\n"
            "\n"
            "    def clear_command(self) -> None:\n"
            "        if self.command_window is not None:\n"
            "            self.command_window.clear_output()\n"
            "\n"
            "    # -- actions ---------------------------------------------------------------\n",
        ),
    ],
    "src/engstudio/gui/app_main.py": [
        (
            "    from engstudio.gui.main_window import APP_NAME, MainWindow\n",
            "    from engstudio.app.kernel.stub import StubKernelClient\n"
            "    from engstudio.gui.main_window import APP_NAME, MainWindow\n",
        ),
        (
            "    window = MainWindow(UiSettings(None if smoke else default_settings_path()))\n",
            "    window = MainWindow(\n"
            "        UiSettings(None if smoke else default_settings_path()), StubKernelClient()\n"
            "    )\n",
        ),
    ],
}


def main() -> int:
    pending: dict[Path, str] = {}
    for name, edits in EDITS.items():
        path = Path(name)
        if not path.exists():
            print(f"ERROR: {name} not found (run from the project root)")
            return 1
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        if "KernelBridge" in text or "StubKernelClient" in text:
            print(f"skip: {name} already patched")
            continue
        if "\r\n" in text:
            print(f"ERROR: {name} has CRLF line endings; patch not applied")
            return 1
        for old, new in edits:
            if text.count(old) != 1:
                print(f"ERROR: expected exactly one match in {name} for:\n{old}")
                return 1
            text = text.replace(old, new)
        pending[path] = text
    for path, text in pending.items():
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print(f"patched: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
