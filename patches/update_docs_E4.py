"""Sync docs for E4 (verified 548 tests). Runs ruff, pytest and the GUI smoke first.

Run from the project root with the venv active: python patches\\update_docs_E4.py
Exact-match and idempotent. Edits docs\\project\\HANDOFF.md and TASKS.md only.
"""
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


ruff = shutil.which("ruff")
ruff_cmd = [ruff] if ruff else [sys.executable, "-m", "ruff"]
run("ruff", ruff_cmd + ["check", "src", "tests"])
run("pytest", [sys.executable, "-m", "pytest", "-q"])
run("gui smoke", [sys.executable, "-m", "engstudio.gui", "--smoke"])

EDITS = {
    "HANDOFF.md": [
        ("Last updated: 2026-11-20, after E3 (docs synced).",
         "Last updated: 2026-11-20, after E4 (docs synced)."),
        ("`engine.decomp` (E2) and `engine.calculus` (E3) done. Next: E4.",
         "`engine.decomp` (E2), `engine.calculus` (E3) and `engine.roots` (E4: bisect, brentq, "
         "newton, secant, polyroots, fsolve; RootResult) done. Next: E5."),
        ("**E4** root finding and equation solving in `engine.roots`: scalar (bracketing, "
         "Newton/secant), polynomial roots, nonlinear systems; `RootResult` per ARCHITECTURE "
         "section 6, `ConvergenceError` on failure, explicit rtol/atol, results checked against "
         "analytic roots. BEFORE building, list `src\\engstudio\\engine` to see what exists.",
         "**E5** interpolation in `engine.interp`: `interp1` (linear, nearest, previous, next, "
         "pchip, spline, natural) and `interp2` (linear, nearest, cubic); default "
         "`extrap=\"error\"`, explicit nan/clamp/extrapolate; tested against exact polynomials. "
         "BEFORE building, list `src\\engstudio\\engine` to see what exists."),
        ("Then E5-E12 per", "Then E6-E12 per"),
    ],
    "TASKS.md": [
        ("- [ ] E4 root finding and equation solving (scalar, systems, polynomials)",
         "- [x] E4 (verified 2026-11-20, 548 tests) root finding and equation solving "
         "(scalar, systems, polynomials)"),
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
print("Docs synced for E4.")
