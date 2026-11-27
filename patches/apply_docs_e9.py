"""Docs update for E9 (idempotent). Run: python patches\\apply_docs_e9.py

ruff, full pytest, the E9 test file and the GUI smoke must pass first, else nothing is edited.
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
MARKER = "<!-- docs E9 -->"

CHANGELOG = """
## 2026-11-20 - E9
- `engine.ode`: `solve_ode` over SciPy `solve_ivp` (RK45, RK23, DOP853, Radau, BDF, LSODA),
  `OdeResult`, `METHODS`. Explicit rtol/atol, optional t_eval, events, user Jacobian, max_step,
  first_step and an evaluation budget `max_nfev`. Non-finite right-hand side (blow-up), budget
  exhaustion and solver failure raise `ConvergenceError`; diagnostics: ODE_WARNING,
  ODE_EVENT (info), ODE_STIFF_SUSPECTED (explicit method with many evaluations).
- Note: `OdeResult.y` has shape `(len(t), n_states)` (SciPy's is the transpose).
"""

API = """
## engstudio.engine.ode (E9)
```python
OdeResult(t, y, status, nfev, diagnostics, method, message, t_events, y_events)
solve_ode(f, t_span, y0, *, method="RK45", rtol=1e-6, atol=1e-9, t_eval=None, events=None,
          jac=None, max_step=inf, first_step=None, max_nfev=200_000) -> OdeResult
METHODS = ("RK45", "RK23", "DOP853", "Radau", "BDF", "LSODA")
```
- `f(t, y)` returns dy/dt (real vector; scalar allowed for one state). `y` shape is
  `(len(t), n_states)`. `status` 0 = reached t1, 1 = stopped by a terminal event.
- Events: SciPy convention (`event(t, y)`, optional `.terminal`, `.direction`); `t_events` /
  `y_events` are tuples with one array per event function.
- `rtol >= 100*eps`; `atol` scalar or per-state vector; `jac` (callable or n x n matrix) only
  for Radau/BDF/LSODA; `t_span` may run backwards.
- Errors: `ValidationError`/`DimensionError` (inputs, wrong f output), `ConvergenceError`
  (step-size failure, non-finite derivative, `max_nfev` exceeded; has `.last_estimate`).
  Exceptions raised inside `f` propagate unchanged.
"""

FILES = """
## Added in E9 (2026-11-20)
- src/engstudio/engine/ode.py
- tests/engine/test_ode.py
"""

TESTS = """
## 2026-11-20 - E9
- tests/engine/test_ode.py: {n_ode} tests (analytic: exponential decay, logistic, harmonic
  oscillator with energy conservation, stiff y' = -1000 (y - cos t) - sin t with exact solution
  cos t, free-fall event time sqrt(2h/g), blow-up y' = y^2, budget, validation).
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
    n_ode = _passed(_run([sys.executable, "-m", "pytest", "tests/engine/test_ode.py", "-q"]),
                    "test_ode")
    count = _passed(_run([sys.executable, "-m", "pytest", "-q"]), "pytest")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = _run([sys.executable, "-m", "engstudio.gui", "--smoke"], env=env, timeout=180)
    print(f"gui smoke: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"GUI smoke failed, no docs edited:\n{r.stdout}{r.stderr}")
    return count, n_ode


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
    text, ok = _edit_line(text, "Last updated: 2026-11-20, after E8",
                          "Last updated: 2026-11-20, after E9 (docs synced).")
    done.append(("last updated", ok))
    old = "histogram) done. Next: E9."
    new = ("histogram) done; `engine.ode` (E9: solve_ode, OdeResult with y shaped "
           "(len(t), n_states), t_eval, events, jac, max_nfev) done. Next: E10.")
    ok = old in text
    text = text.replace(old, new, 1) if ok else text
    done.append(("engine state", ok))
    text, ok = _edit_line(text, "**E9** ODE solvers in `engine.ode`:",
                          "**E10** Fourier transforms and spectral tools in `engine.transforms` "
                          "(fft/ifft, rfft, power spectrum, windows, convolution, filtering "
                          "helpers) over `numpy.fft`/`scipy.signal`, validated inputs, typed "
                          "errors, tested against analytic transforms (single tone peak, "
                          "Parseval, delta/boxcar pairs). BEFORE building, list "
                          "`src\\engstudio\\engine` to see what exists.")
    done.append(("next task", ok))
    old = "Then E10-E12 per"
    ok = old in text
    text = text.replace(old, "Then E11-E12 per", 1) if ok else text
    done.append(("then line", ok))
    text, n = re.subn(r"(`python -m pytest -q` )\d+( passed, ruff clean, GUI smoke ok \()E1-E8\)",
                      rf"\g<1>{count}\g<2>E1-E9)", text)
    done.append(("verified line", n > 0))
    _write(p, text)
    for name, ok in done:
        print(f"HANDOFF.md {name}: {'edited' if ok else 'not found, skipped'}")


def _edit_tasks(count: int) -> None:
    p = DOCS / "TASKS.md"
    text = _read(p)
    old = "- [ ] E9 ODE solvers"
    if old in text:
        text = text.replace(old, f"- [x] E9 (verified 2026-11-20, {count} tests) ODE solvers", 1)
        _write(p, text)
        print("TASKS.md: E9 ticked")
    else:
        print("TASKS.md: E9 line not found, skipped")


def main() -> int:
    names = ["CHANGELOG.md", "TEST_STATUS.md", "API_REFERENCE.md", "FILE_STRUCTURE.md",
             "HANDOFF.md", "TASKS.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if missing:
        sys.exit(f"missing in {DOCS}: {missing}. Nothing changed.")
    count, n_ode = run_checks()
    backup = ROOT / "patches" / f"backup_docs_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    print(f"backup: {backup}")
    plan = [("CHANGELOG.md", CHANGELOG), ("API_REFERENCE.md", API), ("FILE_STRUCTURE.md", FILES),
            ("TEST_STATUS.md", TESTS.format(count=count, n_ode=n_ode))]
    for n, block in plan:
        print(f"{n}: {_append(DOCS / n, block)}")
    _edit_handoff(count)
    _edit_tasks(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
