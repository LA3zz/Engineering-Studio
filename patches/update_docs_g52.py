"""Run ONLY after G5.2 works. Checks ruff + pytest + app smoke first; updates docs\\project."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from importlib.metadata import PackageNotFoundError, version
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
try:
    pgv = version("pyqtgraph")
except PackageNotFoundError:
    pgv = "unknown"


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
    return re.sub(r"- \[ \] G5\.2 .*",
                  f"- [x] G5.2 Figure window ({n} tests, verified {today})\n"
                  "- [ ] G5.3 Figure export (plotting.export, Matplotlib/Agg: PNG/SVG/PDF) "
                  "+ save button in the Figure window", t, count=1)


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G5.2.", t, count=1)
    t = t.replace("; no Figure window yet.",
                  "; G5.2 done: `gui.plots` (PyQtGraph renderer), `gui.figure_window`, "
                  "`MainWindow.show_figure` (one window per figure number, updated in place), "
                  "stub `demo_plot [N]`.")
    nxt = ("## Next task\n**G5.3** Figure export: `plotting.export` (L1, Matplotlib with the "
           "Agg backend, no Qt) renders a `FigureSpec` to PNG/SVG/PDF; a Save As action in "
           "`FigureWindow` asks for the path (GUI) and calls it through `app` (the GUI does "
           "not import Matplotlib). Check `matplotlib` is in the venv and lock file first. "
           "Bars on log axes are currently skipped by the PyQtGraph renderer (reported in the "
           "window status line); decide whether export should draw them.\n")
    t = re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)
    return re.sub(r"\nLater:.*",
                  "\nLater: G6 Documentation + Diagnostics panels, real kernel process, GUI in "
                  "the PyInstaller spec, Save/Load Workspace.", t, count=1)


edit("TASKS.md", tasks)
edit("HANDOFF.md", handoff)
edit("CHANGELOG.md", append(f"\n## {today} - G5.2\n- Figure window: `gui.plot_params`, "
                            "`gui.plots` (PyQtGraph), `gui.figure_window`; MainWindow opens "
                            "and updates figure windows on `FigureUpdate`; stub `demo_plot`. "
                            "Known limits: bar series are not in the legend and are skipped on "
                            "log axes.\n"))
edit("TEST_STATUS.md", append(f"\n- {today} G5.2: pytest {n} passed, ruff clean, "
                              "`engstudio.gui --smoke` exit 0 (Windows).\n"))
edit("FILE_STRUCTURE.md", append("\n- src/engstudio/gui/plot_params.py\n"
                                 "- src/engstudio/gui/plots.py\n"
                                 "- src/engstudio/gui/figure_window.py\n"
                                 "- tests/gui/test_plot_params.py\n"
                                 "- tests/gui/test_gui_figures.py\n"
                                 "- tests/app/test_kernel_demo_plot.py\n"))
edit("DEPENDENCIES.md", lambda t: t if "pyqtgraph" in t.lower() else
     t.rstrip("\n") + f"\n- pyqtgraph {pgv}: interactive figure rendering (gui.plots)\n")
edit("API_REFERENCE.md", append(
    "\n## Figure window (G5.2)\n"
    "- `engstudio.gui.plots.FigureView(theme).set_figure(FigureSpec)`; `.plot_items()`, "
    "`.warnings`, `.set_theme(name)`\n"
    "- `engstudio.gui.figure_window.FigureWindow(number, theme, parent)` (`closed(int)` signal)\n"
    "- `MainWindow.show_figure(spec)`; stub command `demo_plot [N]`.\n"))
print(f"docs updated ({n} tests)")
