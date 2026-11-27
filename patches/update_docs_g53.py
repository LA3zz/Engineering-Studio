"""Run ONLY after G5.3 works. Checks ruff + pytest + app smoke first; updates docs\\project."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

D = Path("docs/project")

_tasks = D / "TASKS.md"
if not _tasks.exists() or "- [x] G5.2" not in _tasks.read_text(encoding="utf-8-sig"):
    sys.exit("TASKS.md does not show G5.2 as done: run patches\\update_docs_g52.py first.")


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
try:
    mplv = version("matplotlib")
except PackageNotFoundError:
    mplv = "unknown"


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
    t = re.sub(r"- \[ \] G5\.3 .*",
               f"- [x] G5.3 Figure export PNG/SVG/PDF ({n} tests, verified {today})", t, count=1)
    return re.sub(r"- \[ \] G6 .*",
                  "- [ ] G6.1 Diagnostics panel\n- [ ] G6.2 Documentation panel", t, count=1)


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G5.3.", t, count=1)
    t = t.replace("stub `demo_plot [N]`.",
                  "stub `demo_plot [N]`; G5.3 done: `plotting.export` (PNG/SVG/PDF, Matplotlib "
                  "Agg, atomic writes, bars drawn on log axes), `app.figure_export`, Save As "
                  "(Ctrl+S) in FigureWindow.", 1)
    nxt = ("## Next task\n**G6.1** Diagnostics panel (`gui.diagnostics_panel`): table of "
           "`Diagnostic` items from `Diagnostics` kernel events (severity colour/icon, code, "
           "message, line:column, which execution), kept across executions (cap 500), Clear "
           "button, severity filter; double-click on a located item emits a signal (jumping to "
           "the editor line is wired later). Replaces the placeholder through a patch of "
           "panels.py/main_window.py. **G6.2** then adds the Documentation panel "
           "(QTextBrowser over local docs in `resources/docs`).\n")
    t = re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)
    return re.sub(r"\nLater:.*",
                  "\nLater: real kernel process, GUI in the PyInstaller spec, Save/Load "
                  "Workspace, restore open script tabs.", t, count=1)


edit("TASKS.md", tasks)
edit("HANDOFF.md", handoff)
edit("CHANGELOG.md", append(f"\n## {today} - G5.3\n- Figure export: `plotting.export` "
                            "(PNG/SVG/PDF via Matplotlib Agg, atomic writes), "
                            "`app.figure_export`, Save As (Ctrl+S) in the Figure window.\n"))
edit("TEST_STATUS.md", append(f"\n- {today} G5.3: pytest {n} passed, ruff clean, "
                              "`engstudio.gui --smoke` exit 0 (Windows).\n"))
edit("FILE_STRUCTURE.md", append("\n- src/engstudio/plotting/export.py\n"
                                 "- src/engstudio/app/figure_export.py\n"
                                 "- tests/plotting/test_plotting_export.py\n"
                                 "- tests/app/test_figure_export_app.py\n"
                                 "- tests/gui/test_gui_figure_export.py\n"))
edit("DEPENDENCIES.md", lambda t: t if "matplotlib" in t.lower() else
     t.rstrip("\n") + f"\n- matplotlib {mplv}: figure export (plotting.export, Agg backend)\n")
edit("API_REFERENCE.md", append(
    "\n## Figure export (G5.3)\n"
    "- `engstudio.plotting.export.export_figure(spec, path, *, dpi=150, size_in=(7.2, 4.8))` "
    "-> Path; format from suffix (.png/.svg/.pdf); `ValidationError` for other suffixes or "
    "bad arguments, `EngStudioError` if the file cannot be written; atomic.\n"
    "- `build_figure(spec, size_in)` -> Matplotlib Figure (no pyplot).\n"
    "- GUI path: `engstudio.app.figure_export.save_figure`; `FigureWindow.save_as()` / "
    "`save_to(path)`.\n"
    "- Unlabelled series without a colour use Matplotlib's colour cycle in exports.\n"))
print(f"docs updated ({n} tests)")
