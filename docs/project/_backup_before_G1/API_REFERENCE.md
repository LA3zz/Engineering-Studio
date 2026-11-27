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
