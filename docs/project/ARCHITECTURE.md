# ARCHITECTURE

## 1. Principles
- Dependencies point downward only (layers below). Enforced by an automated import test.
- Pure-Python/NumPy engine; no Qt, no matplotlib in L0–L2.
- Plugins (toolboxes, blocks) register through one mechanism.
- Results are structured; errors are typed; diagnostics are data, not `warnings.warn`/print.

## 2. Layers and allowed imports
| Layer | Package(s) | May import |
|---|---|---|
| L0 | `core` | stdlib, numpy |
| L1 | `engine`, `control`, `data`, `plotting.model` | L0, numpy, scipy, sympy (engine), python-control (control), pandas/openpyxl/sqlite3 (data) |
| L2 | `lang`, `sim`, `toolboxes.<name>` | L0, L1. **Not each other.** (toolboxes may not import other toolboxes; shared code goes to `engine`) |
| L3 | `app` | L0–L2 (toolboxes only through registry loader) |
| L4 | `gui` | `app`, `core`, `plotting.model`, `plotting.text`, `sim.model`, `sim.serialization`, PySide6, pyqtgraph (Matplotlib only in `gui.mpl_view`) |

Special: `plotting.export` (Matplotlib/Agg, no Qt) is L1-level and used by `app` for file export. PyQtGraph rendering lives in `gui.plots`. Root-level modules (`__main__`, `version`, `selftest`) are composition roots and not layered; `engstudio.selftest` is the bundle probe and is exempt from the third-party placement rules (tested).

## 3. Packages and responsibilities
| Package | Responsibility |
|---|---|
| `core` | Error hierarchy, `Diagnostic`, `Trace`, units & conversion, registry/plugin API, paths, logging, version |
| `engine` | Numerical algorithms: linalg, calculus, solvers, ode, interpolation, regression, optimize, stats, transforms, symbolic, uncertainty, validation helpers. Pure functions on arrays |
| `control` | TF/SS/PID, time & frequency response, stability, wrapping python-control with validation and our error types |
| `data` | Reserved (empty). Settings live in `gui.settings` (JSON); file I/O lives in `app.file_bindings` and `app.workspace_files` |
| `plotting` | `model` (FigureSpec/AxesSpec/SeriesSpec/SurfaceSpec/TextSpec), `text` (TeX subset), `export` (Matplotlib Agg PNG/SVG/PDF/GIF) |
| `lang` | Lexer, parser, AST, tree-walking interpreter, value model, builtin function binding to registry. No I/O except through injected `Host` interface (disp, plot, input) |
| `sim` | Model graph, block library, compiler (sorting, loop detection, sample-time propagation), solvers, runner, `.esmodel` serialization |
| `toolboxes.*` | 9 built-in packages (mechanical, thermo, fluids, heat, electrical, materials, structures, robotics, aero; 85 functions): `toolbox.toml`, `__init__.py` (register), `functions.py`. Docs pages in `app/docs_pages`, examples in `examples/`, tests in `tests/toolboxes` |
| `app` | `kernel` (protocol, client, `inprocess` kernel, stub), bindings that add builtins to the interpreter (`toolbox_bindings`, `sim_bindings`, `file_bindings`, `workspace_files`), function help (`help_core`, `help_toolbox`, `function_help`), `sim_service` (model editor runs), `docs` + `docs_pages`, `syntax` (highlight rules), `input_state`, `figure_export` |
| `gui` | Main window, docks, editor (+ call tips, `calltip`), command window, workspace/folder/toolbox browsers (+ details pane), figure windows (PyQtGraph 2-D, embedded Matplotlib 3-D), model editor (`sim_editor`), themes, splash, single instance, update check |

## 4. Kernel model and communication (as built)
```
GUI thread                                   Kernel worker thread (same process)
 gui.* ──Qt signals── gui.KernelBridge ── app.kernel.InProcessKernelClient ── lang / sim / engine / toolboxes
```
- The kernel runs in the GUI's process on a worker thread (the separate-process design of
  Phase 1 was not needed: Stop is a cancel flag checked by the interpreter and by long
  builtins via `interp.check_cancel()`). `InProcessKernelClient(threaded=False)` runs
  synchronously for tests and `engstudio-console --run`.
- The GUI never imports `lang`, `engine` or `toolboxes`; it only sees protocol events and plain
  data (`app.kernel.protocol`).
- Requests: `execute(code, file)`, `cancel(request_id)`, `list_toolboxes()`, `figure_closed(n)`,
  `shutdown()`.
- Events: `Stdout`, `Diagnostics`, `WorkspaceSummary` (name, class, size, preview),
  `ExecutionFinished(status)`, `ToolboxList` (every function with signature, summary, full help,
  argument names and docs; feeds the Toolbox browser and call tips), `FigureUpdate(FigureSpec)`,
  `FigureClosed`, `OpenModel` (`open_system`), `FolderChanged` (`cd`).
- The working folder is the Current Folder panel: the panel `chdir`s; `cd` emits `FolderChanged`.
- Simulation runs from the model editor go through `app.sim_service` on a QThread.
## 5. Value model (interpreter ↔ engine)
| MATLAB-like | Python representation |
|---|---|
| double/complex/logical | `numpy.ndarray`, always ≥2-D, `float64/complex128/bool`; linear indexing uses column-major order |
| char/string | `CharArray` (wraps str/ndarray of `<U1`) |
| cell | `CellArray` (object ndarray) |
| struct | `StructValue` (ordered dict of fields; array of structs later) |
| function handle | `FunctionHandle(name or closure)` |
| symbolic | `SymExpr` (wraps sympy); explicit conversion to numeric |
Engine/toolbox Python APIs accept `array_like` and return ndarray/dataclasses; adaptation (`to_engine`, `from_engine`) lives in `lang.interop`.

## 6. Numerical computation API (contract)
```python
# core.errors
class EngStudioError(Exception): ...
class ValidationError(EngStudioError): ...   # bad input value/type
class DimensionError(ValidationError): ...   # shape mismatch
class UnitError(ValidationError): ...
class SingularMatrixError(EngStudioError): ...  # has .rcond
class ConvergenceError(EngStudioError): ...     # has .iterations, .last_estimate
class NotSupportedError(EngStudioError): ...

# core.diagnostics
@dataclass(frozen=True)
class Diagnostic: severity: Literal["info","warning","error"]; code: str; message: str; location: SourceLoc|None = None

# core.trace
class Trace:  # optional calculation details; functions accept trace: Trace|None = None
    def step(self, description: str, **values): ...
```
Rules:
1. Functions are pure, take `array_like`, never mutate inputs, no global state.
2. Return plain ndarray for simple results; frozen dataclass for results with metadata: `SolveResult(x, residual_norm, rcond, method, diagnostics)`, `RootResult(root, converged, iterations, residual, diagnostics)`, `OdeResult(t, y, status, nfev, diagnostics)`, `FitResult(params, covariance, residuals, r_squared, diagnostics)`.
3. Failure → raise typed error. Degraded-but-valid (e.g., `rcond < 1e-12`) → return result with `Diagnostic(warning)`.
4. Singular: `rcond < eps` → `SingularMatrixError`. Ill-conditioned: `rcond < 1e-12` → warning.
5. Tolerances (`rtol`, `atol`) are explicit keyword args with documented defaults.
6. Units: all inputs/outputs SI; `core.units.convert(value, "psi", "Pa")` explicit; no implicit conversion.
7. Uncertainty: `engine.uncertainty.propagate(f, x, ux, method="linear"|"montecarlo")` (GUM first-order, MC with seed).
8. Naming: Python API `snake_case` in `engstudio.engine.<module>`; interpreter names are registered separately (MATLAB-like lowercase, e.g. `inv`, `det`, `trapz`).
9. Differences from MATLAB conventions are documented per function (e.g., `std` default normalisation, `eig` ordering/sign).

## 7. Plugin / toolbox architecture
Each toolbox is a package `engstudio.toolboxes.<name>`:
```
<name>/
  toolbox.toml        # manifest
  __init__.py         # register() entry point
  functions.py        # @tb_function-decorated pure functions
  blocks.py           # optional simulation blocks (@sim_block)
  docs/*.md           # per-function docs
  examples/*.m
  tests/
```
Manifest (`toolbox.toml`):
```toml
[toolbox]
name = "mechanical"
display_name = "Mechanical Engineering"
version = "0.1.0"
api_version = 1          # core plugin API version required
category = "mechanical"
```
Registration:
```python
@tb_function(name="beam_deflection_ss", category="mechanical",
             args=[Arg("L", unit="m", positive=True), Arg("E", unit="Pa", positive=True), ...],
             returns=[Ret("delta", unit="m")], doc="docs/beam_deflection_ss.md")
def beam_deflection_ss(...): ...
```
- `tb_function` generates input validation from `Arg` specs (shape, positivity, range, unit tag) and records metadata for the toolbox browser/docs.
- `core.registry.Registry` holds functions and blocks; `app.ToolboxManager` loads toolboxes.
- Discovery: (1) built-ins from an explicit list `BUILTIN` in `toolboxes/__init__.py` (explicit so PyInstaller sees them), bound into the interpreter by `app.toolbox_bindings` (a toolbox name never replaces a core builtin; tested); (2) planned, not built yet: user toolboxes folder `%APPDATA%\EngineeringStudio\toolboxes\` (manifest + Python files, loaded only after user enables; trust warning shown).
- Version gate: manifest `api_version` must equal core `PLUGIN_API_VERSION` else toolbox disabled with a diagnostic.
- A toolbox failing to load never prevents startup.

## 8. Simulation architecture
- `sim.model`: `Model`, `Block`, `Port`, `Line`, `SolverSettings` (pure dataclasses; GUI edits these).
- `sim.blocks`: registered via `@sim_block` — declares ports, parameters (with validation), `kind` (continuous/discrete/algebraic/source/sink), `derivatives()`, `output()`, `update()`.
- `sim.compiler`: validate graph → flatten subsystems → topological sort → algebraic-loop detection (error v1) → sample-time propagation → state vector layout.
- Solvers (in `sim.runner`): continuous via `scipy.integrate.solve_ivp` (RK45/RK23/DOP853/Radau/BDF/LSODA); fixed-step RK4/Euler; discrete via major-step scheduling at GCD of sample times; hybrid: integrate between discrete hits.
- `sim.runner`: `run(model, should_stop=...) -> SimResult` (tout, scopes, To Workspace data, outports, displays); `sim.subsystems` flattens subsystems; blocks live in `sim.blocks` + `blocks_sources/sinks/continuous/discrete/nonlinear`.
- `sim.serialization`: `.esmodel` JSON with `schema_version` and migration functions.
- Validation sources: analytic step responses (1st/2nd order), integrator of constant, harmonic oscillator energy conservation.

## 9. Plotting
Interpreter plot commands build/modify `FigureSpec` held in the kernel (`lang.figstate`) and send snapshots as `FigureUpdate` (throttled to 30/s per figure). `gui.plots` renders 2-D with PyQtGraph; 3-D, surfaces, contours and polar plots use an embedded Matplotlib canvas (`gui.mpl_view`); `plotting.export` renders the same spec with Matplotlib/Agg for PNG/SVG/PDF/GIF.

## 10. Data and persistence
- UI settings: `%APPDATA%\EngineeringStudio\ui_settings.json` (`gui.settings.UiSettings`):
  window geometry/state, theme and custom themes, command history, current folder, open
  script tabs (restored at start-up).
- Workspace files: `save`/`load` use MATLAB `.mat` (v5) via `scipy.io` (`app.workspace_files`).
- Lab data: CSV/TXT/DAT/TSV/XLSX via pandas/openpyxl (`app.file_bindings`).
- Models: `.esmodel` JSON (`sim.serialization`). Start-up errors of the packaged app:
  `%LOCALAPPDATA%\EngineeringStudio\startup_error.txt`.

## 10a. Function help and call tips
`app.help_core` (calling forms + summary of every core command), `app.help_toolbox` (meaning
of every toolbox input + a tested example) and `app.function_help` (adds units, limits,
defaults, outputs and result fields from the `@tb_function` declarations) are the one source
for: the Toolbox browser details pane, `help name`, call tips (`gui.calltip`, fed by the
`ToolboxList` event) and the PDF manual (`tools/make_manual.py`). Tests check that every
command and every toolbox input is documented and that every example runs.
## 11. Testing strategy
| Suite | Purpose | Notes |
|---|---|---|
| unit | pure logic | pytest |
| validation | numerical correctness | known analytic results/textbook constants; each test cites source in docstring; explicit tolerances; no values copied from unverified output |
| conformance | interpreter | `tests/conformance/*.m` + `.expected` (stdout/values) |
| architecture | import layering | AST scan of `src/`, compares to layer table; fails on violation or cycle |
| gui | widgets | pytest-qt, `QT_QPA_PLATFORM=offscreen` |
| integration | kernel end-to-end | spawn worker, execute scripts, cancel test |
| offline | no network | session fixture patches `socket.socket.connect` to raise |
| frozen smoke | packaging | `EngineeringStudio.exe --selftest` runs numeric checks + kernel spawn |
Coverage target for `engine` and `lang`: ≥90% lines (reported, not gamed). Every bug fix adds a regression test.

## 12. Offline packaging strategy
- PyInstaller **onedir** (not onefile: faster start, fewer AV false positives, LGPL-friendly dynamic linking of PySide6).
- `packaging/engstudio.spec`: explicit `hiddenimports` for built-in toolboxes, `collect_data_files` for resources/docs/themes, exclude unused Qt modules (WebEngine etc.) and test packages.
- `multiprocessing.freeze_support()` at entry (used by `--selftest`); the kernel itself runs on a thread. Two programs share one runtime: `EngineeringStudio.exe` (windowed) and `engstudio-console.exe` (`--version`, `--selftest`, `--run script.m`).
- Installer: Inno Setup script → per-user install, Start Menu entry, `.m` and `.esmodel` association (optional).
- Updates: Help > Check for Updates (`gui.updates`) reads GitHub's latest release, downloads the
  `EngineeringStudio-Setup-*.exe` asset, verifies its SHA-256 (asset digest or attached `.sha256`),
  closes the app and runs the installer with `/SILENT /UPDATE` (the installer restarts the app).
- Docs shipped as local Markdown in `engstudio/app/docs_pages` (inside a known package so the layer test accepts it), rendered by `QTextBrowser`.
- Gate: smoke build + `--selftest` on a clean Windows VM without Python each phase; third-party license notices bundled.
- Optional heavy components (PyVista/VTK) can be split into a later "3D add-on" if size becomes a problem.

## 13. Decision log
| ID | Decision | Consequence |
|---|---|---|
| D1 | Python 3.14 (since 2026-11-27; 3.11 still works) | All pinned libraries have 3.14 wheels; tests and frozen build pass |
| D2 | Kernel on a worker thread in the GUI process (changed from the planned separate process) | No serialization; Stop via cancel flag; a hard crash in native code would take the GUI down |
| D3 | Handwritten Pratt parser | Full control of MATLAB quirks; more code to test |
| D4 | Plot specs as data | GUI-agnostic plots; renderer parity tests needed |
| D5 | `control` is L1 library | `sim` and toolbox share it without layer violation |
| D6 | Explicit built-in toolbox list | Slight boilerplate; reliable freezing |
| D7 | JSON for models and UI settings, MATLAB .mat for workspaces | No database needed; .mat files interchange with MATLAB |
| D8 | `.m` extension for scripts | Familiar; only our subset runs |
| D9 | Registry is an explicit object; decorators only attach metadata | No global state, easy to test; `app.ToolboxManager` owns the live registry |
| D10 | Validated numeric arguments are normalised before the function body runs | Function bodies can rely on float/float64 types; callers' data is never mutated |

## 14. Technical risks
| ID | Risk | Likelihood/Impact | Mitigation |
|---|---|---|---|
| R1 | Interpreter scope creep | H/H | Frozen v1 subset; "not supported" diagnostics; conformance tests |
| R2 | Frozen build + multiprocessing issues | M/H | Spike in Phase 2 |
| R3 | Bundle size/startup | H/M | Lazy imports, optional PyVista, exclude Qt modules |
| R4 | MATLAB convention differences | H/M | Document; never claim identical outputs |
| R5 | Simulation semantics (loops, hybrid, events) | M/H | Staged scope; analytic validation |
| R6 | Dual plotting backends diverge | M/M | `FigureSpec` contract; golden-spec tests |
| R7 | SymPy performance & typing | M/M | Separate `SymExpr` type; timeouts via kernel kill |
| R8 | AV false positives / unsigned installer | M/M | onedir; later code signing |
| R9 | Licensing/trademark | L/H | License inventory; no MATLAB assets/branding; LGPL compliance |
| R10 | Free-plan context limits | H/M | HANDOFF.md; small tasks; patches only |
| R11 | Dock layout persistence bugs | M/L | Use Qt `saveState`; versioned layout keys |
| R12 | Kernel crash loses workspace | M/M | Periodic autosave of workspace to temp |
