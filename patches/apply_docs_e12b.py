"""Docs update for E12b (idempotent). Run: python patches\\apply_docs_e12b.py

ruff, the E12b test file, full pytest and the GUI smoke must pass first, else nothing is
edited. Backs up the docs it touches, appends marker-guarded entries and applies exact-match
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
MARKER = "<!-- docs E12b -->"
TEST_FILE = "tests/app/test_engine_api_page.py"

CHANGELOG = """
## {date} - E12b
- Documentation panel: new page `engine-api` (Math engine API, E1-E12) listing modules,
  functions, result types, conventions and error behaviour; linked from the index page.
"""

FILES = """
## Added in E12b ({date})
- src/engstudio/app/docs_pages/engine-api.md
- tests/app/test_engine_api_page.py
- src/engstudio/app/docs_pages/index.md (link added)
"""

TESTS = """
## {date} - E12b
- {test_file}: {n_new} tests (page registered and linked; one section per engine module;
  every documented function exists in the module and is mentioned on the page).
- Full suite: {count} passed, ruff clean, GUI smoke ok.
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
    n_new = _passed(_run([sys.executable, "-m", "pytest", TEST_FILE, "-q"]), "page tests")
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


def _edit_handoff(count: int) -> None:
    p = DOCS / "HANDOFF.md"
    text = _read(p)
    done = []
    text, ok = _edit_line(text, "Last updated: 2026-11-20, after E12 (docs synced)",
                          "Last updated: 2026-11-21, after E12b (docs synced).")
    done.append(("last updated", ok))
    old = "Next: E12b (docs page)."
    new = ("Docs page `engine-api` (E12b: Math engine API, E1-E12) done in "
           "`app/docs_pages`. Next: G7 (theme editor).")
    ok = old in text
    text = text.replace(old, new, 1) if ok else text
    done.append(("engine state", ok))
    text, ok = _edit_line(text, "**E12b** Engine API docs page",
                          "**G7** custom theme editor (details below).")
    done.append(("next task", ok))
    old = "**Then G7** custom theme editor:"
    ok = old in text
    text = text.replace(old, "**G7 details:**", 1) if ok else text
    done.append(("g7 heading", ok))
    text, n = re.subn(r"(`python -m pytest -q` )\d+( passed, ruff clean, GUI smoke ok \()"
                      r"E1-E12\)", rf"\g<1>{count}\g<2>E1-E12b)", text)
    done.append(("verified line", n > 0))
    _write(p, text)
    for name, ok in done:
        print(f"HANDOFF.md {name}: {'edited' if ok else 'not found, skipped'}")


def _edit_tasks(count: int, date: str) -> None:
    p = DOCS / "TASKS.md"
    text = _read(p)
    old = ("- [ ] E12b engine API docs page in the Documentation panel "
           "(needs app/docs.py, tests/app/test_docs.py, docs_pages listing)")
    if old not in text:
        print("TASKS.md: E12b line not found, skipped")
        return
    new = (f"- [x] E12b (verified {date}, {count} tests) engine API docs page "
           "(app/docs_pages/engine-api.md)")
    _write(p, text.replace(old, new, 1))
    print("TASKS.md: E12b ticked")


def main() -> int:
    names = ["CHANGELOG.md", "TEST_STATUS.md", "FILE_STRUCTURE.md", "HANDOFF.md", "TASKS.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if missing:
        sys.exit(f"missing in {DOCS}: {missing}. Nothing changed.")
    count, n_new = run_checks()
    date = time.strftime("%Y-%m-%d")
    backup = ROOT / "patches" / f"backup_docs_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    print(f"backup: {backup}")
    plan = [("CHANGELOG.md", CHANGELOG.format(date=date)),
            ("FILE_STRUCTURE.md", FILES.format(date=date)),
            ("TEST_STATUS.md", TESTS.format(date=date, count=count, n_new=n_new,
                                            test_file=TEST_FILE))]
    for n, block in plan:
        print(f"{n}: {_append(DOCS / n, block)}")
    _edit_handoff(count)
    _edit_tasks(count, date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
