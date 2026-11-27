# API_REFERENCE
Status: **design contracts only (Phase 1). Nothing implemented.** Update this file as each API lands.

## core.errors
`EngStudioError` > `ValidationError` > `DimensionError`, `UnitError`; `SingularMatrixError(rcond)`, `ConvergenceError(iterations, last_estimate)`, `NotSupportedError`, `PluginError` (E_PLUGIN).

## core.diagnostics
`Diagnostic(severity, code, message, location=None)`; `SourceLoc(file, line, col)`.

## core.trace
`Trace.step(description, **values)`; functions accept `trace: Trace | None = None`.

## core.units
`convert(value, from_unit, to_unit)` (float or ndarray), `conversion_factor(a, b)`, `dimension_of(u)`, `is_compatible(a, b)`, `known_units()`, `format_dimension(dim)`. Compound expressions (`kg*m/s^2`, `W/(m*K)`, `m^3`, `1/s`); case-sensitive ASCII names with aliases (`°C`, `Ω`, `µm`). `degC`/`degF` only standalone (use `delta_degC`/`delta_degF` for differences). Angle is a separate base dimension, so `Hz` and `rad/s` are NOT interchangeable. Raises `UnitError` (unknown/incompatible/syntax) or `ValidationError` (non-numeric value). SI base everywhere.

## core.plugin / core.registry
`@tb_function(name, category, args, returns, doc)` wraps a function so each call validates `Arg` specs and passes normalised values (scalar -> float/int, array -> float64 ndarray). `Arg(name, unit, shape, positive, nonnegative, min, max, integer, finite=True, optional, choices, complex_ok, doc)`: errors are `ValidationError`/`DimensionError`; definition mistakes raise `PluginError`. `Ret(name, unit, doc)`. `@sim_block(name, category)` (metadata only until Phase 9). `CATEGORIES` (15), `PLUGIN_API_VERSION = 1`, `parse_manifest(text)`, `load_manifest(path)`, `ToolboxManifest.compatibility_diagnostic()`. `Registry`: `add_function`, `add_block`, `register_module(module, toolbox)`, `remove_toolbox`, `get_function`, `find_function`, `call`, `functions(category, toolbox)`, `get_block`, `blocks(...)`.

## engine (planned signatures, v0 draft)
```python
linalg.solve(A, b, *, trace=None) -> SolveResult
linalg.inv(A) -> ndarray            # SingularMatrixError if singular
linalg.eig(A) -> EigResult(values, vectors)
solvers.fzero(f, bracket|x0, *, rtol=1e-12, atol=1e-12, maxiter=100) -> RootResult
calculus.integrate(f, a, b, *, rtol=1e-10, atol=1e-12) -> IntegralResult(value, error_estimate)
calculus.derivative(f, x, *, h=None, order=1, method="central") -> ndarray
ode.solve(f, t_span, y0, *, method="RK45", rtol=1e-6, atol=1e-9) -> OdeResult
regression.polyfit(x, y, deg) -> FitResult
optimize.minimize(f, x0, *, bounds=None, constraints=None, method=None) -> OptimizeResult
stats.describe(x, *, ddof=1) -> StatsResult
```

## lang
`Interpreter(host: Host)`; `.execute(source, filename) -> list[Diagnostic]`; `Host` protocol: `write(text)`, `figure_update(FigureSpec)`, `cancelled() -> bool`.

## app.kernel (protocol v1 draft)
Requests: `Execute`, `Cancel`, `GetVariable`, `SetVariable`, `RunSimulation`, `ListToolboxes`, `Shutdown`.
Events: `Stdout`, `Diagnostics`, `WorkspaceSummary`, `VariableValue`, `FigureUpdate`, `SimProgress`, `SimResult`, `ExecutionFinished`.
`KernelClient` interface: `send(request)`, `events` (Qt signal wrapper in gui layer), `close()`.

## sim
`Model`, `Block`, `Line`, `SolverSettings`; `compile(model) -> CompiledModel`; `run(compiled, settings, progress_cb, cancel) -> SimResult`; `.esmodel` JSON with `schema_version`.


## engstudio.lang.lexer (T3.1)
- `tokenize(source: str, file: str | None = None) -> list[Token]` - ends with an `EOF` token; raises `LexError` on the first lexical error.
- `Token(kind, text, loc: SourceLoc, value, space_before, synthetic)`. Kinds: NUMBER (float), IMAG (complex), IDENT, KEYWORD, STRING, DQSTRING, TRANSPOSE, NEWLINE, EOF, and punctuation/operators (kind == text). Inside `[]`/`{}`: synthetic `,` between whitespace-separated elements and synthetic `;` for newlines.
- `LexError(EngStudioError)`, code `E_LEX`, attribute `.location`.

## engstudio.gui (G1)
- `app_main.main(argv=None) -> int`; `--smoke` opens and quits, no settings I/O.
- `MainWindow(settings: UiSettings | None)`: `set_theme(name)`, `toggle_theme()`, `reset_layout()`, `set_all_panels(bool)`, `docks`, `tabs`.
- `UiSettings(path | None)`: `get/set/get_bytes/set_bytes/save`; `default_settings_path()`.
- `theme`: `get_palette`, `build_stylesheet`, `apply_theme`, `contrast_ratio`, `LIGHT`, `DARK`.
- `panels`: `PanelSpec`, `default_panels()`. `editor_tabs`: `ScriptTabs`, `ScriptEditor`.

## Kernel protocol additions (G3.2)
- `ListToolboxes(request_id)` request; `KernelClient.list_toolboxes() -> int`
- `ToolboxList(request_id, toolboxes)` event; `ToolboxInfo(name, display_name, functions)`;
  `ToolboxFunction(name, summary, signature)`. Protocol version unchanged (additive).

## Syntax highlighting (G4)
- `engstudio.app.syntax.SYNTAX_KEYWORDS: frozenset[str]` (mirrors `lang.lexer.KEYWORDS`)
- `engstudio.gui.highlight_rules.tokenize_line(text, in_block, keywords) -> (list[Token], in_block)`

## Figure model (G5.1)
- `engstudio.plotting.model`: `SeriesSpec(kind, x, y, label, color, line_style, line_width, marker, marker_size)`, `AxesSpec(series, title, xlabel, ylabel, xlim, ylim, xscale, yscale, grid, legend)`, `FigureSpec(number, title, axes, rows, cols)`.
- Data are copied to read-only 1-D float64; 1xN/Nx1 flattened; matrices -> `DimensionError`; complex -> `ValidationError`; NaN allowed.
- `FigureUpdate(request_id, figure)` event in `app.kernel.protocol`.

## Figure model (G5.1)
- `engstudio.plotting.model`: `SeriesSpec(kind, x, y, label, color, line_style, line_width, marker, marker_size)`, `AxesSpec(series, title, xlabel, ylabel, xlim, ylim, xscale, yscale, grid, legend)`, `FigureSpec(number, title, axes, rows, cols)`.
- Data are copied to read-only 1-D float64; 1xN/Nx1 flattened; matrices -> `DimensionError`; complex -> `ValidationError`; NaN allowed.
- `FigureUpdate(request_id, figure)` event in `app.kernel.protocol`.

## Figure window (G5.2)
- `engstudio.gui.plots.FigureView(theme).set_figure(FigureSpec)`; `.plot_items()`, `.warnings`, `.set_theme(name)`
- `engstudio.gui.figure_window.FigureWindow(number, theme, parent)` (`closed(int)` signal)
- `MainWindow.show_figure(spec)`; stub command `demo_plot [N]`.

## Figure window (G5.2)
- `engstudio.gui.plots.FigureView(theme).set_figure(FigureSpec)`; `.plot_items()`, `.warnings`, `.set_theme(name)`
- `engstudio.gui.figure_window.FigureWindow(number, theme, parent)` (`closed(int)` signal)
- `MainWindow.show_figure(spec)`; stub command `demo_plot [N]`.

## Figure export (G5.3)
- `engstudio.plotting.export.export_figure(spec, path, *, dpi=150, size_in=(7.2, 4.8))` -> Path; format from suffix (.png/.svg/.pdf); `ValidationError` for other suffixes or bad arguments, `EngStudioError` if the file cannot be written; atomic.
- `build_figure(spec, size_in)` -> Matplotlib Figure (no pyplot).
- GUI path: `engstudio.app.figure_export.save_figure`; `FigureWindow.save_as()` / `save_to(path)`.
- Unlabelled series without a colour use Matplotlib's colour cycle in exports.

## Figure window (G5.2)
- `engstudio.gui.plots.FigureView(theme).set_figure(FigureSpec)`; `.plot_items()`, `.warnings`, `.set_theme(name)`
- `engstudio.gui.figure_window.FigureWindow(number, theme, parent)` (`closed(int)` signal)
- `MainWindow.show_figure(spec)`; stub command `demo_plot [N]`.

## Figure export (G5.3)
- `engstudio.plotting.export.export_figure(spec, path, *, dpi=150, size_in=(7.2, 4.8))` -> Path; format from suffix (.png/.svg/.pdf); `ValidationError` for other suffixes or bad arguments, `EngStudioError` if the file cannot be written; atomic.
- `build_figure(spec, size_in)` -> Matplotlib Figure (no pyplot).
- GUI path: `engstudio.app.figure_export.save_figure`; `FigureWindow.save_as()` / `save_to(path)`.
- Unlabelled series without a colour use Matplotlib's colour cycle in exports.

## Diagnostics panel (G6.1)
- `engstudio.gui.diagnostic_log.DiagnosticLog(cap=500)`: `add(Diagnostics)`, `clear()`, `counts()`, `visible(severities)`, `entries`, `dropped`; `location_parts(SourceLoc)` reads (file, line, column) by field position.
- `engstudio.gui.diagnostics_panel.DiagnosticsPanel(bridge, theme)`: signal `location_activated(file, line, column)`, `activate_row(row)`, `clear()`, `set_theme(name)`.

## Figure window (G5.2)
- `engstudio.gui.plots.FigureView(theme).set_figure(FigureSpec)`; `.plot_items()`, `.warnings`, `.set_theme(name)`
- `engstudio.gui.figure_window.FigureWindow(number, theme, parent)` (`closed(int)` signal)
- `MainWindow.show_figure(spec)`; stub command `demo_plot [N]`.

## Figure export (G5.3)
- `engstudio.plotting.export.export_figure(spec, path, *, dpi=150, size_in=(7.2, 4.8))` -> Path; format from suffix (.png/.svg/.pdf); `ValidationError` for other suffixes or bad arguments, `EngStudioError` if the file cannot be written; atomic.
- `build_figure(spec, size_in)` -> Matplotlib Figure (no pyplot).
- GUI path: `engstudio.app.figure_export.save_figure`; `FigureWindow.save_as()` / `save_to(path)`.
- Unlabelled series without a colour use Matplotlib's colour cycle in exports.

## Diagnostics panel (G6.1)
- `engstudio.gui.diagnostic_log.DiagnosticLog(cap=500)`: `add(Diagnostics)`, `clear()`, `counts()`, `visible(severities)`, `entries`, `dropped`; `location_parts(SourceLoc)` reads (file, line, column) by field position.
- `engstudio.gui.diagnostics_panel.DiagnosticsPanel(bridge, theme)`: signal `location_activated(file, line, column)`, `activate_row(row)`, `clear()`, `set_theme(name)`.

## Figure window (G5.2)
- `engstudio.gui.plots.FigureView(theme).set_figure(FigureSpec)`; `.plot_items()`, `.warnings`, `.set_theme(name)`
- `engstudio.gui.figure_window.FigureWindow(number, theme, parent)` (`closed(int)` signal)
- `MainWindow.show_figure(spec)`; stub command `demo_plot [N]`.

## Figure export (G5.3)
- `engstudio.plotting.export.export_figure(spec, path, *, dpi=150, size_in=(7.2, 4.8))` -> Path; format from suffix (.png/.svg/.pdf); `ValidationError` for other suffixes or bad arguments, `EngStudioError` if the file cannot be written; atomic.
- `build_figure(spec, size_in)` -> Matplotlib Figure (no pyplot).
- GUI path: `engstudio.app.figure_export.save_figure`; `FigureWindow.save_as()` / `save_to(path)`.
- Unlabelled series without a colour use Matplotlib's colour cycle in exports.

## Diagnostics panel (G6.1)
- `engstudio.gui.diagnostic_log.DiagnosticLog(cap=500)`: `add(Diagnostics)`, `clear()`, `counts()`, `visible(severities)`, `entries`, `dropped`; `location_parts(SourceLoc)` reads (file, line, column) by field position.
- `engstudio.gui.diagnostics_panel.DiagnosticsPanel(bridge, theme)`: signal `location_activated(file, line, column)`, `activate_row(row)`, `clear()`, `set_theme(name)`.

## engstudio.engine.linalg (E1)
`solve(a, b) -> SolveResult(x, residual_norm, rcond, method, diagnostics)`; `inv(a) -> InvResult(value, rcond, diagnostics)`; `det`, `trace`, `matmul`, `transpose`, `ctranspose`, `dot` (conjugates first arg), `cross`, `norm(x, kind=2)`, `rank(a, tol=None)`, `cond(a, p=2)`, `rcond(a)`.
rcond < eps -> SingularMatrixError; rcond < 1e-12 -> warning diagnostic ILL_CONDITIONED. Inputs are validated copies (NaN/Inf, empty, ragged, non-numeric -> ValidationError; shape problems -> DimensionError). 1-D b gives 1-D x.
