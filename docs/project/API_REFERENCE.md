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

<!-- docs-catchup E2-E8 -->
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

<!-- docs E9 -->
## engstudio.engine.ode (E9)
```python
OdeResult(t, y, status, nfev, diagnostics, method, message, t_events, y_events)
solve_ode(f, t_span, y0, *, method="RK45", rtol=1e-6, atol=1e-9, t_eval=None, events=None,
          jac=None, max_step=inf, first_step=None, max_nfev=200_000) -> OdeResult
METHODS = ("RK45", "RK23", "DOP853", "Radau", "BDF", "LSODA")
```
- `f(t, y)` returns dy/dt (real vector; scalar allowed for one state). `y` shape is
  `(len(t), n_states)`. `status` 0 = reached t1, 1 = stopped by a terminal event.
- Events: SciPy convention (`event(t, y)`, optional `.terminal`, `.direction`); `t_events` /
  `y_events` are tuples with one array per event function.
- `rtol >= 100*eps`; `atol` scalar or per-state vector; `jac` (callable or n x n matrix) only
  for Radau/BDF/LSODA; `t_span` may run backwards.
- Errors: `ValidationError`/`DimensionError` (inputs, wrong f output), `ConvergenceError`
  (step-size failure, non-finite derivative, `max_nfev` exceeded; has `.last_estimate`).
  Exceptions raised inside `f` propagate unchanged.

<!-- docs E10 -->
## engstudio.engine.transforms (E10)
```python
SpectrumResult(freq, values, kind, window, fs, diagnostics)   # kind: "amplitude" | "psd"
fft(x, n=None); ifft(X, n=None); rfft(x, n=None); irfft(X, n=None)
fftfreq(n, d=1.0); rfftfreq(n, d=1.0)
window(name, n, *, periodic=True)          # WINDOWS = rect, boxcar, hann, hamming, ...
amplitude_spectrum(x, fs, *, window="rect", n=None)   # n may only zero-pad
psd(x, fs, *, window="hann", detrend=True)             # units x^2/Hz
convolve(a, b, mode="full")                # "full" | "same" | "valid"
butter_filter(x, fs, cutoff, *, btype="low", order=4, zero_phase=True)
```
- Forward FFT is unnormalised, inverse is 1/N (NumPy/MATLAB convention). Inputs are validated
  1-D copies. A bin-centred sine of amplitude A shows A in `amplitude_spectrum` (DC and even-N
  Nyquist not doubled). Cutoffs in Hz within (0, fs/2); `band`/`bandstop` take (low, high).
- Errors: `ValidationError` (bad values, window name, cutoff, short signal), `DimensionError`
  (matrix input). Uniform sampling is assumed and cannot be checked.

<!-- docs E11 -->
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

<!-- docs E12 -->
## engstudio.engine.uncertainty (E12)
```python
UncertaintyResult(value, standard_uncertainty, expanded_uncertainty, interval, coverage,
                  sensitivities, contributions, method, k=None, n_samples=0, diagnostics=())
propagate(f, x, ux, *, method="linear", corr=None, coverage=0.95, k=None, n=100_000,
          seed=0, vectorized=False) -> UncertaintyResult
```
- `f(x)` takes a 1-D array of input estimates and returns one real number; `ux` are standard
  uncertainties (>= 0, same length as `x`); `corr` an optional symmetric positive semidefinite
  correlation matrix with unit diagonal. `value` is f at the estimates.
- `"linear"`: u_c^2 = g^T U g; interval = value -+ k u_c, k from `coverage` (normal quantile) or
  the explicit `k`. `contributions[i] = |g_i| ux[i]` (not additive when inputs are correlated).
- `"montecarlo"`: `n` samples (100..5,000,000) of normal inputs, `seed` (default 0, `None` =
  fresh entropy); `standard_uncertainty` is the sample std, `interval` the symmetric `coverage`
  interval; `vectorized=True` calls `f` once with an (n, n_inputs) array returning n values.
- Errors: `ValidationError` (bad options, correlation matrix, non-finite or non-scalar model
  output, model undefined in the input distribution), `DimensionError` (size mismatches).

<!-- docs G7 -->
## engstudio.gui.theme_custom (G7, no Qt)
```python
ROLES, ROLE_LABELS, CONTRAST_PAIRS, MIN_CONTRAST = 4.5, MAX_NAME = 40, MAX_THEMES = 50
parse_hex(text) -> "#rrggbb"            # accepts #rgb, rgb, #rrggbb, rrggbb; ValueError
make_palette(name, colors, base) -> Palette   # missing roles come from `base`
contrast_issues(palette, minimum=4.5) -> list[ContrastIssue(fg, bg, ratio)]
role_issues(issues, role) -> str; readable_text_colour(background) -> "#000000" | "#ffffff"
validate_name(name, existing=()) -> str       # not 'light'/'dark', <= 40 chars, no clashes
CustomThemes: names, get, base_of, resolve, set(name, palette, base) -> name, delete(name)
              -> base, to_data(), from_data(data) (bad entries skipped, listed in .errors)
palette_to_json(palette, base) -> str; palette_from_json(text) -> ThemeFile(name, base, palette)
```
Settings key `custom_themes`: `{name: {"base": "light"|"dark", "colors": {role: "#rrggbb"}}}`.
Theme file: `{"format": "engstudio-theme", "version": 1, "name", "base", "colors"}`; missing
colours fall back to the base theme.
`gui.theme.apply_palette(app, palette)` applies any palette; `gui.theme_dialog.ThemeDialog`
(signals `preview_requested(Palette)`, `themes_changed()`, `theme_activated(str)`).
