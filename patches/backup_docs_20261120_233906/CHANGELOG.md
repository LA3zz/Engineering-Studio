# CHANGELOG
Format: Keep a Changelog style. Newest first.

## [Unreleased]
### Added
- T2.7: packaging spike - `engstudio.selftest` (11 bundle checks incl. spawned child process and terminate), `--selftest`/`--selftest-gui` flags, `packaging/engstudio.spec`, `entry.py`, `build.ps1`. PyInstaller onedir build passes on the dev PC (282 MB).
- T2.8: dependency versions pinned (`requirements.lock.txt` UTF-8, table in DEPENDENCIES.md).
- T2.6: test-session offline guard (`tests/conftest.py`): blocks non-loopback connect/DNS/UDP, records attempts and fails tests that make them (even if the error is swallowed).
- T2.5: `core.plugin` (`@tb_function` with automatic argument validation, `Arg`/`Ret`, `@sim_block` metadata, `toolbox.toml` manifest loader, `PLUGIN_API_VERSION`), `core.registry` (explicit `Registry`), `PluginError`; tests incl. beam-deflection reference case.
- T2.4: `core.units` - explicit unit conversion (exact rational factors, compound expressions, offset temperatures, angle as separate dimension) with tests.
- T2.3: architecture test enforcing layer rules, Qt/matplotlib placement, toolbox isolation and import cycles (checker itself tested on synthetic trees).
- T2.2: `core.errors` (typed error hierarchy) and `core.diagnostics` (Diagnostic, SourceLoc) with unit tests.
- T2.1: repo scaffold (pyproject, src layout, `python -m engstudio --version`, pytest/ruff config).
- Phase 1: architecture design and project documentation set (no application code).

## 2026-11-18
### Added
- `engstudio.lang.lexer` (T3.1): tokenizer for the v1 MATLAB-like subset (complex literals, transpose vs string, whitespace-separated matrix elements, comments, block comments, continuation), `LexError` (E_LEX).
- `engstudio.gui` (G1): main window, menus, toolstrip, light/dark themes, six dockable panels (placeholders) with visibility controls, tabbed script editor, JSON UI settings, `python -m engstudio.gui [--smoke]`.
- Tests: tests/lang/test_lexer.py, tests/gui/*.
### Notes
- UI settings use a JSON file (%APPDATA%\EngineeringStudio\ui_settings.json) as an interim stand-in for the SQLite store in ARCHITECTURE.md.
### G2.1
- Added engstudio.app.kernel: protocol (frozen message dataclasses), KernelClient (abstract), StubKernelClient (not an interpreter; name = number, clear). Tests: tests/app/test_kernel_stub.py.

### G2.2
- Added gui.command_window, gui.kernel_bridge, gui.history; panels.py now passes a PanelContext to factories; main_window/app_main patched (optional kernel argument, history persistence, View menu items). The app now runs against StubKernelClient.

### G2.3
- Added gui.workspace_panel (WorkspaceModel + WorkspacePanel: live variable table, sort, filter, Clear Selected/All via kernel, double-click to display), gui.formatting.format_size. panels.py patched to use it.

## 2026-11-19 - G3.1
- Added Current Folder browser (`gui.folder_panel`), wired into panels/main window.

## 2026-11-19 - G3.2
- Added Toolbox browser (`gui.toolbox_panel`), `ListToolboxes`/`ToolboxList` protocol messages, `KernelClient.list_toolboxes` (default: not supported), stub sample catalogue, `MainWindow.insert_in_command`.

## 2026-11-19 - G4
- Script editor syntax highlighting (`gui.highlight_rules` pure tokenizer, `gui.highlighter` Qt adapter, `app.syntax` keyword bridge); highlighting follows the light/dark theme.

## 2026-11-19 - G5.1
- Added `plotting.model` (validated immutable figure description) and the `FigureUpdate` kernel event.

## 2026-11-19 - G5.1
- Added `plotting.model` (validated immutable figure description) and the `FigureUpdate` kernel event.

## 2026-11-19 - G5.2
- Figure window: `gui.plot_params`, `gui.plots` (PyQtGraph), `gui.figure_window`; MainWindow opens and updates figure windows on `FigureUpdate`; stub `demo_plot`. Known limits: bar series are not in the legend and are skipped on log axes.

## 2026-11-19 - G5.2
- Figure window: `gui.plot_params`, `gui.plots` (PyQtGraph), `gui.figure_window`; MainWindow opens and updates figure windows on `FigureUpdate`; stub `demo_plot`. Known limits: bar series are not in the legend and are skipped on log axes.

## 2026-11-19 - G5.3
- Figure export: `plotting.export` (PNG/SVG/PDF via Matplotlib Agg, atomic writes), `app.figure_export`, Save As (Ctrl+S) in the Figure window.

## 2026-11-20 - G5.2
- Figure window: `gui.plot_params`, `gui.plots` (PyQtGraph), `gui.figure_window`; MainWindow opens and updates figure windows on `FigureUpdate`; stub `demo_plot`. Known limits: bar series are not in the legend and are skipped on log axes.

## 2026-11-20 - G5.3
- Figure export: `plotting.export` (PNG/SVG/PDF via Matplotlib Agg, atomic writes), `app.figure_export`, Save As (Ctrl+S) in the Figure window.

## 2026-11-20 - G6.1
- Diagnostics panel (`gui.diagnostic_log` pure history, `gui.diagnostics_panel`): table with severity, code, message, location, run; accumulates across executions; severity filters; Clear; theme-aware colours.

## 2026-11-20 - G5.2
- Figure window: `gui.plot_params`, `gui.plots` (PyQtGraph), `gui.figure_window`; MainWindow opens and updates figure windows on `FigureUpdate`; stub `demo_plot`. Known limits: bar series are not in the legend and are skipped on log axes.

## 2026-11-20 - G5.3
- Figure export: `plotting.export` (PNG/SVG/PDF via Matplotlib Agg, atomic writes), `app.figure_export`, Save As (Ctrl+S) in the Figure window.

## 2026-11-20 - G6.1
- Diagnostics panel (`gui.diagnostic_log` pure history, `gui.diagnostics_panel`): table with severity, code, message, location, run; accumulates across executions; severity filters; Clear; theme-aware colours.

## 2026-11-20 - G5.2
- Figure window: `gui.plot_params`, `gui.plots` (PyQtGraph), `gui.figure_window`; MainWindow opens and updates figure windows on `FigureUpdate`; stub `demo_plot`. Known limits: bar series are not in the legend and are skipped on log axes.

## 2026-11-20 - G5.3
- Figure export: `plotting.export` (PNG/SVG/PDF via Matplotlib Agg, atomic writes), `app.figure_export`, Save As (Ctrl+S) in the Figure window.

## 2026-11-20 - G6.1
- Diagnostics panel (`gui.diagnostic_log` pure history, `gui.diagnostics_panel`): table with severity, code, message, location, run; accumulates across executions; severity filters; Clear; theme-aware colours.

## 2026-11-20
- G6.2 Documentation panel (app.docs, gui.docs_panel, 10 pages).
- E1 engine.validation and engine.linalg.

## 2026-11-20
- E2 engine.decomp and E3 engine.calculus recorded (built in earlier chats); test fix: nested pytest.approx replaced; 510 tests.

<!-- docs-catchup E2-E8 -->
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

<!-- docs E9 -->
## 2026-11-20 - E9
- `engine.ode`: `solve_ode` over SciPy `solve_ivp` (RK45, RK23, DOP853, Radau, BDF, LSODA),
  `OdeResult`, `METHODS`. Explicit rtol/atol, optional t_eval, events, user Jacobian, max_step,
  first_step and an evaluation budget `max_nfev`. Non-finite right-hand side (blow-up), budget
  exhaustion and solver failure raise `ConvergenceError`; diagnostics: ODE_WARNING,
  ODE_EVENT (info), ODE_STIFF_SUSPECTED (explicit method with many evaluations).
- Note: `OdeResult.y` has shape `(len(t), n_states)` (SciPy's is the transpose).

<!-- docs E10 -->
## 2026-11-20 - E10
- `engine.transforms`: fft, ifft, rfft, irfft, fftfreq, rfftfreq (NumPy FFT, validated),
  window (rect/boxcar, hann, hamming, blackman, bartlett, flattop; periodic or symmetric),
  amplitude_spectrum (single-sided, window-gain corrected), psd (one-sided periodogram),
  convolve (full/same/valid), butter_filter (low/high/band/bandstop, zero-phase option),
  `SpectrumResult`, `WINDOWS`.
