"""Run ONLY after G3.2 works. Checks ruff + pytest + app smoke first; updates docs\\project."""

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
    t = re.sub(r"- \[ \] G3\.2 .*",
               f"- [x] G3.2 Toolbox browser (stub catalogue; {n} tests, verified {today})", t,
               count=1)
    backlog = ("- [ ] Restore open script tabs on startup (unscheduled)\n"
               "- [ ] Find the root cause of the intermittent Qt teardown crash in the GUI test "
               "process (workaround in tests/gui/conftest.py) (unscheduled)\n")
    if "Restore open script tabs" not in t:
        t = t.replace("## Backlog (not scheduled)\n", "## Backlog (not scheduled)\n" + backlog, 1)
    return t


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G3.2.", t, count=1)
    t = t.replace("Placeholders remain: Toolboxes, ", "Placeholders remain: ")
    t = t.replace("G3.1 Current Folder (",
                  "G3.2 Toolbox browser (ListToolboxes/ToolboxList via the stub catalogue, filter "
                  "box, double-click inserts the name in the Command Window), G3.1 Current "
                  "Folder (", 1)
    nxt = ("## Next task\n**G4** Script editor syntax highlighting (`gui.highlighter`, a "
           "QSyntaxHighlighter on `ScriptEditor`): keywords, comments (`%`), strings, numbers; "
           "colours from the theme palette so light/dark both work. The GUI must not import "
           "`lang`, so the keyword list must reach it through `app` (for example a small "
           "`app` module re-exporting `lang.lexer.KEYWORDS`); decide and state that in the "
           "plan before coding.\n")
    t = re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)
    return re.sub(r"\nLater:.*",
                  "\nLater: G5 Figure window, G6 Documentation + Diagnostics panels, real "
                  "kernel process, GUI in the PyInstaller spec.", t, count=1)


edit("TASKS.md", tasks)
edit("HANDOFF.md", handoff)
edit("CHANGELOG.md", append(f"\n## {today} - G3.2\n- Added Toolbox browser "
                            "(`gui.toolbox_panel`), `ListToolboxes`/`ToolboxList` protocol "
                            "messages, `KernelClient.list_toolboxes` (default: not supported), "
                            "stub sample catalogue, `MainWindow.insert_in_command`.\n"))
edit("TEST_STATUS.md", append(f"\n- {today} G3.2: pytest {n} passed, ruff clean, "
                              "`engstudio.gui --smoke` exit 0 (Windows).\n"))
edit("FILE_STRUCTURE.md", append("\n- src/engstudio/gui/toolbox_panel.py\n"
                                 "- tests/gui/test_gui_toolbox_panel.py\n"
                                 "- tests/app/test_kernel_toolboxes.py\n"))
edit("API_REFERENCE.md", append(
    "\n## Kernel protocol additions (G3.2)\n"
    "- `ListToolboxes(request_id)` request; `KernelClient.list_toolboxes() -> int`\n"
    "- `ToolboxList(request_id, toolboxes)` event; `ToolboxInfo(name, display_name, functions)`;\n"
    "  `ToolboxFunction(name, summary, signature)`. Protocol version unchanged (additive).\n"))
print(f"docs updated ({n} tests)")
