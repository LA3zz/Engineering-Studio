"""Run ONLY after G6.1 works. Checks ruff + pytest + app smoke first; updates docs\\project."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

D = Path("docs/project")

_tasks = D / "TASKS.md"
if not _tasks.exists() or "- [x] G5.3" not in _tasks.read_text(encoding="utf-8-sig"):
    sys.exit("TASKS.md does not show G5.3 as done: run patches\\update_docs_g53.py first.")


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
    return re.sub(r"- \[ \] G6\.1 .*",
                  f"- [x] G6.1 Diagnostics panel ({n} tests, verified {today})", t, count=1)


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G6.1.", t, count=1)
    t = t.replace("Placeholders remain: Documentation, Diagnostics.",
                  "G6.1 done: Diagnostics panel (history across executions, cap 500, severity "
                  "filters, Clear, `location_activated` signal not yet wired to the editor). "
                  "Placeholder remains: Documentation.")
    nxt = ("## Next task\n**G6.2** Documentation panel (`gui.docs_panel`): a `QTextBrowser` "
           "with Back/Forward/Home over local documentation pages (Markdown via Qt's built-in "
           "`setMarkdown`, so no new dependency; internal links between pages; theme-aware). "
           "Pages are read through a small `app` service (the GUI does not touch the file "
           "layout), shipped under `resources/docs` (check how `core.paths` locates resources "
           "and that PyInstaller will include them). Start with an index plus a getting-"
           "started page and one page per implemented GUI feature; function pages from "
           "toolboxes come later.\n")
    t = re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)
    return re.sub(r"\nLater:.*",
                  "\nLater: wire diagnostics `location_activated` to the editor (open file, "
                  "go to line), real kernel process, GUI in the PyInstaller spec, Save/Load "
                  "Workspace, restore open script tabs.", t, count=1)


edit("TASKS.md", tasks)
edit("HANDOFF.md", handoff)
edit("CHANGELOG.md", append(f"\n## {today} - G6.1\n- Diagnostics panel (`gui.diagnostic_log` "
                            "pure history, `gui.diagnostics_panel`): table with severity, "
                            "code, message, location, run; accumulates across executions; "
                            "severity filters; Clear; theme-aware colours.\n"))
edit("TEST_STATUS.md", append(f"\n- {today} G6.1: pytest {n} passed, ruff clean, "
                              "`engstudio.gui --smoke` exit 0 (Windows).\n"))
edit("FILE_STRUCTURE.md", append("\n- src/engstudio/gui/diagnostic_log.py\n"
                                 "- src/engstudio/gui/diagnostics_panel.py\n"
                                 "- tests/gui/test_diagnostic_log.py\n"
                                 "- tests/gui/test_gui_diagnostics_panel.py\n"))
edit("API_REFERENCE.md", append(
    "\n## Diagnostics panel (G6.1)\n"
    "- `engstudio.gui.diagnostic_log.DiagnosticLog(cap=500)`: `add(Diagnostics)`, `clear()`, "
    "`counts()`, `visible(severities)`, `entries`, `dropped`; `location_parts(SourceLoc)` reads "
    "(file, line, column) by field position.\n"
    "- `engstudio.gui.diagnostics_panel.DiagnosticsPanel(bridge, theme)`: signal "
    "`location_activated(file, line, column)`, `activate_row(row)`, `clear()`, "
    "`set_theme(name)`.\n"))
print(f"docs updated ({n} tests)")
