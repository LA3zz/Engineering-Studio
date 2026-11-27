"""Sync docs for E7 (optimize) and E8 (stats) after the real tests pass.

Run from the project root with the venv active: python patches\\update_docs_E7_E8.py
Runs ruff, pytest and the GUI smoke first; edits docs\\project\\HANDOFF.md and TASKS.md only.
Exact-match and idempotent. Requires update_docs_E5_E6.py to have been applied.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "project"


def run(label, cmd):
    print(f"[check] {label} ...", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit(f"ABORT: {label} failed; docs not changed")
    return r.stdout


ruff = shutil.which("ruff")
ruff_cmd = [ruff] if ruff else [sys.executable, "-m", "ruff"]
run("ruff", ruff_cmd + ["check", "src", "tests"])
out = run("pytest", [sys.executable, "-m", "pytest", "-q"])
m = re.search(r"(\d+) passed", out)
if not m:
    sys.exit("ABORT: could not read the pytest pass count")
count = m.group(1)
run("gui smoke", [sys.executable, "-m", "engstudio.gui", "--smoke"])

E7_PARA = (
    "**E7** numerical optimization in `engine.optimize`: scalar minimization (bounded Brent), "
    "unconstrained minimization (BFGS, Nelder-Mead), bounds and constraints, linear "
    "programming; result dataclass with converged/iterations/nfev, `ConvergenceError` on "
    "failure, explicit tolerances, results checked against analytic minima. "
    "BEFORE building, list `src\\engstudio\\engine` to see what exists.")
E9_PARA = (
    "**E9** ODE solvers in `engine.ode`: `solve_ode` over SciPy `solve_ivp` (RK45, RK23, "
    "DOP853, Radau, BDF, LSODA) with explicit rtol/atol, `OdeResult(t, y, status, nfev, "
    "diagnostics)` per ARCHITECTURE section 6, `ConvergenceError` on failure, events "
    "optional, tested against analytic solutions (exponential decay, harmonic oscillator, "
    "logistic). BEFORE building, list `src\\engstudio\\engine` to see what exists.")

EDITS = {
    "HANDOFF.md": [
        ("Last updated: 2026-11-20, after E6 (docs synced).",
         "Last updated: 2026-11-20, after E8 (docs synced)."),
        ("FitResult) done. Next: E7.",
         "FitResult) done; `engine.optimize` (E7: minimize_scalar, minimize, linprog; "
         "MinimizeResult) and `engine.stats` (E8: descriptive stats, quantile, pearsonr, "
         "confidence_interval_mean, ttest_1samp/ind/paired, histogram) done. Next: E9."),
        (E7_PARA, E9_PARA),
        ("Then E8-E12 per", "Then E10-E12 per"),
    ],
    "TASKS.md": [
        ("- [ ] E7 numerical optimization",
         "- [x] E7 (verified 2026-11-20) numerical optimization"),
        ("- [ ] E8 statistics",
         f"- [x] E8 (verified 2026-11-20, {count} tests) statistics"),
    ],
}

for name, pairs in EDITS.items():
    path = DOCS / name
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    for old, new in pairs:
        if new in text:
            print(f"[skip] {name}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"[ok]   {name}: edited")
        else:
            sys.exit(f"ABORT: {name}: expected text not found: {old[:60]!r}")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
print(f"Docs synced for E7 and E8 ({count} tests).")
