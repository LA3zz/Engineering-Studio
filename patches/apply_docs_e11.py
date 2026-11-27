"""Docs update for E11 (idempotent). Run: python patches\\apply_docs_e11.py

ruff, full pytest, the E11 test file and the GUI smoke must pass first, else nothing is edited.
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
MARKER = "<!-- docs E11 -->"

CHANGELOG = """
## 2026-11-20 - E11
- `engine.symbolic` over SymPy: `SymExpr`, parse (tokenizer-guarded, no raw eval, exponent
  cap), simplify, expand, factor, subs, equivalent, to_numeric, lambdify, diff, integrate,
  limit, series, solve, solve_system, laplace, inverse_laplace. Unevaluated, conditional,
  divergent, incomplete or non-existent results raise `NotSupportedError` instead of being
  returned silently.
"""

API = """
## engstudio.engine.symbolic (E11)
```python
SymExpr(expr)  # .free_symbols -> tuple[str, ...]; .latex(); str() = SymPy text form
parse(text); simplify(e); expand(e); factor(e); subs(e, mapping); equivalent(a, b) -> bool
to_numeric(e, values=None) -> float | complex; lambdify(e, variables) -> numpy callable
diff(e, var, order=1); integrate(e, var, a=None, b=None, *, allow_conditional=False)
limit(e, var, point, *, direction="+-"); series(e, var, point=0, n=6)
solve(equation, var, *, domain="complex") -> tuple[SymExpr, ...]
solve_system(equations, variables) -> tuple[dict[str, SymExpr], ...]
laplace(e, t, s); inverse_laplace(e, s, t)            # inverse valid for t > 0
FUNCTIONS, CONSTANTS                                   # reserved names
```
- Arguments may be `SymExpr`, text (`x^2 + sin(x)`, `^` is power, no implicit
  multiplication) or numbers. Reserved: sin cos tan asin acos atan sinh cosh tanh exp log (natural)
  ln log10 sqrt abs, pi e I oo inf. Other identifiers are plain symbols.
- Errors: `ValidationError` (bad text/arguments, unknown function, exponent > 1000,
  undefined constants), `NotSupportedError` (no closed form, conditional or divergent integral,
  non-finite solution set, two-sided limit that does not exist).
- Limits of honesty: `solve` returns distinct solutions only; `solve_system` can miss solutions
  of nonlinear systems; `equivalent` False means "not shown equal".
"""

FILES = """
## Added in E11 (2026-11-20)
- src/engstudio/engine/symbolic.py
- tests/engine/test_symbolic.py
"""

TESTS = """
## 2026-11-20 - E11
- tests/engine/test_symbolic.py: {n_new} tests (safe parsing and rejection cases, identities
  checked by differentiating back, numeric cross-checks against engine.calculus, known limits
  and series, Laplace table and round trip, refusal paths).
- Verified with SymPy {sympy_version}. Full suite: {count} passed, ruff clean, GUI smoke ok.
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
    n_new = _passed(_run([sys.executable, "-m", "pytest", "tests/engine/test_symbolic.py", "-q"]),
                    "test_ode")
    count = _passed(_run([sys.executable, "-m", "pytest", "-q"]), "pytest")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = _run([sys.executable, "-m", "engstudio.gui", "--smoke"], env=env, timeout=180)
    print(f"gui smoke: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"GUI smoke failed, no docs edited:\n{r.stdout}{r.stderr}")
    return count, n_new


def _sympy_version() -> str:
    r = _run([sys.executable, "-c", "import sympy; print(sympy.__version__)"])
    return r.stdout.strip() or "unknown"


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
    text, ok = _edit_line(text, "Last updated: 2026-11-20, after E10",
                          "Last updated: 2026-11-20, after E11 (docs synced).")
    done.append(("last updated", ok))
    old = "SpectrumResult) done. Next: E11."
    new = ("SpectrumResult) done; `engine.symbolic` (E11: SymExpr, parse, diff, integrate, "
           "limit, series, solve, solve_system, laplace, inverse_laplace; unevaluated results "
           "raise NotSupportedError) done. Next: E12.")
    ok = old in text
    text = text.replace(old, new, 1) if ok else text
    done.append(("engine state", ok))
    text, ok = _edit_line(text, "**E11** Symbolic mathematics",
                          "**E12** Uncertainty propagation in `engine.uncertainty` per "
                          "ARCHITECTURE section 6 (`propagate(f, x, ux, method='linear'|"
                          "'montecarlo')`): GUM first-order law using the numerical Jacobian "
                          "from `engine.calculus`, optional input covariance, per-input "
                          "contributions, expanded uncertainty (coverage factor), Monte Carlo "
                          "with explicit seed; frozen Result dataclass with diagnostics; "
                          "tested against closed-form cases (sums, products, powers, "
                          "correlated inputs). Then the engine API docs page in "
                          "`app/docs_pages` (list the E1-E12 modules). BEFORE building, list "
                          "`src\\engstudio\\engine` to see what exists.")
    done.append(("next task", ok))
    old = "Then E12 per"
    ok = old in text
    text = text.replace(old, "Then Phase 4 per", 1) if ok else text
    done.append(("then line", ok))
    text, n = re.subn(r"(`python -m pytest -q` )\d+( passed, ruff clean, GUI smoke ok \()E1-E10\)",
                      rf"\g<1>{count}\g<2>E1-E11)", text)
    done.append(("verified line", n > 0))
    _write(p, text)
    for name, ok in done:
        print(f"HANDOFF.md {name}: {'edited' if ok else 'not found, skipped'}")


def _edit_tasks(count: int) -> None:
    p = DOCS / "TASKS.md"
    text = _read(p)
    old = "- [ ] E11 symbolic mathematics"
    if old in text:
        done = f"- [x] E11 (verified 2026-11-20, {count} tests) symbolic mathematics"
        text = text.replace(old, done, 1)
        _write(p, text)
        print("TASKS.md: E11 ticked")
    else:
        print("TASKS.md: E11 line not found, skipped")


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
            ("TEST_STATUS.md",
             TESTS.format(count=count, n_new=n_new, sympy_version=_sympy_version()))]
    for n, block in plan:
        print(f"{n}: {_append(DOCS / n, block)}")
    _edit_handoff(count)
    _edit_tasks(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
