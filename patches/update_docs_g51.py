"""Run ONLY after G5.1 works. Checks ruff + pytest + app smoke first; updates docs\\project."""

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
    return re.sub(
        r"- \[ \] G5 .*",
        f"- [x] G5.1 Figure data model + FigureUpdate event ({n} tests, verified {today})\n"
        "- [ ] G5.2 Figure window (gui.plots PyQtGraph renderer + stub demo_plot)",
        t, count=1)


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G5.1.", t, count=1)
    t = t.replace("No Figure window yet.",
                  "G5.1 done: `plotting.model` (FigureSpec/AxesSpec/SeriesSpec, validated, "
                  "immutable) and the `FigureUpdate` event; no Figure window yet.")
    nxt = ("## Next task\n**G5.2** Figure window: `gui.plots` renders a `FigureSpec` with "
           "PyQtGraph (line, scatter, bar; titles, labels, limits, log axes, grid, legend; "
           "subplot grid) inside a `FigureWindow`; `MainWindow` opens or updates one window "
           "per `FigureSpec.number` on `FigureUpdate`; the stub kernel gets a `demo_plot` "
           "command that emits a small labelled sample figure. First check that `pyqtgraph` "
           "is installed in the venv and listed in `requirements.lock.txt` / DEPENDENCIES.md "
           "(report if missing, do not install silently). The GUI imports `plotting.model` "
           "only, never `lang`/`engine`.\n")
    t = re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)
    return re.sub(r"\nLater:.*",
                  "\nLater: G5.3 figure export (plotting.export, Matplotlib/Agg), G6 "
                  "Documentation + Diagnostics panels, real kernel process, GUI in the "
                  "PyInstaller spec, Save/Load Workspace.", t, count=1)


edit("TASKS.md", tasks)
edit("HANDOFF.md", handoff)
edit("CHANGELOG.md", append(f"\n## {today} - G5.1\n- Added `plotting.model` (validated immutable "
                            "figure description) and the `FigureUpdate` kernel event.\n"))
edit("TEST_STATUS.md", append(f"\n- {today} G5.1: pytest {n} passed, ruff clean, "
                              "`engstudio.gui --smoke` exit 0 (Windows).\n"))
edit("FILE_STRUCTURE.md", append("\n- src/engstudio/plotting/model.py\n"
                                 "- tests/plotting/test_plotting_model.py\n"
                                 "- tests/app/test_kernel_figure.py\n"))
edit("API_REFERENCE.md", append(
    "\n## Figure model (G5.1)\n"
    "- `engstudio.plotting.model`: `SeriesSpec(kind, x, y, label, color, line_style, "
    "line_width, marker, marker_size)`, `AxesSpec(series, title, xlabel, ylabel, xlim, ylim, "
    "xscale, yscale, grid, legend)`, `FigureSpec(number, title, axes, rows, cols)`.\n"
    "- Data are copied to read-only 1-D float64; 1xN/Nx1 flattened; matrices -> "
    "`DimensionError`; complex -> `ValidationError`; NaN allowed.\n"
    "- `FigureUpdate(request_id, figure)` event in `app.kernel.protocol`.\n"))
print(f"docs updated ({n} tests)")
