# TEST_STATUS
Last updated: 2026-11-18 (end of Phase 2)

| Suite | Location | Status |
|---|---|---|
| all tests | pytest -q | 94 passed in 8.98s |
| unit | tests/unit | included above (version, errors/diagnostics, units, plugin/registry, offline guard, selftest) |
| architecture (import rules) | tests/architecture | 17 tests, included above |
| offline guard | tests/conftest.py | active for every test |
| lint | ruff check . | All checks passed |
| frozen smoke (build) | packaging\build.ps1 | PASSED on dev PC: onedir 282 MB; `--version`, `--selftest` (11/11, normal and minimal PATH), `--selftest-gui` all exit 0 |
| frozen startup time | same | selftest wall time 19.4 s first run, 6.3 s on later run (scipy import dominates) |
| clean PC (no Python) | manual | NOT YET DONE (task T2.7b) |
| numerical validation | tests/validation | not created |
| interpreter conformance | tests/conformance | not created |
| GUI (pytest-qt, offscreen) | tests/gui | not created |
| integration (kernel e2e) | tests/integration | not created |

Environment: Windows 10 (build 26300), Python 3.11.9. See DEPENDENCIES.md for versions.
## 2026-11-18 (Windows 10, Python 3.11.9, user-run)
- `python -m pytest tests\gui tests\lang tests\architecture -q`: 81 passed in 2.13 s (includes 42 lexer tests; GUI tests run headless/offscreen).
- `python -m ruff check src\engstudio\gui tests\gui` and `src\engstudio\lang tests\lang`: all checks passed.
- `python -m engstudio.gui --smoke` (offscreen): exits cleanly; Qt prints a harmless "Cannot find font directory" notice.
- Manual real-window check (user-reported OK): panels shown, theme toggle, hide/restore panels, new/type/save, layout and theme persistence.
- Not covered: only tests\gui, tests\lang, tests\architecture were in this run; GUI not yet in the PyInstaller build; T2.7b clean-PC test still pending.
- G2.1 (user-run): full suite python -m pytest -q: 188 passed in 22.20 s.

- G2.2 (user-run): python -m pytest -q: 210 passed in 18.80 s. Ruff and manual window check: pending.

- G2.2 manual real-window check (user-reported): OK.

- G2.3 (user-run): python -m pytest -q: 227 passed; ruff clean (after B008 fix); manual real-window check OK. T2.7b deferred by user.

- 2026-11-19 G3.1: pytest 238 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).
- KNOWN ISSUE: the GUI test process intermittently aborts at Qt teardown (exit 0xC0000409, about 50% of full runs) although all tests pass; the real app exits cleanly (0 of 6 smoke runs failed). Workaround: tests/gui/conftest.py exits with pytest's own status via os._exit (disable: ENGSTUDIO_NO_FAST_EXIT=1). Root cause not found.

- 2026-11-19 G3.2: pytest 254 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-19 G4: pytest 282 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-19 G5.1: pytest 324 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-19 G5.1: pytest 324 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-19 G5.2: pytest 354 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-19 G5.2: pytest 388 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-19 G5.3: pytest 388 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G5.2: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G5.3: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G6.1: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G5.2: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G5.3: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G6.1: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G5.2: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G5.3: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

- 2026-11-20 G6.1: pytest 412 passed, ruff clean, `engstudio.gui --smoke` exit 0 (Windows).

## 2026-11-20
- pytest: 470 passed; ruff clean; GUI smoke ok.

## 2026-11-20
- pytest: 510 passed; ruff clean; GUI smoke ok.

<!-- docs-catchup E2-E8 -->
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
Whole suite collected: 638. Run by docs catch-up script: 638 passed, ruff clean,
GUI smoke ok.

<!-- docs E9 -->
## 2026-11-20 - E9
- tests/engine/test_ode.py: 83 tests (analytic: exponential decay, logistic, harmonic
  oscillator with energy conservation, stiff y' = -1000 (y - cos t) - sin t with exact solution
  cos t, free-fall event time sqrt(2h/g), blow-up y' = y^2, budget, validation).
- Full suite: 721 passed, ruff clean, GUI smoke ok.

<!-- docs E10 -->
## 2026-11-20 - E10
- tests/engine/test_transforms.py: 44 tests (DFT definition, known pairs, Parseval,
  round trips, window values, bin-centred amplitude, PSD integral, hand-computed convolution,
  Butterworth -3 dB at cutoff, validation).
- Full suite: 765 passed, ruff clean, GUI smoke ok.

<!-- docs E11 -->
## 2026-11-20 - E11
- tests/engine/test_symbolic.py: 93 tests (safe parsing and rejection cases, identities
  checked by differentiating back, numeric cross-checks against engine.calculus, known limits
  and series, Laplace table and round trip, refusal paths).
- Verified with SymPy 1.14.0. Full suite: 858 passed, ruff clean, GUI smoke ok.
