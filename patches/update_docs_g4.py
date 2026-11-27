"""Run ONLY after G4 works. Checks ruff + pytest + app smoke first; updates docs\\project."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

D = Path("docs/project")


def run(args: list[str]) -> str:
    r = subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True)
    out = r.stdout + r.stderr
    if r.returncode != 0:
        print(out)
        sys.exit(f"{' '.join(args)} FAILED; docs not updated")
    return out


run(["ruff", "check", "."])
out = run(["pytest", "-q"])
run(["engstudio.gui", "--smoke"])  # the real app must exit cleanly too
m = re.search(r"(\d+) passed", out)
if not m:
    sys.exit("could not read pytest summary; docs not updated")
n, today = m.group(1), date.today().isoformat()


def edit(name: str, fn) -> None:
    p = D / name
    if not p.exists():
        print(f"warning: {p} not found, skipped")
        return
    with open(p, encoding="utf-8-sig", newline="") as f:
        t = f.read()
    nl = "\r\n" if "\r\n" in t else "\n"
    new = fn(t.replace("\r\n", "\n"))
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(new.replace("\n", nl))


def append(text: str):
    return lambda t: t.rstrip("\n") + "\n" + text


def tasks(t: str) -> str:
    t = re.sub(r"- \[ \] G4 .*",
               f"- [x] G4 Script editor syntax highlighting ({n} tests, verified {today})", t,
               count=1)
    backlog = "- [ ] Save/Load Workspace (GUI buttons, save/load commands), after the real kernel\n"
    if "Save/Load Workspace" not in t:
        t = t.replace("## Backlog (not scheduled)\n", "## Backlog (not scheduled)\n" + backlog, 1)
    return t


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G4.", t, count=1)
    t = t.replace("No syntax highlighting, no Figure window yet.",
                  "Syntax highlighting done (G4). No Figure window yet.")
    t = t.replace("G3.2 Toolbox browser (",
                  "G4 syntax highlighting (keywords, comments incl. %{ %}, strings, numbers; "
                  "theme-aware; keywords via `app.syntax`), G3.2 Toolbox browser (", 1)
    nxt = ("## Next task\n**G5.1** Figure data model, no Qt: `plotting.model` frozen dataclasses "
           "(`FigureSpec`, `AxesSpec`, `SeriesSpec` with line/scatter/bar styles, labels, "
           "limits, validation of array shapes) + tests, then a `FigureUpdate` event in "
           "`app.kernel.protocol` (plain data, same additive pattern as `ToolboxList`). "
           "**G5.2** then adds `gui.plots` (PyQtGraph renderer in a Figure window; check that "
           "`pyqtgraph` is in the venv and `requirements.lock.txt`) and a stub `demo_plot` "
           "command. Keep to the layer table: `plotting.model` is L1, the GUI renders specs "
           "only.\n")
    t = re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)
    return re.sub(r"\nLater:.*",
                  "\nLater: G6 Documentation + Diagnostics panels, real kernel process, GUI in "
                  "the PyInstaller spec, Save/Load Workspace.", t, count=1)


edit("TASKS.md", tasks)
edit("HANDOFF.md", handoff)
edit("CHANGELOG.md", append(f"\n## {today} - G4\n- Script editor syntax highlighting "
                            "(`gui.highlight_rules` pure tokenizer, `gui.highlighter` Qt "
                            "adapter, `app.syntax` keyword bridge); highlighting follows the "
                            "light/dark theme.\n"))
edit("TEST_STATUS.md", append(f"\n- {today} G4: pytest {n} passed, ruff clean, "
                              "`engstudio.gui --smoke` exit 0 (Windows).\n"))
edit("FILE_STRUCTURE.md", append("\n- src/engstudio/app/syntax.py\n"
                                 "- src/engstudio/gui/highlight_rules.py\n"
                                 "- src/engstudio/gui/highlighter.py\n"
                                 "- tests/gui/test_highlight_rules.py\n"
                                 "- tests/gui/test_gui_highlighter.py\n"
                                 "- tests/app/test_syntax_info.py\n"))
edit("API_REFERENCE.md", append(
    "\n## Syntax highlighting (G4)\n"
    "- `engstudio.app.syntax.SYNTAX_KEYWORDS: frozenset[str]` (mirrors `lang.lexer.KEYWORDS`)\n"
    "- `engstudio.gui.highlight_rules.tokenize_line(text, in_block, keywords) -> "
    "(list[Token], in_block)`\n"))
print(f"docs updated ({n} tests)")
