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
