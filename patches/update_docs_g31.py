"""Run ONLY after G3.1 works. Checks ruff + pytest first; updates docs\\project on success."""

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
    with open(p, encoding="utf-8-sig", newline="") as f:
        t = f.read()
    nl = "\r\n" if "\r\n" in t else "\n"
    t = fn(t.replace("\r\n", "\n")).replace("\n", nl)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)


def append(name: str, text: str):
    return lambda t: t.rstrip("\n") + "\n" + text


def tasks(t: str) -> str:
    return t.replace(
        "- [ ] G3 Current Folder + Toolbox browsers",
        f"- [x] G3.1 Current Folder browser ({n} tests, verified {today})\n"
        "- [ ] G3.2 Toolbox browser (needs ListToolboxes in kernel protocol)")


def handoff(t: str) -> str:
    t = re.sub(r"Last updated: .*", f"Last updated: {today}, after G3.1.", t, count=1)
    t = re.sub(r"Placeholders remain: Current Folder, ", "Placeholders remain: ", t)
    t = t.replace("Workspace browser (live table",
                  "G3.1 Current Folder (tree, up/browse/path box, double-click opens .m, "
                  "folder persisted as `current_folder`), Workspace browser (live table")
    nxt = ("## Next task\n**G3.2** Toolbox browser (`gui.toolbox_panel`): add `ListToolboxes` "
           "request and `ToolboxList` event (plain data: toolbox name, display name, functions "
           "with one-line summary) to `app.kernel.protocol`, `KernelClient` and the stub; "
           "tree in the GUI, double-click inserts the function name into the Command Window "
           "input. GUI must not import toolboxes.\n")
    return re.sub(r"## Next task\n.*?(?=\nLater:)", nxt, t, count=1, flags=re.S)


edit("TASKS.md", tasks)


def known(t: str) -> str:
    return t.replace("## Known problems\n", "## Known problems\n"
                     "- GUI test process intermittently aborts at Qt teardown (0xC0000409); "
                     "see TEST_STATUS.md. Workaround in tests/gui/conftest.py; "
                     "root cause open.\n", 1)


edit("HANDOFF.md", handoff)
edit("HANDOFF.md", known)
edit("CHANGELOG.md", append("CHANGELOG.md", f"\n## {today} - G3.1\n- Added Current Folder "
                            "browser (`gui.folder_panel`), wired into panels/main window.\n"))
edit("TEST_STATUS.md", append(
    "TEST_STATUS.md",
    f"\n- {today} G3.1: pytest {n} passed, ruff clean, "
    "`engstudio.gui --smoke` exit 0 (Windows).\n"
    "- KNOWN ISSUE: the GUI test process intermittently aborts at Qt teardown (exit "
    "0xC0000409, about 50% of full runs) although all tests pass; the real app exits cleanly "
    "(0 of 6 smoke runs failed). Workaround: tests/gui/conftest.py exits with pytest's own "
    "status via os._exit (disable: ENGSTUDIO_NO_FAST_EXIT=1). Root cause not found.\n"))
edit("FILE_STRUCTURE.md", append("FILE_STRUCTURE.md", "\n- src/engstudio/gui/folder_panel.py\n"
                                 "- tests/gui/test_folder_panel.py\n"))
print(f"docs updated ({n} tests)")
