"""Record the planned G7 task (custom theme editor) in TASKS.md and HANDOFF.md.

Idempotent and exact-match: edits only if the anchor lines exist and G7 is not yet recorded.
Backs up both files first. Docs-only; touches no code. Run: python patches\\add_g7_task.py
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "project"
TASKS_ANCHOR = "- [ ] E12b engine API docs page"
HANDOFF_ANCHOR = "**E12b** Engine API docs page"
G7_TASKS = ("- [ ] G7 custom theme editor: View > Theme > Customize... with QColorDialog "
            "per colour role, live preview, contrast warnings, named custom themes saved in "
            "UiSettings, JSON import/export (pure logic module + headless tests); after E12b")
G7_HANDOFF = ("**Then G7** custom theme editor: View > Theme > \"Customize...\" lists the "
              "colour roles of `gui.theme`'s palette, each edited with QColorDialog (wheel, "
              "hex, picker), live preview, contrast warnings via `contrast_ratio` (< 4.5), "
              "named custom themes in UiSettings (JSON) next to Light/Dark, reset to a base "
              "theme, JSON import/export, persisted. Pure module (palette validation, hex "
              "parsing, serialisation) with headless tests; never open a real colour dialog "
              "in tests. BEFORE building, ask the user for `gui/theme.py`, `gui/settings.py`, "
              "`gui/main_window.py` and `tests/gui/test_gui_theme.py`.")


def _read(p: Path) -> str:
    with open(p, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(p: Path, text: str) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, p)


def _add_after(path: Path, anchor: str, new_line: str) -> str:
    text = _read(path)
    if "G7" in text:
        return "G7 already recorded, skipped"
    m = re.search(r"^" + re.escape(anchor) + r"[^\r\n]*", text, flags=re.M)
    if not m:
        return "anchor line not found, skipped"
    nl = "\r\n" if "\r\n" in text else "\n"
    extra = nl + new_line if path.name == "TASKS.md" else nl + nl + new_line
    _write(path, text[:m.end()] + extra + text[m.end():])
    return "G7 added"


def main() -> int:
    names = ["TASKS.md", "HANDOFF.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if missing:
        sys.exit(f"missing in {DOCS}: {missing}. Nothing changed.")
    backup = ROOT / "patches" / f"backup_g7_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    print(f"backup: {backup}")
    print("TASKS.md:", _add_after(DOCS / "TASKS.md", TASKS_ANCHOR, G7_TASKS))
    print("HANDOFF.md:", _add_after(DOCS / "HANDOFF.md", HANDOFF_ANCHOR, G7_HANDOFF))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
