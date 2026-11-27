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
| L4 | `gui` | `app`, `core`, `plotting.model`, `sim.model`, `sim.serialization`, PySide6, pyqtgraph, pyvista(qt) |

Special: `plotting.export` (Matplotlib/Agg, no Qt) is L1-level and used by `app` for file export. PyQtGraph rendering lives in `gui.plots`. Root-level modules (`__main__`, `version`, `selftest`) are composition roots and not layered; `engstudio.selftest` is the bundle probe and is exempt from the third-party placement rules (tested).

## 3. Packages and responsibilities
| Package | Responsibility |
|---|---|
| `core` | Error hierarchy, `Diagnostic`, `Trace`, units & conversion, registry/plugin API, paths, logging, version |
| `engine` | Numerical algorithms: linalg, calculus, solvers, ode, interpolation, regression, optimize, stats, transforms, symbolic, uncertainty, validation helpers. Pure functions on arrays |
| `control` | TF/SS/PID, time & frequency response, stability, wrapping python-control with validation and our error types |
| `data` | SQLite store (settings, history, recent), CSV/Excel import-export, project file read/write, workspace save/load |
| `plotting` | `model` (FigureSpec/AxesSpec/SeriesSpec dataclasses), `export` (Matplotlib Agg PNG/SVG/PDF) |
| `lang` | Lexer, parser, AST, tree-walking interpreter, value model, builtin function binding to registry. No I/O except through injected `Host` interface (disp, plot, input) |
| `sim` | Model graph, block library, compiler (sorting, loop detection, sample-time propagation), solvers, runner, `.esmodel` serialization |
| `toolboxes.*` | 15 independent packages: functions, manifest, docs, examples, tests |
| `app` | `Session` (workspace + interpreter + host), `kernel` (process, protocol, client), `ProjectManager`, `SimulationService`, `ToolboxManager`, `DocService` |
| `gui` | Windows, docks, editor, command window, workspace/folder/toolbox browsers, figure windows, simulation canvas, themes |

## 4. Process model and communication
```
GUI process                              Kernel process (spawned)
 gui.* ──Qt signals── app.KernelClient ══ pipe ══ app.kernel.Worker ── Session ── lang / sim / engine / toolboxes
```
- GUI never imports `lang`, `engine`, or `toolboxes`. It only sees messages and plain data.
- Transport: `multiprocessing.Connection` (trusted local process), versioned dataclass messages (`PROTOCOL_VERSION`).
- Requests (GUI→Kernel): `Execute(code|file, request_id)`, `Cancel`, `GetVariable(name)`, `SetVariable`, `RunSimulation(model)`, `ListToolboxes`, `Shutdown`.
- Events (Kernel→GUI): `Stdout`, `Diagnostics`, `WorkspaceSummary` (name, class, size, short preview — never whole large arrays), `VariableValue`, `FigureUpdate(FigureSpec)`, `SimProgress`, `SimResult`, `ExecutionFinished(status)`.
- Stop: soft cancel flag checked by interpreter loop; on timeout, kernel process is killed and restarted (workspace lost unless autosaved — documented behaviour).
- Testing: `InProcessKernelClient` implements the same interface synchronously.
- Threads: all kernel work is off the GUI thread; Qt-side client uses `QSocketNotifier`/`QThread` reader and re-emits signals.

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
- Discovery: (1) built-ins from an explicit list in `toolboxes/__init__.py` (explicit so PyInstaller sees them); (2) user toolboxes folder `%APPDATA%\EngineeringStudio\toolboxes\` (manifest + Python files, loaded only after user enables; trust warning shown).
- Version gate: manifest `api_version` must equal core `PLUGIN_API_VERSION` else toolbox disabled with a diagnostic.
- A toolbox failing to load never prevents startup.

## 8. Simulation architecture
- `sim.model`: `Model`, `Block`, `Port`, `Line`, `SolverSettings` (pure dataclasses; GUI edits these).
- `sim.blocks`: registered via `@sim_block` — declares ports, parameters (with validation), `kind` (continuous/discrete/algebraic/source/sink), `derivatives()`, `output()`, `update()`.
- `sim.compiler`: validate graph → flatten subsystems → topological sort → algebraic-loop detection (error v1) → sample-time propagation → state vector layout.
- `sim.solvers`: continuous via `scipy.integrate.solve_ivp` (RK45/RK23/DOP853/Radau/BDF/LSODA); fixed-step RK4/Euler; discrete via major-step scheduling at GCD of sample times; hybrid: integrate between discrete hits.
- `sim.runner`: `run(model, settings, progress_cb, cancel_token) -> SimResult(t, signals)`.
- `sim.serialization`: `.esmodel` JSON with `schema_version` and migration functions.
- Validation sources: analytic step responses (1st/2nd order), integrator of constant, harmonic oscillator energy conservation.

## 9. Plotting
Interpreter plot commands build/modify `FigureSpec` held in the kernel session and send diffs/snapshots as `FigureUpdate`. `gui.plots` renders with PyQtGraph (interactive); `plotting.export` renders same spec with Matplotlib/Agg for PNG/SVG/PDF. 3D via PyVista in `gui.plots3d` (optional dependency, lazily imported).

## 10. Data and persistence
SQLite (`app.db`): settings, command history, recent projects, window layouts. Schema versioned with simple migration table. Projects: JSON manifest + folder. All paths via `core.paths` (supports portable mode if `portable.flag` next to exe).

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
- `multiprocessing.freeze_support()` at entry; kernel spawned with `spawn` start method.
- Installer: Inno Setup script → per-user install, Start Menu entry, `.m` and `.esmodel` association (optional).
- Docs shipped as local Markdown in `engstudio/app/docs_pages` (inside a known package so the layer test accepts it), rendered by `QTextBrowser`.
- Gate: smoke build + `--selftest` on a clean Windows VM without Python each phase; third-party license notices bundled.
- Optional heavy components (PyVista/VTK) can be split into a later "3D add-on" if size becomes a problem.

## 13. Decision log
| ID | Decision | Consequence |
|---|---|---|
| D1 | Python 3.14 (since 2026-11-28; 3.11 still works) | All pinned libraries have 3.14 wheels; tests and frozen build pass |
| D2 | Kernel in separate process | Serialization cost; robust Stop; workspace summaries only |
| D3 | Handwritten Pratt parser | Full control of MATLAB quirks; more code to test |
| D4 | Plot specs as data | GUI-agnostic plots; renderer parity tests needed |
| D5 | `control` is L1 library | `sim` and toolbox share it without layer violation |
| D6 | Explicit built-in toolbox list | Slight boilerplate; reliable freezing |
| D7 | JSON for projects/models, SQLite for app data | No TOML writer dependency |
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
