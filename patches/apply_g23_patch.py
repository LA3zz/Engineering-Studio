# ruff: noqa: E501
"""Applies the G2.3 edit to src/engstudio/gui/panels.py (Workspace placeholder -> real panel).

Run from the project root:  python patches\\apply_g23_patch.py
All edits must match exactly once or nothing is written; re-running is safe.
"""

from __future__ import annotations

import sys

PATH = "src/engstudio/gui/panels.py"
EDITS = [
    (
        "from engstudio.gui.kernel_bridge import KernelBridge\n",
        "from engstudio.gui.kernel_bridge import KernelBridge\n"
        "from engstudio.gui.workspace_panel import WorkspacePanel\n",
    ),
    (
        "def default_panels() -> list[PanelSpec]:\n",
        "def _workspace(ctx: PanelContext) -> QWidget:\n"
        "    return WorkspacePanel(ctx.bridge)\n"
        "\n"
        "\n"
        "def default_panels() -> list[PanelSpec]:\n",
    ),
    (
        '_placeholder("Workspace", "G2.3"), None, "Ctrl+Shift+3"),',
        '_workspace, None, "Ctrl+Shift+3"),',
    ),
]


def main() -> int:
    try:
        with open(PATH, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {PATH} (run from the project root): {exc}")
        return 1
    if "WorkspacePanel" in text:
        print(f"skip: {PATH} already patched")
        return 0
    if "\r\n" in text:
        print(f"ERROR: {PATH} has CRLF line endings; patch not applied")
        return 1
    for old, new in EDITS:
        if text.count(old) != 1:
            print(f"ERROR: expected exactly one match in {PATH} for:\n{old}")
            return 1
        text = text.replace(old, new)
    with open(PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"patched: {PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
