# HANDOFF
Last updated: 2026-11-20, after E10 (docs synced).

## How to resume in a new conversation
Paste the short role/rules prompt, then attach this file, ARCHITECTURE.md, TASKS.md, and only the source files named below. All project docs live in `docs\project\`.

## State
- Phase 1, 2 done. T2.7b (clean-PC test) DEFERRED by the user: repeat once on the final frozen build that includes the GUI (Windows Sandbox on Pro editions, or a VM).
- Project: C:\Users\ma704\Downloads\EngineeringStudio, venv `.venv`, Python 3.11.9, Windows 10. Versions: DEPENDENCIES.md, `requirements.lock.txt`.
- Engine: `engine.validation` (as_matrix/as_vector/singular_error) and `engine.linalg` (solve, inv, det, trace, matmul, transpose, ctranspose, dot, cross, norm, rank, cond, rcond; SolveResult/InvResult) done (E1). `engine.decomp` (E2), `engine.calculus` (E3) and `engine.roots` (E4: bisect, brentq, newton, secant, polyroots, fsolve; RootResult) done; `engine.interp` (E5: interp1, interp2) and `engine.regression` (E6: linfit, polyfit, polyval, fit_curve, confidence_intervals; FitResult) done; `engine.optimize` (E7: minimize_scalar, minimize, linprog; MinimizeResult) and `engine.stats` (E8: descriptive stats, quantile, pearsonr, confidence_interval_mean, ttest_1samp/ind/paired, histogram) done; `engine.ode` (E9: solve_ode, OdeResult with y shaped (len(t), n_states), t_eval, events, jac, max_nfev) done; `engine.transforms` (E10: fft/ifft/rfft/irfft, window, amplitude_spectrum, psd, convolve, butter_filter; SpectrumResult) done. Next: E11.
- Interpreter: `lang.lexer` done (T3.1). Next in that series: T3.2 `lang.ast`.
- Kernel: `app.kernel` protocol (frozen message dataclasses), abstract `KernelClient`, `StubKernelClient` (NOT an interpreter: `name = number`, `name`, `clear`). Real process kernel (D2) not built.
- GUI (all via KernelClient; GUI never imports lang/engine): G1 shell (themes, docks, tabbed script editor), G2.2 Command Window (history, red errors, `clc`), G2.3 G4 syntax highlighting (keywords, comments incl. %{ %}, strings, numbers; theme-aware; keywords via `app.syntax`), G3.2 Toolbox browser (ListToolboxes/ToolboxList via the stub catalogue, filter box, double-click inserts the name in the Command Window), G3.1 Current Folder (tree, up/browse/path box, double-click opens .m, folder persisted as `current_folder`), Workspace browser (live table, sort, filter, clear, double-click display). G6.1 done: Diagnostics panel (history across executions, cap 500, severity filters, Clear, `location_activated` signal not yet wired to the editor). G6.2 done: `app.docs.DocService` + `gui.docs_panel` (Markdown pages in `app/docs_pages`, Back/Forward/Home, internal links, theme-aware). Syntax highlighting done (G4). G5.1 done: `plotting.model` (FigureSpec/AxesSpec/SeriesSpec, validated, immutable) and the `FigureUpdate` event; G5.2 done: `gui.plots` (PyQtGraph renderer), `gui.figure_window`, `MainWindow.show_figure` (one window per figure number, updated in place), stub `demo_plot [N]`; G5.3 done: `plotting.export` (PNG/SVG/PDF, Matplotlib Agg, atomic writes, bars drawn on log axes), `app.figure_export`, Save As (Ctrl+S) in FigureWindow.
- Verified by user 2026-11-20: `python -m pytest -q` 765 passed, ruff clean, GUI smoke ok (E1-E10); real window checked manually on 2026-11-18.
- Run GUI: `python -m engstudio.gui` (`--smoke` = open and quit, no settings I/O).
- Decisions in force: Python 3.11, `.m` scripts, kernel in separate process (D2, not implemented), explicit Registry (D9), validated args (D10). Interim: UI settings and command history in JSON (`gui.settings`), to be replaced by SQLite behind the same get/set/save interface.

## Conventions and gotchas
- PowerShell 5.1: write files UTF-8 without BOM ([IO.File]::WriteAllText + UTF8Encoding($false)); `>` writes UTF-16. Native tools writing to stderr abort scripts under `$ErrorActionPreference="Stop"`; wrap with `cmd /c "... 2>&1"`. In a new window always `cd` to the project and activate `.venv` first.
- Delivery pattern: zip of new files (Expand-Archive -Force at project root) + a `patches\apply_*.py` script for edits to existing files (exact-match, idempotent). Python 3.11: `Path.read_text` has no `newline=` argument (3.13+); use `open(..., newline="")`.
- ruff: isort ignores case, line length 100, rule B008 forbids calls in argument defaults (use a module-level singleton, e.g. `_ROOT = QModelIndex()`).
- tests/conftest.py blocks non-loopback network (`blocked_attempts` fixture). Architecture test (tests/architecture/test_import_rules.py) holds the layer table; update with ARCHITECTURE.md. `app` may import `lang` (stub uses lang.lexer.KEYWORDS).
- GUI tests run headless (QT_QPA_PLATFORM=offscreen set in each test file). A fixture that leaves an unsaved editor tab must clear `document().setModified(False)` before closing, else the unsaved-changes dialog hangs the run. `setPlainText` clears the modified flag (use `insertPlainText`). Docks tabbed behind another are not `isVisible()`: test base docks or one per tab group.
- Qt prints "Cannot find font directory" under offscreen: harmless.
- Sandbox used for development has no PySide6/PowerShell/pytest/PyInstaller: Qt code and tests are verified only after the user's Windows run.

- LESSON (2026-11-20): docs lagged the code (E2, E3 were built in another chat). Before any milestone run `dir src\engstudio\engine` and `dir tests\engine`. Expand-Archive only the zip named in the reply, never an older zip of the same name.

## Waiting on the user
Approve the next task.

## Next task
**E11** Symbolic mathematics in `engine.symbolic` over SymPy: `SymExpr` wrapper (parse, simplify, substitute, to-numeric via lambdify), diff, integrate (definite/indefinite), solve, series, limit, Laplace and inverse Laplace; unsupported or unevaluated results are typed errors, never silent; parsing must not use eval on raw text; results checked against known identities. BEFORE building, list `src\engstudio\engine` to see what exists.

Then E12 per 'Agreed plan' in TASKS.md. Later: wire diagnostics `location_activated` to the editor, real kernel process, GUI in the PyInstaller spec (docs pages are already in `datas`), Save/Load Workspace.

## Files that matter now
src/engstudio/engine/*.py, src/engstudio/gui/*.py, src/engstudio/app/kernel/*.py, src/engstudio/lang/lexer.py, src/engstudio/core/*.py, tests/gui/*, tests/app/test_kernel_stub.py, tests/architecture/test_import_rules.py.

## Known problems
- GUI test process intermittently aborts at Qt teardown (0xC0000409); see TEST_STATUS.md. Workaround in tests/gui/conftest.py; root cause open.
- Most panels are placeholders (see State). The stub kernel only holds 1x1 doubles.
- GUI not yet in the PyInstaller spec/frozen build; check Qt plugins and size when added.
- Unverified: behaviour on a PC without Python (T2.7b deferred).