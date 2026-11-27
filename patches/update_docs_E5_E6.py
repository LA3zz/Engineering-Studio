"""Sync docs for E5 (interp) and E6 (regression) after the real tests pass.

Run from the project root with the venv active: python patches\\update_docs_E5_E6.py
Runs ruff, pytest and the GUI smoke first; edits docs\\project\\HANDOFF.md and TASKS.md only.
Exact-match and idempotent. Requires update_docs_E4.py to have been applied.
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

E5_PARA = (
    "**E5** interpolation in `engine.interp`: `interp1` (linear, nearest, previous, next, "
    "pchip, spline, natural) and `interp2` (linear, nearest, cubic); default "
    "`extrap=\"error\"`, explicit nan/clamp/extrapolate; tested against exact polynomials. "
    "BEFORE building, list `src\\engstudio\\engine` to see what exists.")
E7_PARA = (
    "**E7** numerical optimization in `engine.optimize`: scalar minimization (bounded Brent), "
    "unconstrained minimization (BFGS, Nelder-Mead), bounds and constraints, linear "
    "programming; result dataclass with converged/iterations/nfev, `ConvergenceError` on "
    "failure, explicit tolerances, results checked against analytic minima. "
    "BEFORE building, list `src\\engstudio\\engine` to see what exists.")

EDITS = {
    "HANDOFF.md": [
        ("Last updated: 2026-11-20, after E4 (docs synced).",
         "Last updated: 2026-11-20, after E6 (docs synced)."),
        ("RootResult) done. Next: E5.",
         "RootResult) done; `engine.interp` (E5: interp1, interp2) and `engine.regression` "
         "(E6: linfit, polyfit, polyval, fit_curve, confidence_intervals; FitResult) done. "
         "Next: E7."),
        (E5_PARA, E7_PARA),
        ("Then E6-E12 per", "Then E8-E12 per"),
    ],
    "TASKS.md": [
        ("- [ ] E5 interpolation",
         "- [x] E5 (verified 2026-11-20, 575 tests) interpolation"),
        ("- [ ] E6 regression and curve fitting",
         f"- [x] E6 (verified 2026-11-20, {count} tests) regression and curve fitting"),
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
print(f"Docs synced for E5 and E6 ({count} tests).")
