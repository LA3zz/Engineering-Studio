# TEST_STATUS
Last updated: 2026-11-27 (end of Phase 9, before the 0.8.0 build)

| Suite | Location / command | Status |
|---|---|---|
| non-GUI tests | `pytest -q tests --ignore=tests\gui` | 2198 passed in 61 s |
| GUI tests (offscreen) | `pytest -q tests\gui` (QT_QPA_PLATFORM=offscreen) | 304 passed in 76 s |
| lint | `ruff check .` | All checks passed |
| numerics validation | `python tools\validate_numerics.py` | 170 / 170 |
| architecture (layer rules, import cycles) | tests/architecture | included above |
| toolboxes (9 toolboxes, 85 functions) | tests/toolboxes | included above; hand calculations and textbook values |
| every example script runs clean | tests/toolboxes/test_examples_run.py | 10 scripts, incl. full_feature_test.m (no FAIL lines) |
| docs complete, links resolve | tests/app/test_docs_pages.py | included above |
| offline guard | tests/conftest.py | active for every test; working folder restored after each test |
| frozen build smoke | packaging\build.ps1 | see Phase 10 entry below |
| clean PC (no Python) | manual | NOT DONE (task T2.7b needs a second PC or VM) |

Environment: Windows 11 (build 26300), Python 3.11.9. Run the non-GUI and GUI folders in
separate processes (a single-process full run hung twice on 2026-11-27; not reproduced).
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

<!-- docs E12 -->
## 2026-11-21 - E12
- tests/engine/test_uncertainty.py: 43 tests (GUM closed forms for sum, product, power,
  parallel resistors and correlated difference; coverage factors; Monte Carlo against exact
  normal and chi-square statistics; reproducibility; validation and warnings).
- Full suite: 901 passed, ruff clean, GUI smoke ok.

<!-- docs E12b -->
## 2026-11-21 - E12b
- tests/app/test_engine_api_page.py: 27 tests (page registered and linked; one section per engine module;
  every documented function exists in the module and is mentioned on the page).
- Full suite: 928 passed, ruff clean, GUI smoke ok.

<!-- docs G7 -->
## 2026-11-21 - G7
- tests/gui/test_theme_custom.py and tests/gui/test_theme_editor_gui.py: 65 tests (hex
  parsing, palette validation, WCAG contrast pairs with known ratios, names, persistence round
  trips, JSON import/export errors, dialog logic without a real colour dialog, main-window
  integration).
- Full suite: 993 passed, ruff clean, GUI smoke ok.

<!-- docs B2b-1/2 -->
## 2026-11-24 - B2b-1, B2b-2 (Windows 10, Python 3.11.9, user-run)
- tests/lang/test_builtins_poly.py, tests/lang/test_builtins_data.py, tests/app/test_kernel_b2b1.py added.
- Full suite: `python -m pytest -q` 1837 passed in 190.99 s; `ruff check src tests` clean. The usual `QThreadStorage ... destroyed` line prints at exit (known Qt teardown issue).
- Manual probes in the GUI (probe_b2b1.m, probe_b2b2.m): output as expected.
- Not yet verified: Code.m (MECH 322) numeric section; frozen build with the GUI.

## B2b-3 (2026-11-25)
- tests/lang/test_builtins_funcs.py added (15 tests); VERIFIED 2026-11-25: 1852 passed.

## B2b-4 (2026-11-25)
- tests/lang/test_builtins_analysis.py (10 tests), tests/engine/test_stats_tquantile.py (7 tests): PENDING user run.

## B2b-5 (2026-11-25)
- tests/lang/test_builtins_sym.py, tests/engine/test_symbolic_ext.py: PENDING user run.

## K3 (2026-11-25)
- tests/app/test_input_state.py, tests/gui/test_command_window_multiline.py: PENDING user run.

## P5.1 figure state (2026-11-26)
- New: tests/lang/test_figstate.py (27, ran in the sandbox), tests/lang/test_builtins_plot.py and tests/app/test_kernel_plot.py (written, not run in the sandbox: it has no lang/engine). Pending: full pytest + ruff on the user's PC.
