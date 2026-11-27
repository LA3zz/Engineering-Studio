"""Docs update for E12 (idempotent). Run: python patches\\apply_docs_e12.py

ruff, full pytest, the E12 test file and the GUI smoke must pass first, else nothing is edited.
Backs up the 6 docs it touches, appends entries (marker-guarded) and applies exact-match
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
MARKER = "<!-- docs E12 -->"

CHANGELOG = """
## 2026-11-21 - E12
- `engine.uncertainty`: `propagate(f, x, ux, ...)` for a scalar model y = f(x) and
  `UncertaintyResult`. Methods: GUM first-order law (central-difference sensitivities scaled to
  the input magnitude, optional correlation matrix, coverage factor) and Monte Carlo (normal
  inputs incl. correlation, seeded, optional vectorised model, symmetric coverage interval).
  Diagnostics: UNC_NONLINEAR, UNC_CHECK_SKIPPED, UNC_CORRELATED, UNC_FEW_SAMPLES, UNC_UNSEEDED.
"""

API = """
## engstudio.engine.uncertainty (E12)
```python
UncertaintyResult(value, standard_uncertainty, expanded_uncertainty, interval, coverage,
                  sensitivities, contributions, method, k=None, n_samples=0, diagnostics=())
propagate(f, x, ux, *, method="linear", corr=None, coverage=0.95, k=None, n=100_000,
          seed=0, vectorized=False) -> UncertaintyResult
```
- `f(x)` takes a 1-D array of input estimates and returns one real number; `ux` are standard
  uncertainties (>= 0, same length as `x`); `corr` an optional symmetric positive semidefinite
  correlation matrix with unit diagonal. `value` is f at the estimates.
- `"linear"`: u_c^2 = g^T U g; interval = value -+ k u_c, k from `coverage` (normal quantile) or
  the explicit `k`. `contributions[i] = |g_i| ux[i]` (not additive when inputs are correlated).
- `"montecarlo"`: `n` samples (100..5,000,000) of normal inputs, `seed` (default 0, `None` =
  fresh entropy); `standard_uncertainty` is the sample std, `interval` the symmetric `coverage`
  interval; `vectorized=True` calls `f` once with an (n, n_inputs) array returning n values.
- Errors: `ValidationError` (bad options, correlation matrix, non-finite or non-scalar model
  output, model undefined in the input distribution), `DimensionError` (size mismatches).
"""

FILES = """
## Added in E12 (2026-11-21)
- src/engstudio/engine/uncertainty.py
- tests/engine/test_uncertainty.py
"""

TESTS = """
## 2026-11-21 - E12
- tests/engine/test_uncertainty.py: {n_new} tests (GUM closed forms for sum, product, power,
  parallel resistors and correlated difference; coverage factors; Monte Carlo against exact
  normal and chi-square statistics; reproducibility; validation and warnings).
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
    ode = _run([sys.executable, "-m", "pytest", "tests/engine/test_uncertainty.py", "-q"])
    n_new = _passed(ode, "test_uncertainty")
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
    """Replace the whole line starting with ``prefix`` (first match). Keeps line ending."""
    m = re.search(r"^" + re.escape(prefix) + r"[^\r\n]*", text, flags=re.M)
    if not m:
        return text, False
    return text[:m.start()] + new + text[m.end():], True


def _edit_handoff(count: int) -> None:
    p = DOCS / "HANDOFF.md"
    text = _read(p)
    done = []
    text, ok = _edit_line(text, "Last updated: 2026-11-20, after E11",
                          "Last updated: 2026-11-20, after E12 (docs synced).")
    done.append(("last updated", ok))
    old = "raise NotSupportedError) done. Next: E12."
    new = ("raise NotSupportedError) done; `engine.uncertainty` (E12: propagate, "
           "UncertaintyResult; linear GUM and Monte Carlo) done. Next: E12b (docs page).")
    ok = old in text
    text = text.replace(old, new, 1) if ok else text
    done.append(("engine state", ok))
    text, ok = _edit_line(text, "**E12** Uncertainty propagation",
                          "**E12b** Engine API docs page for the Documentation panel: one new "
                          "Markdown page in `app/docs_pages` listing the E1-E12 engine modules "
                          "(functions, result types, conventions, error behaviour), registered "
                          "the way the existing pages are. BEFORE building, ask the user for "
                          "`src\\engstudio\\app\\docs.py`, `tests\\app\\test_docs.py` and "
                          "`dir src\\engstudio\\app\\docs_pages` (page registration and the "
                          "page-count assertions are unknown).")
    done.append(("next task", ok))
    text, n = re.subn(r"(`python -m pytest -q` )\d+( passed, ruff clean, GUI smoke ok \()E1-E11\)",
                      rf"\g<1>{count}\g<2>E1-E12)", text)
    done.append(("verified line", n > 0))
    _write(p, text)
    for name, ok in done:
        print(f"HANDOFF.md {name}: {'edited' if ok else 'not found, skipped'}")


def _edit_tasks(count: int) -> None:
    p = DOCS / "TASKS.md"
    text = _read(p)
    old = "- [ ] E12 uncertainty propagation (GUM linear + Monte Carlo) and engine API docs"
    if old not in text:
        print("TASKS.md: E12 line not found, skipped")
        return
    nl = "\r\n" if "\r\n" in text else "\n"
    new = (f"- [x] E12 (verified 2026-11-21, {count} tests) uncertainty propagation (GUM linear "
           f"+ Monte Carlo){nl}- [ ] E12b engine API docs page in the Documentation panel "
           "(needs app/docs.py, tests/app/test_docs.py, docs_pages listing)")
    _write(p, text.replace(old, new, 1))
    print("TASKS.md: E12 ticked, E12b added")


def main() -> int:
    names = ["CHANGELOG.md", "TEST_STATUS.md", "API_REFERENCE.md", "FILE_STRUCTURE.md",
             "HANDOFF.md", "TASKS.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if missing:
        sys.exit(f"missing in {DOCS}: {missing}. Nothing changed.")
    count, n_new = run_checks()
    backup = ROOT / "patches" / f"backup_docs_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    print(f"backup: {backup}")
    plan = [("CHANGELOG.md", CHANGELOG), ("API_REFERENCE.md", API), ("FILE_STRUCTURE.md", FILES),
            ("TEST_STATUS.md", TESTS.format(count=count, n_new=n_new))]
    for n, block in plan:
        print(f"{n}: {_append(DOCS / n, block)}")
    _edit_handoff(count)
    _edit_tasks(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
