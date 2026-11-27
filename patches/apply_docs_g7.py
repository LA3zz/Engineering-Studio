"""Docs update for G7 (idempotent). Run: python patches\\apply_docs_g7.py

ruff, the two G7 test files, full pytest and the GUI smoke must pass first, else nothing is
edited. Backs up the files it touches, appends marker-guarded entries and applies exact-match
edits to HANDOFF.md and TASKS.md. Nothing is deleted.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "project"
PAGE = ROOT / "src" / "engstudio" / "app" / "docs_pages" / "layout-and-themes.md"
MARKER = "<!-- docs G7 -->"
TEST_FILES = ["tests/gui/test_theme_custom.py", "tests/gui/test_theme_editor_gui.py"]

CHANGELOG = """
## {date} - G7
- Custom theme editor: View > Theme > Customize... (`gui.theme_dialog`). Edit every colour
  role (double-click, hex field or QColorDialog), live preview, contrast warnings below 4.5:1,
  named custom themes stored in UiSettings (`custom_themes`), reset to a base theme, JSON
  import/export. Pure logic in `gui.theme_custom` (no Qt).
- `gui.theme`: new `apply_palette(app, palette)`; `apply_theme(app, name)` now calls it.
- `MainWindow`: `custom_themes`, `base_theme()`, custom entries in View > Theme.
"""

API = """
## engstudio.gui.theme_custom (G7, no Qt)
```python
ROLES, ROLE_LABELS, CONTRAST_PAIRS, MIN_CONTRAST = 4.5, MAX_NAME = 40, MAX_THEMES = 50
parse_hex(text) -> "#rrggbb"            # accepts #rgb, rgb, #rrggbb, rrggbb; ValueError
make_palette(name, colors, base) -> Palette   # missing roles come from `base`
contrast_issues(palette, minimum=4.5) -> list[ContrastIssue(fg, bg, ratio)]
role_issues(issues, role) -> str; readable_text_colour(background) -> "#000000" | "#ffffff"
validate_name(name, existing=()) -> str       # not 'light'/'dark', <= 40 chars, no clashes
CustomThemes: names, get, base_of, resolve, set(name, palette, base) -> name, delete(name)
              -> base, to_data(), from_data(data) (bad entries skipped, listed in .errors)
palette_to_json(palette, base) -> str; palette_from_json(text) -> ThemeFile(name, base, palette)
```
Settings key `custom_themes`: `{name: {"base": "light"|"dark", "colors": {role: "#rrggbb"}}}`.
Theme file: `{"format": "engstudio-theme", "version": 1, "name", "base", "colors"}`; missing
colours fall back to the base theme.
`gui.theme.apply_palette(app, palette)` applies any palette; `gui.theme_dialog.ThemeDialog`
(signals `preview_requested(Palette)`, `themes_changed()`, `theme_activated(str)`).
"""

FILES = """
## Added in G7 ({date})
- src/engstudio/gui/theme_custom.py
- src/engstudio/gui/theme_dialog.py
- tests/gui/test_theme_custom.py
- tests/gui/test_theme_editor_gui.py
- Edited: src/engstudio/gui/theme.py, src/engstudio/gui/main_window.py,
  src/engstudio/app/docs_pages/layout-and-themes.md
"""

TESTS = """
## {date} - G7
- tests/gui/test_theme_custom.py and tests/gui/test_theme_editor_gui.py: {n_new} tests (hex
  parsing, palette validation, WCAG contrast pairs with known ratios, names, persistence round
  trips, JSON import/export errors, dialog logic without a real colour dialog, main-window
  integration).
- Full suite: {count} passed, ruff clean, GUI smoke ok.
"""

PAGE_TEXT = """
## Custom themes
Open **View > Theme > Customize...**. Pick a starting theme, then double-click a colour role
(or select it and type a hex value such as `#1f2933`, or press **Pick...**). Every change is
previewed live on the whole window. The last column warns when a text colour has less than
4.5:1 contrast against a background it is drawn on; warnings do not block saving.

Type a name and press **Save** to keep the theme. It then appears in **View > Theme** next to
Light and Dark and is remembered after a restart. **Reset to base** restores the colours of the
chosen base theme, **Delete** removes a saved theme, and **Export...** / **Import...** use a small
JSON file.

The script editor, figure windows, Diagnostics and Documentation panels follow the base theme
(Light or Dark) of a custom theme; they do not use its individual colours yet.
"""


def _run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 1800):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                          env=env)


def _passed(r: subprocess.CompletedProcess, label: str) -> int:
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    m = re.search(r"(\d+) passed", tail)
    print(f"{label}: exit {r.returncode}: {tail}")
    if r.returncode != 0 or not m or re.search(r"\d+ (failed|error)", tail):
        sys.exit(f"{label} failed, no docs edited:\n{r.stdout[-3000:]}{r.stderr[-1000:]}")
    return int(m.group(1))


def run_checks() -> tuple[int, int]:
    r = _run([sys.executable, "-m", "ruff", "check", "src", "tests"])
    print(f"ruff: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"ruff failed, no docs edited:\n{r.stdout}{r.stderr}")
    n_new = _passed(_run([sys.executable, "-m", "pytest", *TEST_FILES, "-q"]), "G7 tests")
    count = _passed(_run([sys.executable, "-m", "pytest", "-q"]), "pytest")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = _run([sys.executable, "-m", "engstudio.gui", "--smoke"], env=env, timeout=180)
    print(f"gui smoke: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"GUI smoke failed, no docs edited:\n{r.stdout}{r.stderr}")
    return count, n_new


def _read(p: Path) -> str:
    with open(p, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(p: Path, text: str) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, p)


def _append(path: Path, block: str) -> str:
    text = _read(path)
    if MARKER in text:
        return "already present, skipped"
    nl = "\r\n" if "\r\n" in text else "\n"
    body = (MARKER + "\n" + block.strip("\n") + "\n").replace("\n", nl)
    sep = "" if text.endswith(nl) else nl
    _write(path, text + sep + nl + body)
    return "appended"


def _edit_line(text: str, prefix: str, new: str) -> tuple[str, bool]:
    m = re.search(r"^" + re.escape(prefix) + r"[^\r\n]*", text, flags=re.M)
    if not m:
        return text, False
    return text[:m.start()] + new + text[m.end():], True


def _edit_handoff(count: int, date: str) -> None:
    p = DOCS / "HANDOFF.md"
    text = _read(p)
    done = []
    text, ok = _edit_line(text, "Last updated:", f"Last updated: {date}, after G7 (docs synced).")
    done.append(("last updated", ok))
    old = "Syntax highlighting done (G4)."
    new = (old + " G7 done: custom theme editor (`gui.theme_custom` pure logic, "
           "`gui.theme_dialog`; View > Theme > Customize...; custom themes in UiSettings key "
           "`custom_themes`; `gui.theme.apply_palette`).")
    ok = old in text and "G7 done" not in text
    text = text.replace(old, new, 1) if ok else text
    done.append(("gui state", ok))
    text, ok = _edit_line(text, "**G7** custom theme editor (details below).",
                          "**Phase 4** scripting: the user pastes the Phase 4 prompt in a "
                          "separate chat. Do not start it unprompted.")
    done.append(("next task", ok))
    text, ok = _edit_line(text, "**G7 details:**",
                          "Known G7 limitation: a custom theme recolours the application "
                          "palette and stylesheet; the script editor, figure windows, "
                          "Diagnostics and Documentation panels follow its base theme "
                          "(light/dark). To colour them too, their set_theme code is needed.")
    done.append(("g7 note", ok))
    text, n = re.subn(r"(`python -m pytest -q` )\d+( passed, ruff clean, GUI smoke ok \()"
                      r"E1-E12b\)", rf"\g<1>{count}\g<2>E1-E12b, G7)", text)
    done.append(("verified line", n > 0))
    _write(p, text)
    for name, ok in done:
        print(f"HANDOFF.md {name}: {'edited' if ok else 'not found, skipped'}")


def _edit_tasks(count: int, date: str) -> None:
    p = DOCS / "TASKS.md"
    text = _read(p)
    text, ok = _edit_line(
        text, "- [ ] G7 custom theme editor",
        f"- [x] G7 (verified {date}, {count} tests) custom theme editor: View > Theme > "
        "Customize..., QColorDialog per colour role, live preview, contrast warnings, named "
        "custom themes in UiSettings, JSON import/export (gui.theme_custom, gui.theme_dialog)")
    if ok:
        _write(p, text)
    print(f"TASKS.md: G7 {'ticked' if ok else 'line not found, skipped'}")


def main() -> int:
    names = ["CHANGELOG.md", "TEST_STATUS.md", "API_REFERENCE.md", "FILE_STRUCTURE.md",
             "HANDOFF.md", "TASKS.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if not PAGE.is_file():
        missing.append(str(PAGE))
    if missing:
        sys.exit(f"missing: {missing}. Nothing changed.")
    count, n_new = run_checks()
    date = time.strftime("%Y-%m-%d")
    backup = ROOT / "patches" / f"backup_docs_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    shutil.copy2(PAGE, backup / PAGE.name)
    print(f"backup: {backup}")
    plan = [(DOCS / "CHANGELOG.md", CHANGELOG.format(date=date)),
            (DOCS / "API_REFERENCE.md", API),
            (DOCS / "FILE_STRUCTURE.md", FILES.format(date=date)),
            (DOCS / "TEST_STATUS.md", TESTS.format(date=date, count=count, n_new=n_new)),
            (PAGE, PAGE_TEXT)]
    for path, block in plan:
        print(f"{path.name}: {_append(path, block)}")
    _edit_handoff(count, date)
    _edit_tasks(count, date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
