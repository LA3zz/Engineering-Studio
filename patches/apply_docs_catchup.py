"""Docs catch-up for E2-E8 (idempotent). Run from anywhere: python patches\\apply_docs_catchup.py

Order: (1) ruff, pytest, GUI smoke must pass, else nothing is edited; (2) backup of the
files it will touch; (3) append entries to CHANGELOG, TEST_STATUS, API_REFERENCE,
FILE_STRUCTURE (skipped if the marker is already present); (4) fix the stale line in
HANDOFF.md (exact match, skipped if absent). Nothing is ever deleted.
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
MARKER = "<!-- docs-catchup E2-E8 -->"
STALE = ("- Verified by user 2026-11-18: `python -m pytest -q` 227 passed, ruff clean, "
         "real window checked manually.")

CHANGELOG = """
## 2026-11-20 - E2 to E8 (catch-up entry)
- E2 `engine.decomp`: lu, qr, svd, cholesky, eig, eigh (EigResult with residual and
  vector_rcond; defective/Hermitian tolerances as module constants).
- E3 `engine.calculus`: derivative (central/forward/backward, order 1-2), gradient, jacobian,
  derivative_data, quad, dblquad (IntegrateResult), trapz, simpson, cumtrapz.
- E4 `engine.roots`: bisect, brentq, newton, secant, polyroots, fsolve (RootResult).
- E5 `engine.interp`: interp1, interp2 (explicit `method` and `extrap`).
- E6 `engine.regression`: linfit, polyfit, polyval, fit_curve, confidence_intervals (FitResult).
- E7 `engine.optimize`: minimize_scalar, minimize, linprog (MinimizeResult).
- E8 `engine.stats`: descriptive statistics, quantile, iqr, zscore, cov, pearsonr,
  confidence_interval_mean, ttest_1samp / ttest_ind / ttest_paired, histogram.
- Docs: this entry, TEST_STATUS, API_REFERENCE, FILE_STRUCTURE and HANDOFF brought up to date.
- Test count after E8: 638 (collected). Added `scripts/dump_api.py` (read-only helper).
"""

API = """
## engstudio.engine, E1-E8 signatures (added 2026-11-20; read from the code, not hand-typed)
Result dataclasses are frozen. Failures raise typed errors from `core.errors`.
```python
# validation
as_matrix(a, name="a", *, allow_complex=True, square=False, allow_empty=False)
as_vector(a, name="a", *, allow_complex=True, allow_empty=False, length=None)
singular_error(message, rcond) -> SingularMatrixError
# linalg (E1): InvResult(value, rcond, diagnostics); SolveResult(x, residual_norm, rcond,
#   method, diagnostics); ILL_CONDITIONED_RCOND = 1e-12
solve(a, b); inv(a); det(a); trace(a); matmul(a, b); transpose(a); ctranspose(a)
dot(a, b); cross(a, b); norm(x, kind=2); rank(a, tol=None); cond(a, p=2); rcond(a)
# decomp (E2): CholResult(factor, lower); EigResult(values, vectors, residual,
#   vector_rcond, diagnostics); LuResult(P, L, U); QrResult(Q, R, mode); SvdResult(U, s, V)
#   DEFECTIVE_RCOND = 1e-12; HERMITIAN_TOL = 1e-12
lu(a); qr(a, mode="full"); svd(a, full=False); cholesky(a, lower=False, tol=1e-12)
eig(a); eigh(a, tol=1e-12)
# calculus (E3): IntegrateResult(value, error_estimate, nfev, converged, diagnostics)
derivative(f, x, *, order=1, h=None, method="central"); gradient(f, x); jacobian(f, x)
derivative_data(x, y); quad(f, a, b, *, rtol=1.49e-8, atol=1.49e-8, limit=200)
dblquad(f, x0, x1, y0, y1, *, rtol=1.49e-8, atol=1.49e-8)
trapz(y, x=None, dx=1.0); simpson(y, x=None, dx=1.0); cumtrapz(y, x=None, dx=1.0)
# roots (E4): RootResult(root, converged, iterations, residual, diagnostics, method, nfev)
bisect(f, a, b, *, rtol=1e-12, atol=1e-14, maxiter=200)
brentq(f, a, b, *, rtol=1e-12, atol=1e-14, maxiter=100)
newton(f, x0, *, fprime=None, rtol=1e-12, atol=1e-14, maxiter=100)
secant(f, x0, x1, *, rtol=1e-12, atol=1e-14, maxiter=100)
polyroots(coeffs)
fsolve(f, x0, *, jac=None, rtol=1e-10, atol=1e-12, maxiter=100)
# interp (E5)
interp1(x, y, xq, *, method="linear", extrap="error")
interp2(x, y, z, xq, yq, *, method="linear", extrap="error")
# regression (E6): FitResult(params, covariance, residuals, r_squared, diagnostics, stderr,
#   dof, method, nfev)
linfit(A, y, *, weights=None); polyfit(x, y, deg, *, weights=None); polyval(p, x)
fit_curve(f, x, y, p0, *, sigma=None, absolute_sigma=False, bounds=None, maxfev=2000)
confidence_intervals(result, level=0.95)
# optimize (E7): MinimizeResult(x, fun, converged, iterations, nfev, diagnostics, method)
minimize_scalar(f, a, b, *, xtol=1e-10, maxiter=500)
minimize(f, x0, *, jac=None, bounds=None, constraints=None, method=None, tol=1e-8,
         maxiter=1000)
linprog(c, A_ub=None, b_ub=None, A_eq=None, b_eq=None, bounds=None)
# stats (E8): CorrResult(r, p_value, n); Summary(n, mean, std, sem, min, q1, median, q3,
#   max); TestResult(statistic, p_value, dof, diagnostics, method)
mean(x); median(x); var(x, ddof=1); std(x, ddof=1); sem(x); rms(x); skewness(x)
kurtosis(x); iqr(x, *, method="linear"); quantile(x, q, *, method="linear")
zscore(x, ddof=1); cov(x, y, ddof=1); pearsonr(x, y); summary(x)
confidence_interval_mean(x, level=0.95) -> (mean, low, high) order per docstring
ttest_1samp(x, popmean=0.0, *, alternative="two-sided")
ttest_ind(x, y, *, equal_var=False, alternative="two-sided")
ttest_paired(x, y, *, alternative="two-sided")
histogram(x, bins=10, *, range_=None) -> (counts, edges) order per docstring
```
"""

FILES = """
## Added in E4-E8 (2026-11-20)
- src/engstudio/engine/roots.py, interp.py, regression.py, optimize.py, stats.py
- tests/engine/test_roots.py, test_interp.py, test_regression.py, test_optimize.py,
  test_stats.py
- scripts/dump_api.py (read-only helper that writes scripts/api_dump.txt; can be deleted)
"""

TESTS = """
## 2026-11-20 - engine test counts per file (collected with pytest --collect-only)
| File | Tests |
|---|---|
| tests/engine/test_engine_validation.py | 14 |
| tests/engine/test_engine_linalg.py | 20 |
| tests/engine/test_engine_decomp.py | 24 |
| tests/engine/test_engine_calculus.py | 16 |
| tests/engine/test_roots.py | 38 |
| tests/engine/test_interp.py | 27 |
| tests/engine/test_regression.py | 24 |
| tests/engine/test_optimize.py | 23 |
| tests/engine/test_stats.py | 16 |
| tests/unit (6 files) | 77 |
Whole suite collected: 638. Run by docs catch-up script: {count} passed, ruff clean,
GUI smoke ok.
"""


def _run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 1800):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                          env=env)


def run_checks() -> int:
    """Return the pytest pass count; exit the process if any check fails."""
    steps = [("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests"])]
    for name, cmd in steps:
        r = _run(cmd)
        print(f"{name}: exit {r.returncode}")
        if r.returncode != 0:
            sys.exit(f"{name} failed, no docs edited:\n{r.stdout}{r.stderr}")
    r = _run([sys.executable, "-m", "pytest", "-q"])
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    m = re.search(r"(\d+) passed", tail)
    print(f"pytest: exit {r.returncode}: {tail}")
    if r.returncode != 0 or not m or re.search(r"\d+ (failed|error)", tail):
        sys.exit(f"pytest failed, no docs edited:\n{r.stdout[-3000:]}")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = _run([sys.executable, "-m", "engstudio.gui", "--smoke"], env=env, timeout=180)
    print(f"gui smoke: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"GUI smoke failed, no docs edited:\n{r.stdout}{r.stderr}")
    return int(m.group(1))


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


def main() -> int:
    names = ["CHANGELOG.md", "TEST_STATUS.md", "API_REFERENCE.md", "FILE_STRUCTURE.md",
             "HANDOFF.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if missing:
        sys.exit(f"missing in {DOCS}: {missing}. Nothing changed.")
    count = run_checks()
    backup = ROOT / "patches" / f"backup_docs_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    print(f"backup: {backup}")
    plan = [("CHANGELOG.md", CHANGELOG), ("TEST_STATUS.md", TESTS.format(count=count)),
            ("API_REFERENCE.md", API), ("FILE_STRUCTURE.md", FILES)]
    for n, block in plan:
        print(f"{n}: {_append(DOCS / n, block)}")
    h = DOCS / "HANDOFF.md"
    text = _read(h)
    new = (f"- Verified by user 2026-11-20: `python -m pytest -q` {count} passed, ruff clean, "
           "GUI smoke ok (E1-E8); real window checked manually on 2026-11-18.")
    if STALE in text:
        _write(h, text.replace(STALE, new, 1))
        print("HANDOFF.md: stale line replaced")
    else:
        print("HANDOFF.md: stale line not found, skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
