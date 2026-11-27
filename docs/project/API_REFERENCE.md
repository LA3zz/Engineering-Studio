# API_REFERENCE
Generated from the code by `tools/make_api_reference.py` for version 0.8.2.
Do not edit by hand: change the docstrings and run the script again.

Layer rules and the design behind these modules: ARCHITECTURE.md. Error types live in
`core.errors` (EngStudioError > ValidationError > DimensionError/UnitError;
SingularMatrixError, ConvergenceError, NotSupportedError, PluginError).

## app

### `engstudio.app`


### `engstudio.app.docs`

Local documentation service (G6.2): lists, reads and links Markdown pages.

- class `DocService(root: 'Path | str | None' = None) -> 'None'`: 
  - methods: names, exists, read, title, links, resolve
- `default_docs_root() -> 'Path'`: 
- `INDEX` (str)

### `engstudio.app.figure_export`

Figure export for the GUI. The GUI imports this, never ``plotting.export`` or Matplotlib; Matplotlib itself is only imported when a figure is actually saved.

- `EXPORT_FORMATS` (dict)
- `MATPLOTLIB_LOCK` (RLock)
- `draw_into(figure: 'object', spec: 'FigureSpec') -> 'None'`: Draw ``spec`` onto an empty Matplotlib ``Figure`` (the GUI's embedded canvas for 3-D,
- `load_matplotlib() -> 'None'`: Import Matplotlib's core once, under a lock. The kernel thread (export) and the GUI
- `save_figure(spec: 'FigureSpec', path: 'Path | str', dpi: 'int' = 150) -> 'Path'`: Write ``spec`` as PNG/SVG/PDF (chosen by the file suffix). Raises ``ValidationError``

### `engstudio.app.file_bindings`

Reading and writing lab data files (Phase 8): CSV, TXT/DAT and Excel.

- `file_functions(script_dir: 'Callable[[], Path | None] | None' = None, folder_changed: 'Callable[[str], None] | None' = None, write: 'Callable[[str], No...`: 

### `engstudio.app.function_help`

Help for every function: calling forms, summary, inputs, outputs and an example.

- class `FunctionHelp(name: 'str', signature: 'str', summary: 'str', text: 'str', params: 'tuple[str, ...]' = (), param_docs: 'tuple[str, ...]' = ()) -> None`: FunctionHelp(name: 'str', signature: 'str', summary: 'str', text: 'str', params: 'tuple[str, ...]' = (), param_docs: 'tuple[str, ...]' = ())
- `core_help(name: 'str') -> 'FunctionHelp | None'`: 
- `toolbox_help(spec, toolbox_title: 'str' = '') -> 'FunctionHelp'`: 
- `split_forms(signature: 'str') -> 'list[str]'`: ``"plot(y) | plot(x, y)"`` -> ``["plot(y)", "plot(x, y)"]`` (ignores ``|`` inside

### `engstudio.app.help_core`

One-line help for the core (non-toolbox) commands: calling forms and a summary.

- `CORE_HELP` (dict)

### `engstudio.app.help_toolbox`

What each toolbox function's inputs mean, plus a worked example per function.

- `ARG_DOCS` (dict)
- `EXAMPLES` (dict)
- `FIELD_DOCS` (dict)

### `engstudio.app.input_state`

Is Command Window input a complete statement, or does it need more lines? (K3)

- `needs_more(code: 'str') -> 'bool'`: True if ``code`` is an incomplete statement or block.

### `engstudio.app.kernel`

Kernel protocol and clients. The GUI talks to a ``KernelClient``; it never imports the engine.


### `engstudio.app.kernel.client`

Abstract kernel client: the only interface the GUI uses to run code.

- class `KernelClient() -> 'None'`: Send requests, receive events through subscribed handlers.
  - methods: subscribe, execute, cancel, shutdown, figure_closed, list_toolboxes

### `engstudio.app.kernel.inprocess`

Real kernel client that runs the interpreter in a worker thread of the GUI process (K1).

- class `InProcessKernelClient(threaded: 'bool' = True) -> 'None'`: 
  - methods: execute, cancel, shutdown, figure_closed, list_toolboxes, function_help
- `to_function_syntax(code: 'str') -> 'str'`: Rewrite command-style statements (``clear x y``, ``syms x; f = x^2``) as calls.

### `engstudio.app.kernel.protocol`

Kernel messages (versioned frozen dataclasses). Plain data only, safe to send over a pipe.

- class `Execute(request_id: 'int', code: 'str') -> None`: Execute(request_id: 'int', code: 'str')
- class `Cancel(request_id: 'int') -> None`: Cancel(request_id: 'int')
- class `Shutdown() -> None`: Shutdown()
- class `ListToolboxes(request_id: 'int') -> None`: ListToolboxes(request_id: 'int')
- class `Stdout(request_id: 'int', text: 'str') -> None`: Stdout(request_id: 'int', text: 'str')
- class `Diagnostics(request_id: 'int', items: 'tuple[Diagnostic, ...]') -> None`: Diagnostics(request_id: 'int', items: 'tuple[Diagnostic, ...]')
- class `VariableInfo(name: 'str', cls: 'str', size: 'tuple[int, ...]', preview: 'str') -> None`: Summary of one workspace variable. Never carries the full array.
- class `WorkspaceSummary(request_id: 'int', variables: 'tuple[VariableInfo, ...]') -> None`: WorkspaceSummary(request_id: 'int', variables: 'tuple[VariableInfo, ...]')
- class `ExecutionFinished(request_id: 'int', status: 'ExecStatus') -> None`: ExecutionFinished(request_id: 'int', status: 'ExecStatus')
- class `ToolboxFunction(name: 'str', summary: 'str', signature: 'str' = '', help: 'str' = '', params: 'tuple[str, ...]' = (), param_docs: 'tuple[str, ...]' = ()...`: One function listed in a toolbox. Plain data (no callable).
- class `ToolboxInfo(name: 'str', display_name: 'str', functions: 'tuple[ToolboxFunction, ...]') -> None`: ToolboxInfo(name: 'str', display_name: 'str', functions: 'tuple[ToolboxFunction, ...]')
- class `ToolboxList(request_id: 'int', toolboxes: 'tuple[ToolboxInfo, ...]') -> None`: ToolboxList(request_id: 'int', toolboxes: 'tuple[ToolboxInfo, ...]')
- class `FigureUpdate(request_id: 'int', figure: 'FigureSpec') -> None`: Full snapshot of one figure (the GUI creates or replaces its window).
- class `FigureClosed(request_id: 'int', number: 'int') -> None`: The script closed figure ``number`` (the GUI closes its window).
- class `OpenModel(request_id: 'int', path: 'str') -> None`: The script asked to open a simulation model (``open_system``) in the editor.
- class `FolderChanged(request_id: 'int', path: 'str') -> None`: The script changed the working folder (``cd``); the Current Folder panel follows.

### `engstudio.app.kernel.stub`

Stub kernel for GUI development. NOT an interpreter.

- `demo_figure(number: 'int' = 1) -> 'FigureSpec'`: Small figure for developing the Figure window (sample data, not a result).
- `format_double(v: 'float') -> 'str'`: Short display format: integers plain, otherwise 4 decimals (or exponent form).
- class `StubKernelClient() -> 'None'`: 
  - methods: cancel, shutdown, list_toolboxes, execute

### `engstudio.app.sim_bindings`

Simulation commands for scripts (Phase 7, S12): ``sim`` and ``open_system``.

- `sim_functions(interp: 'Interpreter', manager: 'FigureManager', open_model: 'Callable[[str], None]', script_dir: 'Callable[[], Path | None] | None' = N...`: 

### `engstudio.app.sim_service`

Simulation services for the model editor (Phase 7, S13-S16).

- class `BlockInfo(name: 'str', category: 'str', doc: 'str', params: 'tuple[ParamInfo, ...]') -> None`: BlockInfo(name: 'str', category: 'str', doc: 'str', params: 'tuple[ParamInfo, ...]')
- class `ParamInfo(name: 'str', kind: 'str', default_text: 'str', choices: 'tuple[str, ...]', doc: 'str') -> None`: ParamInfo(name: 'str', kind: 'str', default_text: 'str', choices: 'tuple[str, ...]', doc: 'str')
- `catalog() -> 'list[BlockInfo]'`: Every block type, sorted by category then name (Subsystem ports excluded).
- `check_block(block: 'Block') -> 'None'`: Raise ValidationError if the block's parameters are invalid.
- `format_param(value: 'object') -> 'str'`: 
- `parse_param(kind: 'str', text: 'str') -> 'object'`: Text typed in a parameter dialog -> model value for a parameter of ``kind``.
- `ports_of(block: 'Block') -> 'tuple[int, int]'`: 
- `run_model(model: 'Model', progress: 'Callable[[float], None] | None' = None, should_stop: 'Callable[[], bool] | None' = None) -> 'SimResult'`: 
- `scope_figures(result: 'SimResult', first_number: 'int' = 1001) -> 'list[FigureSpec]'`: One figure per Scope (lines per input/element, legend when several).

### `engstudio.app.syntax`

Language facts the GUI needs for syntax highlighting, without the GUI importing ``lang``.

- `SYNTAX_KEYWORDS` (frozenset)

### `engstudio.app.toolbox_bindings`

Make toolbox functions callable from scripts (Phase 8).

- `load_toolboxes() -> 'list[tuple[str, str, tuple[FunctionSpec, ...]]]'`: [(name, display name, function specs)] for every built-in toolbox.
- `to_value(x: 'object') -> 'object'`: Python result -> interpreter value.
- `toolbox_builtins() -> 'tuple[dict[str, Builtin], dict[str, tuple[str, tuple[str, ...]]]]'`: (builtins by name, toolbox categories {key: (display name, function names)}).

### `engstudio.app.workspace_files`

Save and load workspace variables in MATLAB's ``.mat`` format (``save``, ``load``).

- `workspace_file_functions(interp: 'Interpreter', write: 'Callable[[str], None]', script_dir: 'Callable[[], Path | None] | None' = None) -> 'dict[str, Builtin]'`: 

## control

### `engstudio.control`


### `engstudio.control.lti`

Linear time-invariant systems (Phase 6, C1): pure engine layer, no GUI, no interpreter.

- class `LtiSystem(form: 'str', data: 'tuple', dt: 'float' = 0.0) -> None`: ``form`` 'tf': data = (num, den); 'zpk': (z, p, k); 'ss': (A, B, C, D).
  - methods: to_control
- class `PidInfo(kind: 'str', kp: 'float', ki: 'float', kd: 'float', tf: 'float', crossover: 'float', phase_margin: 'float', stable: 'bool') -> None`: PidInfo(kind: 'str', kp: 'float', ki: 'float', kd: 'float', tf: 'float', crossover: 'float', phase_margin: 'float', stable: 'bool')
- class `StepInfo(rise_time: 'float', settling_time: 'float', settling_min: 'float', settling_max: 'float', overshoot: 'float', undershoot: 'float', peak:...`: StepInfo(rise_time: 'float', settling_time: 'float', settling_min: 'float', settling_max: 'float', overshoot: 'float', undershoot: 'float', peak: 'float', peak_time: 'float')
- `bode(sys: 'LtiSystem', w: 'object' = None) -> 'tuple[np.ndarray, np.ndarray, np.ndarray]'`: (magnitude (absolute), phase (degrees, unwrapped), w (rad/s)).
- `c2d(sys: 'LtiSystem', ts: 'float', method: 'str' = 'zoh') -> 'LtiSystem'`: 
- `damp(sys: 'LtiSystem') -> 'tuple[np.ndarray, np.ndarray, np.ndarray]'`: (natural frequencies, damping ratios, poles), sorted by frequency as MATLAB.
- `dcgain(sys: 'LtiSystem') -> 'np.ndarray | float'`: 
- `feedback(g: 'object', h: 'object' = 1.0, sign: 'int' = -1) -> 'LtiSystem'`: Closed loop g / (1 - sign*g*h); ``sign`` -1 (default) is negative feedback.
- `impulse(sys: 'LtiSystem', t: 'object' = None) -> 'tuple[np.ndarray, np.ndarray]'`: 
- `initial(sys: 'LtiSystem', x0: 'object', t: 'object' = None) -> 'tuple[np.ndarray, np.ndarray]'`: 
- `is_stable(sys: 'LtiSystem') -> 'bool'`: 
- `lsim(sys: 'LtiSystem', u: 'object', t: 'object', x0: 'object' = None) -> 'tuple[np.ndarray, np.ndarray]'`: Response to input samples ``u`` at times ``t`` (zero-order hold between samples).
- `margin(sys: 'LtiSystem') -> 'tuple[float, float, float, float]'`: (gain margin (absolute), phase margin (deg), w at phase -180, w at gain 1);
- `nyquist(sys: 'LtiSystem', w: 'object' = None) -> 'tuple[np.ndarray, np.ndarray, np.ndarray]'`: (real part, imaginary part, w) of G(jw) for positive w.
- `parallel(a: 'object', b: 'object') -> 'LtiSystem'`: 
- `pid(kp: 'float' = 1.0, ki: 'float' = 0.0, kd: 'float' = 0.0, tf_: 'float' = 0.0, dt: 'float' = 0.0) -> 'LtiSystem'`: Parallel PID C(s) = Kp + Ki/s + Kd s / (Tf s + 1) as a transfer function.
- `pidstd(kp: 'float' = 1.0, ti: 'float' = inf, td: 'float' = 0.0, n: 'float' = inf) -> 'LtiSystem'`: Standard form Kp (1 + 1/(Ti s) + Td s / (Td/N s + 1)).
- `pidtune(plant: 'LtiSystem', kind: 'str' = 'PID', wc: 'float | None' = None, phase_margin: 'float' = 60.0) -> 'tuple[LtiSystem, PidInfo]'`: Tune a P, PI, PD or PID controller for ``plant`` by loop shaping: open-loop gain 1 and
- `poles(sys: 'LtiSystem') -> 'np.ndarray'`: 
- `rlocus(sys: 'LtiSystem', gains: 'object' = None) -> 'tuple[np.ndarray, np.ndarray]'`: (closed-loop roots, one row per gain; gains) of 1 + k*G = 0.
- `series(a: 'object', b: 'object') -> 'LtiSystem'`: b * a (a first, then b), as MATLAB's series(a, b).
- `ss(a: 'object', b: 'object', c: 'object', d: 'object', dt: 'float' = 0.0) -> 'LtiSystem'`: 
- `step(sys: 'LtiSystem', t: 'object' = None) -> 'tuple[np.ndarray, np.ndarray]'`: (t, y) of the unit step response.
- `stepinfo(sys: 'LtiSystem', settling: 'float' = 0.02, rise: 'tuple[float, float]' = (0.1, 0.9)) -> 'StepInfo'`: 
- `tf(num: 'object', den: 'object', dt: 'float' = 0.0) -> 'LtiSystem'`: 
- `to_ss(sys: 'LtiSystem') -> 'LtiSystem'`: 
- `to_tf(sys: 'LtiSystem') -> 'LtiSystem'`: 
- `to_zpk(sys: 'LtiSystem') -> 'LtiSystem'`: 
- `zeros(sys: 'LtiSystem') -> 'np.ndarray'`: 
- `zpk(z: 'object', p: 'object', k: 'float', dt: 'float' = 0.0) -> 'LtiSystem'`: 

## core

### `engstudio.core`


### `engstudio.core.diagnostics`

Structured diagnostics: messages as data, never printed or raised implicitly.

- class `SourceLoc(file: 'str | None' = None, line: 'int | None' = None, col: 'int | None' = None) -> None`: Position in a source file. Lines and columns are 1-based.
- class `Diagnostic(severity: 'Severity', code: 'str', message: 'str', location: 'SourceLoc | None' = None) -> None`: Diagnostic(severity: 'Severity', code: 'str', message: 'str', location: 'SourceLoc | None' = None)
- `info(code: 'str', message: 'str', location: 'SourceLoc | None' = None) -> 'Diagnostic'`: 
- `warning(code: 'str', message: 'str', location: 'SourceLoc | None' = None) -> 'Diagnostic'`: 
- `error(code: 'str', message: 'str', location: 'SourceLoc | None' = None) -> 'Diagnostic'`: 

### `engstudio.core.errors`

Typed error hierarchy. Every error has a stable machine-readable ``code``.

- class `EngStudioError(...)`: Base class for all errors raised by Engineering Studio.
  - methods: to_diagnostic
- class `ValidationError(...)`: Invalid input value or type.
- class `DimensionError(...)`: Array shapes are incompatible for the requested operation.
- class `UnitError(...)`: Unknown or incompatible unit.
- class `SingularMatrixError(message: 'str' = 'Matrix is singular to working precision', rcond: 'float | None' = None) -> 'None'`: Matrix is singular to working precision.
- class `ConvergenceError(message: 'str', iterations: 'int | None' = None, last_estimate: 'object | None' = None) -> 'None'`: An iterative method failed to converge.
- class `NotSupportedError(...)`: Feature is outside the documented supported subset.
- class `PluginError(...)`: Invalid toolbox/plugin definition or registration.

### `engstudio.core.plugin`

Plugin API: toolbox function decorator with input validation, block metadata, manifests.

- class `Arg(name: 'str', unit: 'str | None' = None, shape: 'tuple[int | None, ...] | None' = None, positive: 'bool' = False, nonnegative: 'bool' = F...`: Declaration and validation rules for one function argument.
- class `Ret(name: 'str', unit: 'str | None' = None, doc: 'str' = '') -> None`: Documentation of one return value.
- class `FunctionSpec(name: 'str', category: 'str', args: 'tuple[Arg, ...]', returns: 'tuple[Ret, ...]', doc: 'str', summary: 'str', func: 'Callable[..., Any]...`: FunctionSpec(name: 'str', category: 'str', args: 'tuple[Arg, ...]', returns: 'tuple[Ret, ...]', doc: 'str', summary: 'str', func: 'Callable[..., Any]', toolbox: 'str | None' = None)
- class `BlockSpec(name: 'str', category: 'str', cls: 'type', doc: 'str' = '', toolbox: 'str | None' = None) -> None`: Minimal block metadata; ports and parameters are defined with the simulation engine.
- `tb_function(name: 'str', category: 'str', args: 'tuple[Arg, ...] | list[Arg]' = (), returns: 'tuple[Ret, ...] | list[Ret]' = (), doc: 'str' = '') ->...`: Declare a toolbox function (see module docstring).
- `sim_block(name: 'str', category: 'str', doc: 'str' = '') -> 'Callable[[type], type]'`: Declare a simulation block class (metadata only until the simulation engine exists).
- class `ToolboxManifest(name: 'str', display_name: 'str', version: 'str', api_version: 'int', category: 'str') -> None`: ToolboxManifest(name: 'str', display_name: 'str', version: 'str', api_version: 'int', category: 'str')
  - methods: compatibility_diagnostic
- `parse_manifest(text: 'str', source: 'str' = '<string>') -> 'ToolboxManifest'`: 
- `load_manifest(path: 'str | Path') -> 'ToolboxManifest'`: 

### `engstudio.core.registry`

Registry of toolbox functions and simulation blocks.

- class `Registry() -> 'None'`: 
  - methods: add_function, add_block, register_module, remove_toolbox, find_function, get_function, call, functions, get_block, blocks

### `engstudio.core.units`

Explicit unit conversion. SI is the base system; nothing is converted implicitly.

- `convert(value, from_unit: 'str', to_unit: 'str')`: Convert a number or array between compatible units.
- `conversion_factor(from_unit: 'str', to_unit: 'str') -> 'float'`: Multiplicative factor; not defined for offset temperature scales.
- `dimension_of(unit: 'str') -> 'Dim'`: Exponents of (m, kg, s, A, K, mol, cd, rad) for a unit expression.
- `is_compatible(unit_a: 'str', unit_b: 'str') -> 'bool'`: 
- `format_dimension(dim: 'Dim') -> 'str'`: 
- `known_units() -> 'list[str]'`: 

## data

### `engstudio.data`


## engine

### `engstudio.engine`


### `engstudio.engine.calculus`

Numerical differentiation and integration (E3).

- class `IntegrateResult(value: 'float', error_estimate: 'float', nfev: 'int', converged: 'bool', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`: IntegrateResult(value: 'float', error_estimate: 'float', nfev: 'int', converged: 'bool', diagnostics: 'tuple[Diagnostic, ...]' = ())
- `cumtrapz(y: 'ArrayLike', x: 'ArrayLike | None' = None, dx: 'float' = 1.0) -> 'NDArray'`: Cumulative trapezoidal integral; same length as ``y``, first value 0.
- `derivative(f: 'Callable[[float], float]', x: 'float', *, order: 'int' = 1, h: 'float | None' = None, method: 'str' = 'central') -> 'float'`: First or second derivative of scalar ``f`` at ``x`` by finite differences.
- `derivative_data(x: 'ArrayLike', y: 'ArrayLike') -> 'NDArray'`: Derivative of sampled data: second-order accurate, including edges and uneven spacing.
- `dblquad(f: 'Callable[[float, float], float]', x0: 'float', x1: 'float', y0: 'float', y1: 'float', *, rtol: 'float' = 1.49e-08, atol: 'float' = 1...`: Integral of ``f(x, y)`` over the rectangle [x0, x1] x [y0, y1] (finite limits).
- `gradient(f: 'Callable[[NDArray], float]', x: 'ArrayLike') -> 'NDArray'`: Gradient of scalar ``f(x)`` (x a 1-D array) by central differences.
- `jacobian(f: 'Callable[[NDArray], ArrayLike]', x: 'ArrayLike') -> 'NDArray'`: Jacobian (m x n) of vector function ``f: R^n -> R^m`` by central differences.
- `quad(f: 'Callable[[float], float]', a: 'float', b: 'float', *, rtol: 'float' = 1.49e-08, atol: 'float' = 1.49e-08, limit: 'int' = 200) -> 'In...`: Adaptive integral of scalar ``f`` over [a, b]; limits may be +-inf.
- `simpson(y: 'ArrayLike', x: 'ArrayLike | None' = None, dx: 'float' = 1.0) -> 'float'`: Simpson's rule (SciPy's handling of an even number of samples).
- `trapz(y: 'ArrayLike', x: 'ArrayLike | None' = None, dx: 'float' = 1.0) -> 'float'`: Trapezoidal rule; ``x`` optional (then uniform spacing ``dx``).

### `engstudio.engine.decomp`

Matrix decompositions and eigenproblems (E2), built on LAPACK through NumPy/SciPy.

- class `CholResult(factor: 'NDArray', lower: 'bool') -> None`: ``factor`` is upper ``R`` with ``R^H R = A`` (or lower ``L`` with ``L L^H = A``).
- class `EigResult(values: 'NDArray', vectors: 'NDArray', residual: 'float', vector_rcond: 'float', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`: EigResult(values: 'NDArray', vectors: 'NDArray', residual: 'float', vector_rcond: 'float', diagnostics: 'tuple[Diagnostic, ...]' = ())
- class `LuResult(P: 'NDArray', L: 'NDArray', U: 'NDArray') -> None`: ``P @ A = L @ U`` with partial pivoting; works for rectangular ``A`` too.
- class `QrResult(Q: 'NDArray', R: 'NDArray', mode: 'str') -> None`: QrResult(Q: 'NDArray', R: 'NDArray', mode: 'str')
- class `SvdResult(U: 'NDArray', s: 'NDArray', V: 'NDArray') -> None`: ``A = U @ diag(s) @ V^H``; ``s`` is descending and non-negative.
- `cholesky(a: 'ArrayLike', lower: 'bool' = False, tol: 'float' = 1e-12) -> 'CholResult'`: Cholesky factor of a Hermitian positive-definite matrix.
- `eig(a: 'ArrayLike') -> 'EigResult'`: Eigenvalues and right eigenvectors of a general square matrix.
- `eigh(a: 'ArrayLike', tol: 'float' = 1e-12) -> 'EigResult'`: Eigenvalues (real, ascending) and orthonormal eigenvectors of a Hermitian matrix.
- `lu(a: 'ArrayLike') -> 'LuResult'`: 
- `qr(a: 'ArrayLike', mode: 'str' = 'full') -> 'QrResult'`: QR by Householder reflections; ``mode`` is ``'full'`` or ``'economic'``.
- `svd(a: 'ArrayLike', full: 'bool' = False) -> 'SvdResult'`: Singular value decomposition; ``full=False`` gives the economy-size factors.
- `DEFECTIVE_RCOND` (float)
- `HERMITIAN_TOL` (float)

### `engstudio.engine.interp`

Interpolation of sampled data (E5).

- `interp1(x: 'ArrayLike', y: 'ArrayLike', xq: 'ArrayLike', *, method: 'str' = 'linear', extrap: 'str' = 'error') -> 'float | NDArray'`: Interpolate samples ``(x, y)`` at the query points ``xq``.
- `interp2(x: 'ArrayLike', y: 'ArrayLike', z: 'ArrayLike', xq: 'ArrayLike', yq: 'ArrayLike', *, method: 'str' = 'linear', extrap: 'str' = 'error') ...`: Interpolate ``z[j, i] = f(x[i], y[j])`` at the point pairs ``(xq, yq)``.

### `engstudio.engine.linalg`

Dense linear algebra with validation, conditioning checks and typed errors (E1).

- class `InvResult(value: 'NDArray', rcond: 'float', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`: InvResult(value: 'NDArray', rcond: 'float', diagnostics: 'tuple[Diagnostic, ...]' = ())
- class `SolveResult(x: 'NDArray', residual_norm: 'float', rcond: 'float', method: 'str', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`: SolveResult(x: 'NDArray', residual_norm: 'float', rcond: 'float', method: 'str', diagnostics: 'tuple[Diagnostic, ...]' = ())
- `cond(a: 'ArrayLike', p: 'float | str' = 2) -> 'float'`: Condition number in the 1, 2, inf or Frobenius norm; ``inf`` if (numerically) singular.
- `cross(a: 'ArrayLike', b: 'ArrayLike') -> 'NDArray'`: 
- `det(a: 'ArrayLike') -> 'float | complex'`: 
- `dot(a: 'ArrayLike', b: 'ArrayLike') -> 'float | complex'`: sum(conj(a) * b) for equal-length vectors (MATLAB ``dot`` convention).
- `inv(a: 'ArrayLike') -> 'InvResult'`: Matrix inverse with conditioning check.
- `matmul(a: 'ArrayLike', b: 'ArrayLike') -> 'NDArray'`: 
- `norm(x: 'ArrayLike', kind: 'float | str' = 2) -> 'float'`: Vector norm (1, 2, inf or p >= 1) or matrix norm (1, 2, inf or 'fro').
- `rank(a: 'ArrayLike', tol: 'float | None' = None) -> 'int'`: Numerical rank from singular values; default tol = max(m, n) * eps * smax.
- `rcond(a: 'ArrayLike') -> 'float'`: Reciprocal condition number in the 1-norm (0 for a singular matrix).
- `solve(a: 'ArrayLike', b: 'ArrayLike') -> 'SolveResult'`: Solve ``a @ x = b`` for square ``a`` (LU with partial pivoting, LAPACK gesv).
- `trace(a: 'ArrayLike') -> 'float | complex'`: 
- `transpose(a: 'ArrayLike') -> 'NDArray'`: 
- `ctranspose(a: 'ArrayLike') -> 'NDArray'`: Conjugate transpose.
- `ILL_CONDITIONED_RCOND` (float)

### `engstudio.engine.ode`

Ordinary differential equations: initial value problems (E9).

- `METHODS` (tuple)
- class `OdeResult(t: 'NDArray', y: 'NDArray', status: 'int', nfev: 'int', diagnostics: 'tuple[Diagnostic, ...]' = (), method: 'str' = '', message: 'str' =...`: OdeResult(t: 'NDArray', y: 'NDArray', status: 'int', nfev: 'int', diagnostics: 'tuple[Diagnostic, ...]' = (), method: 'str' = '', message: 'str' = '', t_events: 'tuple[NDArray, ...]' = (), y_events: 'tuple[NDArray, ...]' = ())
- `solve_ode(f: 'Callable[[float, NDArray], ArrayLike]', t_span: 'ArrayLike', y0: 'ArrayLike', *, method: 'str' = 'RK45', rtol: 'float' = 1e-06, atol...`: Solve dy/dt = f(t, y), y(t0) = y0 over ``t_span = (t0, t1)``.

### `engstudio.engine.optimize`

Numerical optimization (E7).

- class `MinimizeResult(x: 'float | NDArray', fun: 'float', converged: 'bool', iterations: 'int', nfev: 'int', diagnostics: 'tuple[Diagnostic, ...]' = (), metho...`: MinimizeResult(x: 'float | NDArray', fun: 'float', converged: 'bool', iterations: 'int', nfev: 'int', diagnostics: 'tuple[Diagnostic, ...]' = (), method: 'str' = '')
- `linprog(c: 'ArrayLike', A_ub: 'ArrayLike | None' = None, b_ub: 'ArrayLike | None' = None, A_eq: 'ArrayLike | None' = None, b_eq: 'ArrayLike | No...`: Minimize ``c @ x`` s.t. ``A_ub @ x <= b_ub``, ``A_eq @ x == b_eq``, bounds (HiGHS).
- `minimize(f: 'Callable[[NDArray], float]', x0: 'ArrayLike', *, jac: 'Callable[[NDArray], ArrayLike] | None' = None, bounds: 'Sequence[tuple[float ...`: Minimize ``f(x)`` (x a 1-D array) starting at ``x0``.
- `minimize_scalar(f: 'Callable[[float], float]', a: 'float', b: 'float', *, xtol: 'float' = 1e-10, maxiter: 'int' = 500) -> 'MinimizeResult'`: Local minimum of scalar ``f`` on [a, b] (bounded Brent: golden section + parabolas).

### `engstudio.engine.regression`

Regression and curve fitting (E6).

- class `FitResult(params: 'NDArray', covariance: 'NDArray', residuals: 'NDArray', r_squared: 'float', diagnostics: 'tuple[Diagnostic, ...]' = (), stderr: ...`: FitResult(params: 'NDArray', covariance: 'NDArray', residuals: 'NDArray', r_squared: 'float', diagnostics: 'tuple[Diagnostic, ...]' = (), stderr: 'NDArray | None' = None, dof: 'int' = 0, method: 'str' = '', nfev: 'int' = 0)
- `confidence_intervals(result: 'FitResult', level: 'float' = 0.95) -> 'NDArray'`: Two-sided Student-t confidence intervals, shape (p, 2): ``params -/+ t * stderr``.
- `fit_curve(f: 'Callable[..., ArrayLike]', x: 'ArrayLike', y: 'ArrayLike', p0: 'ArrayLike', *, sigma: 'ArrayLike | None' = None, absolute_sigma: 'bo...`: Fit ``y ~ f(x, *params)`` by nonlinear least squares starting at ``p0``.
- `linfit(A: 'ArrayLike', y: 'ArrayLike', *, weights: 'ArrayLike | None' = None) -> 'FitResult'`: Least-squares solution of ``y ~ A @ beta`` (columns of ``A`` are the basis functions).
- `polyfit(x: 'ArrayLike', y: 'ArrayLike', deg: 'int', *, weights: 'ArrayLike | None' = None) -> 'FitResult'`: Fit a polynomial of degree ``deg``; ``params`` are highest power first.
- `polyval(p: 'ArrayLike', x: 'ArrayLike') -> 'float | NDArray'`: Evaluate a polynomial (highest power first); scalar in, float out.

### `engstudio.engine.roots`

Root finding and equation solving (E4).

- class `RootResult(root: 'float | NDArray', converged: 'bool', iterations: 'int', residual: 'float', diagnostics: 'tuple[Diagnostic, ...]' = (), method: 's...`: ``root`` is a float (scalar methods), a vector (``fsolve``) or complex roots (poly).
- `bisect(f: 'Callable[[float], float]', a: 'float', b: 'float', *, rtol: 'float' = 1e-12, atol: 'float' = 1e-14, maxiter: 'int' = 200) -> 'RootRe...`: Bisection on [a, b]; requires f(a) and f(b) of opposite sign (or an exact zero).
- `brentq(f: 'Callable[[float], float]', a: 'float', b: 'float', *, rtol: 'float' = 1e-12, atol: 'float' = 1e-14, maxiter: 'int' = 100) -> 'RootRe...`: Brent's method (SciPy ``brentq``) on a sign-changing bracket [a, b].
- `fsolve(f: 'Callable[[NDArray], ArrayLike]', x0: 'ArrayLike', *, jac: 'Callable[[NDArray], ArrayLike] | None' = None, rtol: 'float' = 1e-10, ato...`: Solve ``f(x) = 0`` for ``f: R^n -> R^n`` by damped Newton (backtracking on ||f||).
- `newton(f: 'Callable[[float], float]', x0: 'float', *, fprime: 'Callable[[float], float] | None' = None, rtol: 'float' = 1e-12, atol: 'float' = ...`: Newton's method. Without ``fprime`` a central-difference derivative is used.
- `polyroots(coeffs: 'ArrayLike') -> 'RootResult'`: All roots of ``c[0]*x^n + ... + c[n]`` (highest power first, real or complex coeffs).
- `secant(f: 'Callable[[float], float]', x0: 'float', x1: 'float', *, rtol: 'float' = 1e-12, atol: 'float' = 1e-14, maxiter: 'int' = 100) -> 'Root...`: Secant method from two distinct starting points.

### `engstudio.engine.stats`

Descriptive statistics, correlation, confidence intervals and t-tests (E8).

- class `CorrResult(r: 'float', p_value: 'float', n: 'int') -> None`: CorrResult(r: 'float', p_value: 'float', n: 'int')
- class `Summary(n: 'int', mean: 'float', std: 'float', sem: 'float', min: 'float', q1: 'float', median: 'float', q3: 'float', max: 'float') -> None`: Summary(n: 'int', mean: 'float', std: 'float', sem: 'float', min: 'float', q1: 'float', median: 'float', q3: 'float', max: 'float')
- class `TestResult(statistic: 'float', p_value: 'float', dof: 'float', diagnostics: 'tuple[Diagnostic, ...]' = (), method: 'str' = '') -> None`: TestResult(statistic: 'float', p_value: 'float', dof: 'float', diagnostics: 'tuple[Diagnostic, ...]' = (), method: 'str' = '')
- `confidence_interval_mean(x: 'ArrayLike', level: 'float' = 0.95) -> 'tuple[float, float, float]'`: ``(mean, lower, upper)``: Student-t interval for the population mean.
- `cov(x: 'ArrayLike', y: 'ArrayLike', ddof: 'int' = 1) -> 'float'`: 
- `histogram(x: 'ArrayLike', bins: 'int | ArrayLike' = 10, *, range_: 'tuple[float, float] | None' = None) -> 'tuple[NDArray, NDArray]'`: Counts and bin edges; the last bin includes its right edge. ``bins``: count or edges.
- `iqr(x: 'ArrayLike', *, method: 'str' = 'linear') -> 'float'`: 
- `kurtosis(x: 'ArrayLike') -> 'float'`: Biased, non-excess kurtosis (a normal distribution has 3).
- `mean(x: 'ArrayLike') -> 'float'`: 
- `median(x: 'ArrayLike') -> 'float'`: 
- `pearsonr(x: 'ArrayLike', y: 'ArrayLike') -> 'CorrResult'`: Pearson correlation coefficient with a two-sided p-value (H0: rho = 0, n >= 3).
- `quantile(x: 'ArrayLike', q: 'ArrayLike', *, method: 'str' = 'linear') -> 'float | NDArray'`: Quantile(s) ``q`` in [0, 1]; scalar ``q`` returns a float.
- `rms(x: 'ArrayLike') -> 'float'`: 
- `sem(x: 'ArrayLike') -> 'float'`: Standard error of the mean, ``s / sqrt(n)`` with the sample standard deviation.
- `skewness(x: 'ArrayLike') -> 'float'`: 
- `std(x: 'ArrayLike', ddof: 'int' = 1) -> 'float'`: 
- `summary(x: 'ArrayLike') -> 'Summary'`: 
- `t_quantile(p: 'float', dof: 'float') -> 'float'`: Student-t quantile (inverse CDF) for probability ``p`` in (0, 1) and ``dof`` > 0.
- `ttest_1samp(x: 'ArrayLike', popmean: 'float' = 0.0, *, alternative: 'str' = 'two-sided') -> 'TestResult'`: One-sample t-test of ``mean(x) == popmean``.
- `ttest_ind(x: 'ArrayLike', y: 'ArrayLike', *, equal_var: 'bool' = False, alternative: 'str' = 'two-sided') -> 'TestResult'`: Two-sample t-test (Welch by default; pooled variance if ``equal_var=True``).
- `ttest_paired(x: 'ArrayLike', y: 'ArrayLike', *, alternative: 'str' = 'two-sided') -> 'TestResult'`: Paired t-test on the differences ``x - y``.
- `var(x: 'ArrayLike', ddof: 'int' = 1) -> 'float'`: 
- `zscore(x: 'ArrayLike', ddof: 'int' = 1) -> 'NDArray'`: 

### `engstudio.engine.symbolic`

Symbolic mathematics on top of SymPy (E11).

- `CONSTANTS` (tuple)
- `FUNCTIONS` (tuple)
- class `SymExpr(expr: 'sp.Basic') -> None`: Immutable wrapper around a SymPy expression.
  - methods: latex
- `diff(expr: 'SymExpr | str', var: 'SymExpr | str', order: 'int' = 1) -> 'SymExpr'`: Derivative of ``expr`` with respect to ``var`` (``order`` 1..50).
- `equivalent(a: 'SymExpr | str', b: 'SymExpr | str') -> 'bool'`: True if ``simplify(a - b)`` is exactly zero. False means 'not shown equal'.
- `expand(expr: 'SymExpr | str') -> 'SymExpr'`: 
- `factor(expr: 'SymExpr | str') -> 'SymExpr'`: 
- `integrate(expr: 'SymExpr | str', var: 'SymExpr | str', a: 'object' = None, b: 'object' = None, *, allow_conditional: 'bool' = False) -> 'SymExpr'`: Indefinite integral (no constant of integration) or definite integral from a to b.
- `inverse_laplace(expr: 'SymExpr | str', s: 'SymExpr | str', t: 'SymExpr | str') -> 'SymExpr'`: Inverse Laplace transform f(t) of F(s), valid for t > 0 (Heaviside(t) removed).
- `lambdify(expr: 'SymExpr | str', variables: 'Sequence[str]') -> 'Callable'`: NumPy-vectorised function of ``variables`` (in that order). Constants return scalars.
- `laplace(expr: 'SymExpr | str', t: 'SymExpr | str', s: 'SymExpr | str') -> 'SymExpr'`: One-sided Laplace transform F(s) of f(t) (convergence conditions are not returned).
- `limit(expr: 'SymExpr | str', var: 'SymExpr | str', point: 'object', *, direction: 'str' = '+-') -> 'SymExpr'`: Limit as ``var`` approaches ``point`` (number, ``"oo"``, ``"-oo"``).
- `parse(text: 'str') -> 'SymExpr'`: Parse text into a ``SymExpr`` (see the module docstring for the accepted grammar).
- `series(expr: 'SymExpr | str', var: 'SymExpr | str', point: 'object' = 0, n: 'int' = 6) -> 'SymExpr'`: Taylor/Laurent polynomial around ``point`` with terms of order below ``n`` (1..50).
- `simplify(expr: 'SymExpr | str') -> 'SymExpr'`: 
- `solve(equation: 'SymExpr | str', var: 'SymExpr | str', *, domain: 'str' = 'complex') -> 'tuple[SymExpr, ...]'`: All distinct solutions of ``equation`` (text with one ``=``, or an expression = 0).
- `to_matlab_code(x: 'SymExpr | str') -> 'str'`: Element-wise MATLAB code for an expression (``.^``, ``.*``, ``./``), as matlabFunction
- `solve_system(equations: 'Sequence[SymExpr | str]', variables: 'Sequence[SymExpr | str]') -> 'tuple[dict[str, SymExpr], ...]'`: Solutions of simultaneous equations as dicts name -> value (each checked by substitution).
- `subs(expr: 'SymExpr | str', mapping: 'Mapping[str, object]') -> 'SymExpr'`: Substitute symbols simultaneously; values may be numbers, text or ``SymExpr``.
- `to_numeric(expr: 'SymExpr | str', values: 'Mapping[str, object] | None' = None) -> 'float | complex'`: Evaluate to a Python float (or complex if the value is not real). All symbols need values.
- `apply_function(name: 'str', x: 'object') -> 'SymExpr'`: Apply one of ``FUNCTIONS`` (sin, exp, sqrt, ...) to an expression.
- `arith(op: 'str', a: 'object', b: 'object') -> 'SymExpr'`: ``a op b`` for op in ``+ - * / ^``; division by zero, huge exponents and undefined
- `as_symexpr(x: 'object') -> 'SymExpr'`: ``SymExpr`` from a ``SymExpr``, text or a number.
- `default_variable(expr: 'object') -> 'str'`: Default variable: the only symbol, else the one closest to 'x' (later letter on ties);
- `equation(a: 'object', b: 'object') -> 'SymExpr'`: The equation ``a == b`` as a ``SymExpr`` (use ``residual_form`` before solving).
- `is_symbol(x: 'object') -> 'bool'`: 
- `negate(a: 'object') -> 'SymExpr'`: 
- `residual_form(x: 'object') -> 'SymExpr'`: ``lhs - rhs`` of an equation (text with one ``=`` or an equation object); an expression
- `symbol(name: 'str') -> 'SymExpr'`: A plain symbol (reserved function/constant names are rejected).
- `to_text(x: 'SymExpr') -> 'str'`: MATLAB-style text: ``^`` for powers, ``lhs == rhs`` for equations.

### `engstudio.engine.transforms`

Fourier transforms, spectra, convolution and Butterworth filtering (E10).

- class `SpectrumResult(freq: 'NDArray', values: 'NDArray', kind: 'str', window: 'str', fs: 'float', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`: SpectrumResult(freq: 'NDArray', values: 'NDArray', kind: 'str', window: 'str', fs: 'float', diagnostics: 'tuple[Diagnostic, ...]' = ())
- `WINDOWS` (tuple)
- `amplitude_spectrum(x: 'ArrayLike', fs: 'float', *, window: 'str' = 'rect', n: 'int | None' = None) -> 'SpectrumResult'`: Single-sided amplitude spectrum of a real signal sampled at ``fs`` Hz.
- `butter_filter(x: 'ArrayLike', fs: 'float', cutoff: 'float | ArrayLike', *, btype: 'str' = 'low', order: 'int' = 4, zero_phase: 'bool' = True) -> 'NDAr...`: Butterworth filter of a real signal. ``band``/``bandstop`` take ``(low, high)`` in Hz.
- `convolve(a: 'ArrayLike', b: 'ArrayLike', mode: 'str' = 'full') -> 'NDArray'`: Discrete convolution. ``same`` has the size of ``a``; ``valid`` has no edge effects.
- `fft(x: 'ArrayLike', n: 'int | None' = None) -> 'NDArray'`: Discrete Fourier transform (complex128), zero-padded or truncated to ``n``.
- `fftfreq(n: 'int', d: 'float' = 1.0) -> 'NDArray'`: Frequencies of ``fft`` bins for sample spacing ``d`` seconds (cycles per second).
- `ifft(X: 'ArrayLike', n: 'int | None' = None) -> 'NDArray'`: Inverse DFT (complex128), 1/N normalised.
- `irfft(X: 'ArrayLike', n: 'int | None' = None) -> 'NDArray'`: Inverse of ``rfft``; ``n`` is the output length (default 2*(len(X)-1), even).
- `psd(x: 'ArrayLike', fs: 'float', *, window: 'str' = 'hann', detrend: 'bool' = True) -> 'SpectrumResult'`: One-sided power spectral density (periodogram), units of x^2 per Hz.
- `rfft(x: 'ArrayLike', n: 'int | None' = None) -> 'NDArray'`: DFT of a real signal, non-negative frequencies only (n//2 + 1 values).
- `rfftfreq(n: 'int', d: 'float' = 1.0) -> 'NDArray'`: Frequencies of ``rfft`` bins (0 to Nyquist).
- `window(name: 'str', n: 'int', *, periodic: 'bool' = True) -> 'NDArray'`: Window of length ``n``: periodic (spectral analysis) or symmetric (filter design).

### `engstudio.engine.uncertainty`

Uncertainty propagation for a scalar measurement model y = f(x) (E12).

- class `UncertaintyResult(value: 'float', standard_uncertainty: 'float', expanded_uncertainty: 'float', interval: 'tuple[float, float]', coverage: 'float', sensit...`: UncertaintyResult(value: 'float', standard_uncertainty: 'float', expanded_uncertainty: 'float', interval: 'tuple[float, float]', coverage: 'float', sensitivities: 'NDArray', contributions: 'NDArray', method: 'str', k: 'float | None' = None, n_samples: 'int' = 0, diagnostics: 'tuple[Diagnostic, ...]' = ())
- `propagate(f: 'Callable[[NDArray], float]', x: 'ArrayLike', ux: 'ArrayLike', *, method: 'str' = 'linear', corr: 'ArrayLike | None' = None, coverage...`: Propagate input standard uncertainties ``ux`` through the scalar model ``f(x)``.

### `engstudio.engine.validation`

Input validation helpers shared by the engine modules.

- `as_matrix(a: 'ArrayLike', name: 'str' = 'a', *, allow_complex: 'bool' = True, square: 'bool' = False, allow_empty: 'bool' = False) -> 'NDArray'`: Validated 2-D float64/complex128 copy. Scalar -> 1x1, 1-D -> column, >2-D -> error.
- `as_vector(a: 'ArrayLike', name: 'str' = 'a', *, allow_complex: 'bool' = True, allow_empty: 'bool' = False, length: 'int | None' = None) -> 'NDArray'`: Validated 1-D copy. Accepts scalar, 1-D, or a 2-D row/column.
- `singular_error(message: 'str', rcond: 'float') -> 'SingularMatrixError'`: Build a ``SingularMatrixError`` carrying ``.rcond`` (contract, ARCHITECTURE section 6).

## gui

### `engstudio.gui`


### `engstudio.gui.app_main`

GUI entry point: ``python -m engstudio.gui [--smoke] [--stub] [file.m ...]``.

- `main(argv: 'list[str] | None' = None) -> 'int'`: 

### `engstudio.gui.calltip`

Call tips: while typing ``plot(x, `` a small box shows how the function can be called, with the argument at the cursor in bold, and (for toolbox functions) what that argument means.

- `CATALOG` (FunctionCatalog)
- class `CallTipController(widget: 'QWidget', catalog: 'FunctionCatalog | None' = None, above: 'bool' = False) -> 'None'`: Shows the call tip for ``widget`` as the user types or moves the cursor.
  - methods: refresh, eventFilter
- class `FunctionCatalog() -> 'None'`: Function name -> ``ToolboxFunction`` (signature, help, argument docs).
  - methods: update, get
- `call_context(text: 'str') -> 'tuple[str, int] | None'`: For the text before the cursor: (function name, zero-based argument index) of the
- `render_tip(entry: 'ToolboxFunction', index: 'int') -> 'str'`: 

### `engstudio.gui.command_window`

Command Window: input line with history, output area, errors in colour.

- class `CommandWindow(bridge: 'KernelBridge | None', history_items: 'Iterable[str]' = (), parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: focus_input, clear_output, echo, submit, paste_block, cancel_pending

### `engstudio.gui.diagnostic_log`

History of kernel diagnostics for the Diagnostics panel. Pure Python (no Qt).

- `CAP` (int)
- `SEVERITIES` (tuple)
- `SEVERITY_COLORS` (dict)
- class `DiagnosticEntry(seq: 'int', request_id: 'int', severity: 'str', code: 'str', message: 'str', file: 'str | None' = None, line: 'int | None' = None, col: ...`: DiagnosticEntry(seq: 'int', request_id: 'int', severity: 'str', code: 'str', message: 'str', file: 'str | None' = None, line: 'int | None' = None, col: 'int | None' = None)
- class `DiagnosticLog(cap: 'int' = 500) -> 'None'`: 
  - methods: add, clear, counts, visible
- `format_location(file: 'str | None', line: 'int | None', col: 'int | None') -> 'str'`: 
- `location_parts(loc: 'object') -> 'tuple[str | None, int | None, int | None]'`: (file, line, column) of a ``SourceLoc``; all ``None`` for no location.

### `engstudio.gui.diagnostics_panel`

Diagnostics panel (G6.1): table of kernel diagnostics kept across executions.

- class `DiagnosticsPanel(bridge: 'KernelBridge | None' = None, theme: 'str' = 'light', parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: visible_entries, clear, set_theme, activate_row, refresh

### `engstudio.gui.docs_panel`

Documentation panel (G6.2): local Markdown pages with Back/Forward/Home.

- class `DocsPanel(service: 'DocService | None' = None, theme: 'str' = 'light', parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: can_back, can_forward, show_page, home, back, forward, open_link, set_theme

### `engstudio.gui.editor_tabs`

Tabbed script editor with syntax highlighting.

- class `ScriptEditor(path: 'Path | None' = None, untitled_name: 'str' = 'untitled.m', theme: 'str' = 'light') -> 'None'`: 
- class `ScriptTabs(parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: editor, current_editor, set_theme, new_script, open_path, save, save_as, close_tab, maybe_close_all, session, restore_session

### `engstudio.gui.figure_edit`

Editing a figure in its window: titles, axis labels, limits, scales, grid, legend and the look of each line (name, colour, style, width, marker).

- class `AxesPropertiesDialog(spec: 'FigureSpec', index: 'int' = 0, focus: 'str' = '', parent: 'QWidget | None' = None, default_colors: 'tuple[str, ...]' = ('#0072BD'...`: Edit one axes (choose which with the subplot selector when there are several) and the
  - methods: applied, result_spec
- `edit_axes(spec: 'FigureSpec', index: 'int', **changes) -> 'FigureSpec'`: A copy of ``spec`` with fields of axes ``index`` changed (AxesSpec field names).
- `edit_figure_title(spec: 'FigureSpec', title: 'str') -> 'FigureSpec'`: 
- `edit_series(spec: 'FigureSpec', index: 'int', series: 'int', **changes) -> 'FigureSpec'`: A copy with fields of one series of axes ``index`` changed (SeriesSpec field names).
- `set_all_axes(spec: 'FigureSpec', **changes) -> 'FigureSpec'`: The same change (e.g. ``grid=True``) on every axes of the figure.

### `engstudio.gui.figure_window`

Top-level window showing one figure (``FigureView`` + status line for render warnings).

- class `FigureWindow(number: 'int', theme: 'str' = 'light', parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: set_figure, set_theme, apply_edit, edit_part, edit_figure_title, toggle_grid, toggle_legend, toggle_equal, reset_zoom, undo_changes, save_as, save_to, closeEvent

### `engstudio.gui.folder_panel`

Current Folder browser: file tree rooted at a chosen folder (G3.1).

- class `FolderPanel(settings: 'UiSettings | None' = None, parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: set_folder, go_up, browse, activate_path
- `SETTINGS_KEY` (str)

### `engstudio.gui.formatting`

Qt-free display helpers shared by GUI panels.

- `format_size(size: 'Sequence[int]') -> 'str'`: ``(3, 4)`` -> ``"3x4"``; N-d sizes join with ``x``; an empty size shows as ``"0x0"``.

### `engstudio.gui.highlight_rules`

Line tokenizer and colours for script syntax highlighting. Pure Python (no Qt).

- `KINDS` (tuple)
- `SYNTAX_COLORS` (dict)
- class `Token(start: int, length: int, kind: str)`: Token(start, length, kind)
- `tokenize_line(text: 'str', in_block: 'bool' = False, keywords: 'Collection[str]' = frozenset()) -> 'tuple[list[Token], bool]'`: Tokens of one line and the block-comment state for the next line.

### `engstudio.gui.highlighter`

Qt syntax highlighter for the script editor (rules live in ``highlight_rules``).

- class `ScriptHighlighter(document: 'QTextDocument', theme: 'str' = 'light', keywords: 'Collection[str] | None' = None) -> 'None'`: 
  - methods: set_theme, highlightBlock

### `engstudio.gui.history`

Command history with shell-style up/down navigation. Qt-free.

- class `CommandHistory(items: 'Iterable[str]' = (), max_size: 'int' = 1000) -> 'None'`: Keeps entered commands. ``previous``/``next`` walk the list; the text being typed
  - methods: items, add, reset, previous, next

### `engstudio.gui.kernel_bridge`

Qt adapter for a KernelClient: re-emits kernel events as a Qt signal and tracks whether code is running.

- class `KernelBridge(client: 'KernelClient', parent: 'QObject | None' = None) -> 'None'`: 
  - methods: execute, list_toolboxes, cancel, figure_closed, cancel_running, shutdown

### `engstudio.gui.main_window`

Main window: menus, toolstrip, dockable panels, themes, persisted layout.

- `about_text() -> 'str'`: Rich text for Help > About: version, contents, runtime and open-source credits.
- class `MainWindow(settings: 'UiSettings | None' = None, kernel: 'KernelClient | None' = None) -> 'None'`: 
  - methods: reset_layout, set_all_panels, toggle_fullscreen, closeEvent, focus_command, insert_in_command, run_script, run_selection, stop_execution, show_figure, close_figure, clear_command, base_theme, set_theme, toggle_theme, customize_theme, new_script, open_script, new_model, sync_working_folder, open_model, open_model_dialog, check_updates, show_about

### `engstudio.gui.mpl_view`

Embedded Matplotlib canvas for figures PyQtGraph cannot draw (3-D, polar, surface and contour axes; design pick 1). The figure is drawn by the same code as file export, so the window and a saved PNG/PDF look the same. A toolbar gives pan, zoom and (3-D) rotation. Double-clicking a title, an axis label or an axes emits `edit_requested` (as `FigureView`).

- class `MplFigureView(theme: 'str' = 'light', parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: main_axes, part_at, set_theme, set_figure

### `engstudio.gui.panels`

Dock panel registry. Panels not yet implemented are placeholders; each is replaced by a real component in its own module in later milestones (G2.3 workspace, G3 folder/toolboxes...).

- class `PanelContext(bridge: 'KernelBridge | None' = None, history_items: 'list[str]' = <factory>, settings: 'UiSettings | None' = None) -> None`: Shared services handed to every panel factory.
- class `PanelSpec(id: 'str', title: 'str', area: 'Qt.DockWidgetArea', create: 'Callable[[PanelContext], QWidget]', tab_with: 'str | None' = None, shortcut...`: PanelSpec(id: 'str', title: 'str', area: 'Qt.DockWidgetArea', create: 'Callable[[PanelContext], QWidget]', tab_with: 'str | None' = None, shortcut: 'str | None' = None)
- class `PlaceholderPanel(title: 'str', milestone: 'str', parent: 'QWidget | None' = None) -> 'None'`: Empty panel that states which milestone provides its real content.
- `default_panels() -> 'list[PanelSpec]'`: 

### `engstudio.gui.plot_params`

Rendering decisions for figures that need no Qt or PyQtGraph: colours, marker/pen mapping, log-axis ranges, bar width. Kept pure so they can be tested exhaustively.

- `PEN_STYLES` (dict)
- `SERIES_COLORS` (dict)
- `SYMBOLS` (dict)
- `bar_width(x: 'Iterable[float]') -> 'float'`: 80% of the smallest gap between distinct finite x positions (0.8 if fewer than two).
- `plot_colors(theme: 'str') -> 'tuple[str, str]'`: (background, foreground) for plots. Raises ValueError for an unknown theme.
- `series_color(theme: 'str', index: 'int', explicit: 'str | None') -> 'str'`: The series' own colour, else the theme's cycle colour for ``index``.
- `symbol_for(marker: 'str | None', kind: 'str') -> 'str | None'`: PyQtGraph symbol for a marker; scatter series default to circles, lines to none.
- `symbol_size(marker: 'str | None', size: 'float') -> 'float'`: 
- `tick_values(pairs: 'list[tuple[float, str]]', scale: 'str') -> 'list[tuple[float, str]]'`: Custom ticks in view coordinates; on a log axis non-positive ticks are dropped.
- `view_range(lim: 'tuple[float, float] | None', scale: 'str') -> 'tuple[float, float] | None'`: Axis limits in view coordinates (PyQtGraph log axes work in log10 units).

### `engstudio.gui.plots`

Renders a ``FigureSpec`` with PyQtGraph. The GUI only ever sees the spec (plain data).

- class `FigureView(theme: 'str' = 'light', parent: 'QWidget | None' = None) -> 'None'`: Axes laid out on the figure's rows x cols grid (``FigureSpec.placements``), with the
  - methods: plot_items, set_theme, set_figure, part_at, mouseDoubleClickEvent

### `engstudio.gui.settings`

Small JSON store for UI preferences (theme, window geometry, dock layout).

- class `UiSettings(path: 'Path | str | None' = None) -> 'None'`: Key/value store. ``path=None`` keeps everything in memory (tests, smoke runs).
  - methods: load, get, set, get_bytes, set_bytes, save
- `default_settings_path() -> 'Path'`: 

### `engstudio.gui.sim_editor`

Block-diagram model editor (Phase 7, S13-S16): library, canvas, wiring, parameter and settings dialogs, Run/Stop with Scope windows, open/save ``.esmodel``.

- class `SimEditor(model: 'Model | None' = None, path: 'Path | None' = None, theme: 'str' = 'light', parent: 'QWidget | None' = None, is_subsystem: 'bool' ...`: 
  - methods: undo, redo, add_block, connect, delete, delete_selected, set_block, sync_positions, redraw, open_block, open_subsystem, settings_dialog, new_model, open_dialog, open_path, save, save_as, save_to, closeEvent, run_async, stop, run_blocking

### `engstudio.gui.single_instance`

One running Engineering Studio per user: a second launch (desktop shortcut, "Open with" on an .m file) hands its file names to the window that is already open and exits, instead of starting a second, slow copy of the application.

- class `SingleInstance(name: 'str | None' = None, parent: 'QObject | None' = None) -> 'None'`: 
  - methods: try_forward, listen, close
- `server_name() -> 'str'`: 

### `engstudio.gui.splash`

Start-up splash: a card drawn with vector graphics at the screen's real resolution, so it stays sharp at any display scaling (the old splash enlarged the 48-pixel icon).

- `make_splash() -> 'QSplashScreen'`: 
- `splash_pixmap(scale: 'float' = 1.0) -> 'QPixmap'`: 

### `engstudio.gui.theme`

Light/dark themes. Palettes and the stylesheet are plain data (no Qt import at module level).

- class `Palette(name: 'str', window: 'str', base: 'str', alt_base: 'str', text: 'str', text_dim: 'str', border: 'str', accent: 'str', accent_text: 'str'...`: Palette(name: 'str', window: 'str', base: 'str', alt_base: 'str', text: 'str', text_dim: 'str', border: 'str', accent: 'str', accent_text: 'str', button: 'str', hover: 'str', toolbar: 'str', selection: 'str')
- `LIGHT` (Palette)
- `DARK` (Palette)
- `THEMES` (dict)
- `get_palette(name: 'str') -> 'Palette'`: 
- `build_stylesheet(p: 'Palette') -> 'str'`: 
- `contrast_ratio(fg: 'str', bg: 'str') -> 'float'`: WCAG 2.x contrast ratio between two ``#rrggbb`` colours.
- `apply_theme(app, name: 'str') -> 'None'`: Apply a built-in theme to a QApplication.
- `apply_palette(app, p: 'Palette') -> 'None'`: Apply any palette to a QApplication (Fusion style + palette + stylesheet).

### `engstudio.gui.theme_custom`

Custom themes (G7): colour parsing, palette validation, contrast checks, JSON.

- `ROLE_LABELS` (dict)
- `ROLES` (tuple)
- `MIN_CONTRAST` (float)
- `MAX_NAME` (int)
- `MAX_THEMES` (int)
- `CONTRAST_PAIRS` (tuple)
- class `ContrastIssue(fg: 'str', bg: 'str', ratio: 'float') -> None`: ContrastIssue(fg: 'str', bg: 'str', ratio: 'float')
- class `ThemeFile(name: 'str', base: 'str', palette: 'Palette') -> None`: ThemeFile(name: 'str', base: 'str', palette: 'Palette')
- class `CustomThemes() -> 'None'`: Named custom palettes, each with the built-in theme ('light'/'dark') it is based on.
  - methods: names, get, base_of, resolve, set, delete, to_data, from_data
- `parse_hex(text: 'object') -> 'str'`: Normalise ``#rgb``, ``rgb``, ``#rrggbb`` or ``rrggbb`` to lowercase ``#rrggbb``.
- `make_palette(name: 'str', colors: 'Mapping[str, object]', base: 'Palette') -> 'Palette'`: Palette named ``name``; roles missing from ``colors`` come from ``base``.
- `contrast_issues(palette: 'Palette', minimum: 'float' = 4.5) -> 'list[ContrastIssue]'`: Foreground/background pairs of ``CONTRAST_PAIRS`` whose WCAG ratio is below ``minimum``.
- `role_issues(issues: 'Iterable[ContrastIssue]', role: 'str') -> 'str'`: Text for the warning column of ``role`` ('' when it takes part in no failing pair).
- `readable_text_colour(background: 'str') -> 'str'`: Black or white, whichever contrasts more with ``background`` (a ``#rrggbb`` colour).
- `validate_name(name: 'object', existing: 'Iterable[str]' = ()) -> 'str'`: Clean and check a custom theme name; returns the cleaned name or raises ValueError.
- `palette_to_json(palette: 'Palette', base: 'str') -> 'str'`: 
- `palette_from_json(text: 'str') -> 'ThemeFile'`: Parse a theme file. Missing colours fall back to the base theme; ValueError if bad.

### `engstudio.gui.theme_dialog`

Theme editor dialog (G7). Qt only; the colour logic lives in ``theme_custom``.

- class `ThemeDialog(themes: 'CustomThemes', active: 'str', parent=None) -> 'None'`: 
  - methods: current_palette, load_theme, set_role_color, reset_to_base, save_theme, delete_theme, to_json_text, load_json_text, import_theme, export_theme

### `engstudio.gui.toolbox_panel`

Toolbox browser (G3.2): tree of toolboxes and their functions, with a filter box.

- class `ToolboxPanel(bridge: 'KernelBridge | None' = None, parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: refresh, populate, apply_filter, show_details, activate_item

### `engstudio.gui.updates`

Help > Check for Updates: asks GitHub for the newest release only when the user clicks it (the application is otherwise fully offline).

- `INSTALLER_ARGS` (list)
- `RELEASES_PAGE` (str)
- class `Release(tag: 'str', page: 'str', installer_name: 'str' = '', installer_url: 'str' = '', installer_size: 'int' = 0, sha256: 'str' = '', sha256_ur...`: Release(tag: 'str', page: 'str', installer_name: 'str' = '', installer_url: 'str' = '', installer_size: 'int' = 0, sha256: 'str' = '', sha256_url: 'str' = '')
- class `UpdateChecker(current: 'str', parent: 'QWidget | None' = None, launcher: 'Callable[[Path], bool]' = <function _launch at 0x000001CD807603B0>, download...`: 
  - methods: check, download_and_install
- `is_newer(latest: 'str', current: 'str') -> 'bool'`: True if release tag ``latest`` (e.g. 'v0.7.0') is newer than ``current``.
- `parse_release(payload: 'bytes') -> 'Release'`: The release and its installer asset from GitHub's 'latest release' JSON; ValueError if
- `sha256_of(path: 'Path') -> 'str'`: 

### `engstudio.gui.workspace_panel`

Workspace browser: live table of the kernel's variables.

- class `WorkspaceModel(parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: rowCount, columnCount, data, headerData, variable, set_variables
- class `WorkspacePanel(bridge: 'KernelBridge | None', parent: 'QWidget | None' = None) -> 'None'`: 
  - methods: selected_names, clear_selected, clear_all, save_workspace, load_workspace

## lang

### `engstudio.lang`


### `engstudio.lang.ast`

AST node dataclasses for the Engineering Studio v1 MATLAB-like subset (T3.2).

- class `Node(*, loc: 'SourceLoc | None' = None) -> None`: Base class. ``loc`` is keyword-only and ignored by ``==``.
- class `Number(value: 'float', *, loc: 'SourceLoc | None' = None) -> None`: Number(value: 'float', *, loc: 'SourceLoc | None' = None)
- class `Imag(value: 'complex', *, loc: 'SourceLoc | None' = None) -> None`: Imaginary literal such as ``2i``; ``value`` is the complex number ``0+2j``.
- class `String(value: 'str', double_quoted: 'bool' = False, *, loc: 'SourceLoc | None' = None) -> None`: String(value: 'str', double_quoted: 'bool' = False, *, loc: 'SourceLoc | None' = None)
- class `Ident(name: 'str', *, loc: 'SourceLoc | None' = None) -> None`: Ident(name: 'str', *, loc: 'SourceLoc | None' = None)
- class `Colon(*, loc: 'SourceLoc | None' = None) -> None`: Bare ``:`` inside an index (select all).
- class `End(*, loc: 'SourceLoc | None' = None) -> None`: ``end`` inside an index (last element along that dimension).
- class `Unary(op: 'str', operand: 'Node', *, loc: 'SourceLoc | None' = None) -> None`: Unary(op: 'str', operand: 'Node', *, loc: 'SourceLoc | None' = None)
- class `Postfix(op: 'str', operand: 'Node', *, loc: 'SourceLoc | None' = None) -> None`: Transpose: ``'`` (conjugate) or ``.'`` (plain).
- class `Binary(op: 'str', left: 'Node', right: 'Node', *, loc: 'SourceLoc | None' = None) -> None`: Binary(op: 'str', left: 'Node', right: 'Node', *, loc: 'SourceLoc | None' = None)
- class `Range(start: 'Node', step: 'Node | None', stop: 'Node', *, loc: 'SourceLoc | None' = None) -> None`: ``start:stop`` or ``start:step:stop`` (``step`` is None for the two-part form).
- class `Index(target: 'Node', args: 'tuple[Node, ...]' = (), *, loc: 'SourceLoc | None' = None) -> None`: ``target(args)``: array index or function call.
- class `CellIndex(target: 'Node', args: 'tuple[Node, ...]' = (), *, loc: 'SourceLoc | None' = None) -> None`: ``target{args}``: cell content indexing.
- class `Field(target: 'Node', name: 'str', *, loc: 'SourceLoc | None' = None) -> None`: ``target.name`` (struct field access).
- class `Matrix(rows: 'tuple[tuple[Node, ...], ...]' = (), *, loc: 'SourceLoc | None' = None) -> None`: ``[a, b; c, d]``: ``rows`` is a tuple of rows, each a tuple of elements.
- class `CellLiteral(rows: 'tuple[tuple[Node, ...], ...]' = (), *, loc: 'SourceLoc | None' = None) -> None`: ``{a, b; c, d}``.
- class `FuncHandle(name: 'str', *, loc: 'SourceLoc | None' = None) -> None`: ``@name``.
- class `AnonFunc(params: 'tuple[str, ...]', body: 'Node', *, loc: 'SourceLoc | None' = None) -> None`: ``@(params) body``.
- class `Tilde(*, loc: 'SourceLoc | None' = None) -> None`: Ignored output placeholder in ``[~, i] = max(x)``; valid only as an Assign target.
- class `ExprStmt(expr: 'Node', printed: 'bool' = True, *, loc: 'SourceLoc | None' = None) -> None`: ExprStmt(expr: 'Node', printed: 'bool' = True, *, loc: 'SourceLoc | None' = None)
- class `Assign(targets: 'tuple[Node, ...]', value: 'Node', printed: 'bool' = True, *, loc: 'SourceLoc | None' = None) -> None`: ``a = e``, ``a(i).f = e`` or ``[a, ~, b] = e``.
- class `IfClause(cond: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None) -> None`: IfClause(cond: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None)
- class `If(clauses: 'tuple[IfClause, ...]', else_body: 'tuple[Node, ...] | None' = None, *, loc: 'SourceLoc | None' = None) -> None`: ``if``/``elseif`` clauses in order, then optional ``else`` body.
- class `For(var: 'Ident', iterable: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None) -> None`: For(var: 'Ident', iterable: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None)
- class `While(cond: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None) -> None`: While(cond: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None)
- class `Case(value: 'Node', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None) -> None`: ``case expr``; a cell literal means "any of".
- class `Switch(subject: 'Node', cases: 'tuple[Case, ...]', otherwise: 'tuple[Node, ...] | None' = None, *, loc: 'SourceLoc | None' = None) -> None`: Switch(subject: 'Node', cases: 'tuple[Case, ...]', otherwise: 'tuple[Node, ...] | None' = None, *, loc: 'SourceLoc | None' = None)
- class `Break(*, loc: 'SourceLoc | None' = None) -> None`: Break(*, loc: 'SourceLoc | None' = None)
- class `Continue(*, loc: 'SourceLoc | None' = None) -> None`: Continue(*, loc: 'SourceLoc | None' = None)
- class `Return(*, loc: 'SourceLoc | None' = None) -> None`: Return(*, loc: 'SourceLoc | None' = None)
- class `TryCatch(body: 'tuple[Node, ...]', catch_var: 'str | None', catch_body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None) -> None`: TryCatch(body: 'tuple[Node, ...]', catch_var: 'str | None', catch_body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None)
- class `FunctionDef(name: 'str', params: 'tuple[str, ...]', outputs: 'tuple[str, ...]', body: 'tuple[Node, ...]', *, loc: 'SourceLoc | None' = None) -> None`: ``function [o1, o2] = name(p1, p2) ... end``.
- class `Program(body: 'tuple[Node, ...]' = (), *, loc: 'SourceLoc | None' = None) -> None`: A parsed script or file: top-level statements (including FunctionDef).
- `children(node: 'Node') -> 'Iterator[Node]'`: Yield the direct child nodes of ``node`` in field order (tuples are flattened).
- `walk(node: 'Node') -> 'Iterator[Node]'`: Pre-order traversal including ``node`` itself.

### `engstudio.lang.builtins_analysis`

Analysis builtins (B2b-4): ``interp2``, ``fminbnd``, ``fminunc``, ``linprog``, ``quantile``, ``prctile``, ``ttest``, ``ttest2``. ``install_analysis(interp)`` registers them.

- `analysis_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The B2b-4 builtins bound to ``interp``.
- `install_analysis(interp: 'Interpreter') -> 'None'`: Register the B2b-4 builtins on ``interp``.

### `engstudio.lang.builtins_control`

Control systems in the interpreter (Phase 6, C2): tf, zpk, ss, pid, pidstd, feedback, series, parallel, pole, zero, dcgain, damp, isstable, stepinfo, margin (values), c2d, tfdata, zpkdata, ssdata, order, isdt, minreal.

- `control_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: 
- `install_control(interp: 'Interpreter') -> 'None'`: 
- `lti_binary(op: 'str', a: 'object', b: 'object') -> 'LtiValue'`: 
- `lti_text(v: 'LtiValue') -> 'str'`: 
- `lti_unary(op: 'str', a: 'LtiValue') -> 'LtiValue'`: 

### `engstudio.lang.builtins_controlplot`

Control-system response plots (Phase 6, C3): step, impulse, initial, lsim, bode, margin, nyquist, rlocus, pzmap.

- `control_plot_functions(interp: 'Interpreter', manager: 'FigureManager', push: 'Callable[[int | None], None]') -> 'dict[str, Builtin]'`: 
- `install_control_plots(interp: 'Interpreter', manager: 'FigureManager') -> 'None'`: Install after ``install_control`` (replaces its text-only ``margin``) and

### `engstudio.lang.builtins_core`

Core builtin functions of the interpreter, part 1 (B1a).

- class `UserError(message: 'str', identifier: 'str' = '') -> 'None'`: Raised by the ``error`` builtin; ``identifier`` is exposed as ``err.identifier``.
- `core_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The core builtins bound to ``interp`` (its host receives output and warnings).
- `format_text(fmt: 'str', args: 'Sequence', name: 'str' = 'sprintf') -> 'str'`: MATLAB ``sprintf``: the format is reused until all arguments are consumed.
- `install_core(interp: 'Interpreter') -> 'None'`: Register the core builtins on ``interp`` (core names overwrite entries of that name).

### `engstudio.lang.builtins_data`

Numerical-analysis, statistics and FFT builtins (B2b-2), none of which take function handles.

- `data_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The B2b-2 builtins bound to ``interp``.
- `install_data(interp: 'Interpreter') -> 'None'`: Register the B2b-2 builtins on ``interp``.

### `engstudio.lang.builtins_decomp`

Matrix-decomposition builtins (B2a): ``eig``, ``lu``, ``qr``, ``chol``, ``svd``.

- `decomp_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The decomposition builtins bound to ``interp``.
- `install_decomp(interp: 'Interpreter') -> 'None'`: Register the decomposition builtins on ``interp``.

### `engstudio.lang.builtins_extra`

More builtins (B1b): structs, cells, ``cellfun``/``arrayfun``, sets, operator functions, random numbers and timing; ``install_extra`` also registers the string functions.

- `extra_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: All B1b builtins (including the string functions) bound to ``interp``.
- `install_extra(interp: 'Interpreter') -> 'None'`: Register the B1b builtins (strings, structs, cells, functional, random, timing).

### `engstudio.lang.builtins_funcs`

Handle-based numerical builtins (B2b-3): functions that take a function handle.

- `funcs_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The B2b-3 builtins bound to ``interp``.
- `install_funcs(interp: 'Interpreter') -> 'None'`: Register the B2b-3 builtins on ``interp``.

### `engstudio.lang.builtins_plot`

Plot commands of the interpreter (P5.1): figure, gcf, gca, clf, cla, close, hold, ishold, plot, drawnow; plus the axes/annotation commands of ``lang.builtins_plotaxes`` (P5.2) and the 2-D plot types of ``lang.builtins_plot2d`` (P5.3), installed together by ``install_plot``. Thin layer over ``lang.figstate``; the kernel client supplies ``publish(spec)`` (send a figure snapshot to the GUI) and ``retire(number)`` (tell the GUI to close a window).

- class `Publisher(publish: 'Callable[[FigureSpec], None]', manager: 'FigureManager', min_interval: 'float' = 0.0, clock: 'Callable[[], float]' = <built-in...`: Sends figure snapshots to the GUI, at most one per figure every ``min_interval``
  - methods: push, wait_time, push_now, flush, forget
- `install_plot(interp: 'Interpreter', publish: 'Callable[[FigureSpec], None]', retire: 'Callable[[int], None]', min_interval: 'float' = 0.0) -> 'Figure...`: Register the plot commands on ``interp``; returns the figure manager they use.
- `plot_functions(interp: 'Interpreter', publish: 'Callable[[FigureSpec], None]', retire: 'Callable[[int], None]', manager: 'FigureManager', publisher: 'P...`: 

### `engstudio.lang.builtins_plot2d`

2-D plot types (P5.3): bar, stem, stairs, area, scatter, semilogx, semilogy, loglog, histogram, hist, histcounts.

- `plot2d_functions(manager: 'FigureManager', push: 'Push') -> 'dict[str, Builtin]'`: 

### `engstudio.lang.builtins_plot3d`

3-D, gridded, polar and reference-line plots (P5.4): plot3, scatter3, surf, mesh, contour, contourf, zlabel, zlim, view, colorbar, colormap, shading, polarplot, errorbar, xline, yline.

- `plot3d_functions(manager: 'FigureManager', push: 'Push') -> 'dict[str, Builtin]'`: 

### `engstudio.lang.builtins_plotaxes`

Axes and annotation commands (P5.2): subplot, axes, title, xlabel, ylabel, sgtitle, grid, box, legend, xlim, ylim, axis, xticks, yticks, xticklabels, yticklabels, text, set, get.

- `axes_functions(manager: 'FigureManager', push: 'Push') -> 'dict[str, Builtin]'`: 
- `label_text(v: 'object', who: 'str') -> 'str'`: Text for a label: char row, char matrix or cell array of rows (joined with newlines);
- `to_py(v: 'object', who: 'str') -> 'object'`: Interpreter value -> ``str`` (character vector) or 2-D float/complex array.

### `engstudio.lang.builtins_plotio`

Animation and figure files (P5.5): pause, animatedline, addpoints, clearpoints, saveas, print, exportgraphics.

- `plotio_functions(interp: 'Interpreter', manager: 'FigureManager', publisher: '_Publisher') -> 'dict[str, Builtin]'`: 

### `engstudio.lang.builtins_poly`

Polynomial builtins (B2b-1): ``poly``, ``roots``, ``polyval``, ``polyfit``.

- `poly_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The polynomial builtins bound to ``interp``.
- `install_poly(interp: 'Interpreter') -> 'None'`: Register the polynomial builtins on ``interp``.

### `engstudio.lang.builtins_sym`

Symbolic builtins (B2b-5): ``syms``, ``sym``, ``diff``, ``int``, ``limit``, ``taylor``, ``solve``, ``simplify``, ``expand``, ``factor``, ``subs``, ``laplace``, ``ilaplace``, ``latex``, ``symvar``, plus symbolic behaviour for ``double``, ``char``, ``disp`` and the elementary functions (``sin cos tan asin acos atan sinh cosh tanh exp log log10 sqrt abs``). ``install_sym(interp)`` registers them (after the core builtins, which it extends).

- `display_text(name: 'str', value: 'object') -> 'str'`: Command Window text: symbolic values as ``name =`` + expression, others as before.
- `install_sym(interp: 'Interpreter') -> 'None'`: Register the symbolic builtins on ``interp`` (after ``install_core``).
- `preview_text(value: 'object') -> 'str'`: Short text for the Workspace browser.
- `sym_functions(interp: 'Interpreter') -> 'dict[str, Builtin]'`: The B2b-5 builtins bound to ``interp`` (overloads wrap the existing numeric ones).
- `sym_text(value: 'SymValue') -> 'str'`: 

### `engstudio.lang.builtins_text`

String builtins (B1b): comparison, case, trimming, search, splitting, conversion.

- `text_functions() -> 'dict[str, Builtin]'`: The string builtins (a fresh dictionary).

### `engstudio.lang.display`

Command Window text for values (T3.4d): ``format_value``, ``format_disp``, ``unparse``.

- `unparse(node: 'A.Node') -> 'str'`: Source text of an expression node.
- `handle_text(h: 'FunctionHandle') -> 'str'`: ``@sin`` or ``@(x) x.^2 + 1``.
- `format_value(name: 'str', value: 'object') -> 'str'`: Text MATLAB would print for the statement ``name = value`` (ends with a newline).
- `format_disp(value: 'object') -> 'str'`: Text of ``disp(value)`` (ends with a newline; empty arrays print nothing).
- `short_text(value: 'object', limit: 'int' = 40) -> 'str'`: One-line preview for the Workspace browser (scalars show their value).

### `engstudio.lang.fastcall`

Fast calls of anonymous functions (``@(t, y) [y(2); -wn^2*y(1)]``).

- class `Fallback(...)`: The compiled path cannot handle this call; use the interpreter instead.
- `compile_anon(interp, params: 'tuple[str, ...]', captured: 'frozenset[str]', body: 'A.Node') -> 'Compiled | None'`: A function ``env -> value`` for the body, or ``None`` if it is not simple enough.

### `engstudio.lang.figstate`

Kernel-side figure state and plot-argument handling (pure Python/NumPy, no GUI, no values).

- class `FigureManager() -> 'None'`: 
  - methods: numbers, current_number, props, figure, update_figure, figure_name, gcf, gca, set_title, figure_title, clf, cla, close, subplot, select_axes, hold, ishold, add_lines, add_overlay, update_surfaces, axes_props, set_axes, axes_series, relabel, add_text, is_axes, is_figure, line, replace_line, figure_of, snapshot
- `MAX_FIGURE` (int)
- `MAX_GRID` (int)
- `build_series(items: 'list') -> 'list[SeriesSpec]'`: ``plot`` arguments (2-D float arrays and ``str``) -> series, in drawing order.
- `parse_color(value: 'object', who: 'str' = 'plot') -> 'str'`: 'r', 'red', '#rrggbb' or an RGB triple in [0, 1] -> '#rrggbb'.
- `parse_linespec(text: 'str', who: 'str' = 'plot') -> 'tuple[str | None, str | None, str | None]'`: 'r--o' -> (color, line style, marker); each part is None when not given.

### `engstudio.lang.indexing`

Indexing and indexed assignment on interpreter values (T3.4b). Pure functions.

- `end_value(v: 'object', position: 'int', nargs: 'int') -> 'int'`: Value of ``end`` at index ``position`` (0-based) of an ``nargs``-index expression.
- `index_value(v: 'object', args: 'Sequence[object]') -> 'object'`: ``v(args...)`` for numeric, char and cell values (cell gives a cell) and 1x1 structs.
- `cell_contents(v: 'object', args: 'Sequence[object]') -> 'list[object]'`: ``c{args...}``: the selected elements in column-major order (a comma-separated list).
- `assign_index(base: 'object | None', args: 'Sequence[object]', rhs: 'object') -> 'object'`: ``base(args...) = rhs``. ``base=None`` means an undefined variable.
- `assign_cell_content(base: 'object | None', args: 'Sequence[object]', rhs: 'object') -> 'CellArray'`: ``base{args...} = rhs`` (``base=None`` or ``[]`` starts a new cell array).
- `get_field(v: 'object', name: 'str') -> 'object'`: ``v.name`` for a struct.
- `set_field(base: 'object | None', name: 'str', rhs: 'object') -> 'StructValue'`: ``base.name = rhs`` (``base=None`` or ``[]`` starts a new struct).

### `engstudio.lang.interp`

Tree-walking evaluator: ``Workspace``, ``Interpreter`` and ``EvalError`` (T3.4c).

- class `EvalError(message: 'str', location: 'SourceLoc | None' = None) -> 'None'`: Runtime error with the source location of the failing node.
  - methods: to_diagnostic
- class `Cancelled(...)`: Execution was stopped with ``Interpreter.cancel()``; never caught by ``try``/``catch``.
- class `Host()`: Output callbacks; subclass and override (the defaults discard everything).
  - methods: display, diagnostic, write
- class `Workspace() -> 'None'`: Named values of the base workspace (insertion ordered, names validated).
  - methods: names, clear, summary
- class `Interpreter(workspace: 'Workspace | None' = None, functions: 'Mapping[str, Function] | None' = None, host: 'Host | None' = None, max_depth: 'int' = ...`: 
  - methods: execute, cancel, clear_cancel, check_cancel, run, call, exec_stmt, one, values

### `engstudio.lang.lexer`

Lexer for the Engineering Studio v1 MATLAB-like subset. Tokens only; no parser.

- class `LexError(message: 'str', location: 'SourceLoc | None' = None) -> 'None'`: Invalid character or malformed token/bracket structure.
  - methods: to_diagnostic
- class `Token(kind: 'str', text: 'str', loc: 'SourceLoc', value: 'object' = None, space_before: 'bool' = False, synthetic: 'bool' = False) -> None`: Token(kind: 'str', text: 'str', loc: 'SourceLoc', value: 'object' = None, space_before: 'bool' = False, synthetic: 'bool' = False)
- `tokenize(source: 'str', file: 'str | None' = None) -> 'list[Token]'`: Tokenize ``source``; the result always ends with an ``EOF`` token.

### `engstudio.lang.ops`

Operators, ranges and concatenation on interpreter values (T3.4a). Pure functions.

- `binary_op(op: 'str', a: 'object', b: 'object', diagnostics: 'list[Diagnostic] | None' = None) -> 'np.ndarray'`: Apply a binary operator (every ``lang.ast.BINARY_OPS`` entry except ``&&``/``||``).
- `to_logical_scalar(v: 'object', op: 'str') -> 'bool'`: Operand of ``&&``/``||``: must be a non-empty scalar convertible to logical.
- `unary_op(op: 'str', a: 'object') -> 'np.ndarray'`: 
- `transpose(a: 'object', conjugate: 'bool') -> 'object'`: ``a'`` (``conjugate=True``) or ``a.'``. Works on numeric, char and cell values.
- `colon_range(start: 'object', step: 'object | None', stop: 'object') -> 'np.ndarray'`: ``start:step:stop`` (``step=None`` means 1). Returns a 1-by-n row; n may be 0.
- `horzcat(values: 'Sequence[object]') -> 'object'`: ``[a, b, ...]``. 0-by-0 operands are skipped, as in MATLAB.
- `vertcat(values: 'Sequence[object]') -> 'object'`: ``[a; b; ...]``.
- `build_matrix(rows: 'Sequence[Sequence[object]]') -> 'object'`: Matrix literal ``[r1; r2; ...]`` where each row is a sequence of evaluated elements.
- `build_cell(rows: 'Sequence[Sequence[object]]') -> 'CellArray'`: Cell literal ``{...}``: every element becomes one cell entry (cells are not flattened).

### `engstudio.lang.parser`

Handwritten Pratt/recursive-descent parser: tokens -> ``lang.ast`` (T3.3).

- class `ParseError(message: 'str', location: 'SourceLoc | None' = None) -> 'None'`: Syntax error with a source location.
  - methods: to_diagnostic
- `parse(source: 'str', file: 'str | None' = None) -> 'A.Program'`: Parse ``source`` into a ``Program``. Raises ``LexError`` or ``ParseError``.

### `engstudio.lang.symops`

Operators on symbolic values (B2b-5): hooks called by the interpreter.

- `binary_op(op: 'str', left: 'object', right: 'object', diags: 'list') -> 'object'`: 
- `build_matrix(rows: 'object') -> 'object'`: 
- `number_of(v: 'object') -> 'int | float | complex'`: Python number from a 1-by-1 double (integral values become ``int``).
- `transpose(value: 'object', conjugate: 'bool') -> 'object'`: 
- `unary_op(op: 'str', value: 'object') -> 'object'`: 

### `engstudio.lang.values`

Value model of the Engineering Studio interpreter (T3.4a).

- `empty_double() -> 'np.ndarray'`: The 0-by-0 double matrix ``[]``.
- class `CharArray(data: 'np.ndarray') -> 'None'`: 2-D character array. ``CharArray.from_str("abc")`` is 1-by-3; ``""`` is 0-by-0.
  - methods: from_str, to_str, codes
- class `CellArray(data: 'np.ndarray') -> 'None'`: 2-D cell array; every element is a value.
  - methods: empty, from_rows
- class `StructValue(fields: 'Mapping[str, object] | None' = None) -> 'None'`: A 1-by-1 struct with ordered fields. Immutable: ``with_field`` returns a new struct.
  - methods: names, items, has, get, with_field
- class `FunctionHandle(name: 'str | None' = None, params: 'Sequence[str]' = (), body: 'A.Node | None' = None, captured: 'Mapping[str, object] | None' = None) -...`: ``@name`` (named) or ``@(params) body`` (anonymous, with captured variables).
- class `SymValue(expr: 'object') -> 'None'`: A symbolic scalar: wraps ``engine.symbolic.SymExpr`` (class ``sym``). Immutable.
- class `LtiValue(system: 'object') -> 'None'`: A linear system (class 'tf', 'zpk' or 'ss'): wraps ``control.lti.LtiSystem``.
- `is_value(x: 'object') -> 'bool'`: 
- `to_value(x: 'object') -> 'object'`: Convert Python data to a value (values pass through unchanged).
- `class_of(v: 'object') -> 'str'`: 
- `size_of(v: 'object') -> 'tuple[int, int]'`: 
- `numel_of(v: 'object') -> 'int'`: 
- `is_empty(v: 'object') -> 'bool'`: 
- `values_equal(a: 'object', b: 'object') -> 'bool'`: Strict structural equality (NaN is not equal to NaN, like MATLAB ``isequal``).
- `is_true(v: 'object') -> 'bool'`: Truth value for ``if``/``while``: non-empty and all elements nonzero.

## plotting

### `engstudio.plotting`


### `engstudio.plotting.export`

Export a ``FigureSpec`` to PNG, SVG or PDF with Matplotlib (Agg, no Qt, no pyplot).

- `EXPORT_FORMATS` (dict)
- `MATPLOTLIB_LOCK` (RLock)
- `build_figure(spec: 'FigureSpec', size_in: 'tuple[float, float]' = (7.2, 4.8)) -> 'Figure'`: The Matplotlib figure for ``spec`` (not tied to pyplot or any GUI backend).
- `cmap_name(name: 'str') -> 'str'`: 
- `draw_figure(fig: 'Figure', spec: 'FigureSpec') -> 'None'`: Draw ``spec`` onto an empty Matplotlib figure (export or the GUI's embedded canvas).
- `export_figure(spec: 'FigureSpec', path: 'Path | str', *, dpi: 'int' = 150, size_in: 'tuple[float, float]' = (7.2, 4.8)) -> 'Path'`: Write ``spec`` to ``path``; the format comes from the suffix (.png, .svg, .pdf).
- `load_matplotlib() -> 'None'`: Import Matplotlib's core once, under a lock. The kernel thread (export) and the GUI
- `render_png(spec: 'FigureSpec', *, dpi: 'int' = 100, size_in: 'tuple[float, float]' = (7.2, 4.8)) -> 'bytes'`: The figure as PNG bytes (one animation frame).
- `write_gif(path: 'Path | str', frames: 'list[bytes]', delay_s: 'float' = 0.1) -> 'Path'`: Write PNG ``frames`` as a looping animated GIF (atomically). Frames of another size

### `engstudio.plotting.model`

Figure description as plain, immutable data (no Qt, no Matplotlib).

- `COLORMAPS` (tuple)
- `PROJECTIONS` (tuple)
- `SURFACE_KINDS` (tuple)
- class `AxesSpec(series: 'tuple[SeriesSpec, ...]' = (), title: 'str' = '', xlabel: 'str' = '', ylabel: 'str' = '', xlim: 'tuple[float, float] | None' = N...`: One axes. ``cell`` = (row, col, rowspan, colspan) in the figure grid; ``None`` places
  - methods: tick_pairs
- class `FigureSpec(number: 'int' = 1, title: 'str' = '', axes: 'tuple[AxesSpec, ...]' = (), rows: 'int' = 1, cols: 'int' = 1, name: 'str' = '', size: 'tupl...`: A figure window's content: ``axes`` fill a ``rows`` x ``cols`` grid in row-major order.
  - methods: placements
- `INTERPRETERS` (tuple)
- `LINE_STYLES` (tuple)
- `MARKERS` (tuple)
- `SCALES` (tuple)
- `SERIES_KINDS` (tuple)
- class `SeriesSpec(kind: 'SeriesKind', x: 'np.ndarray', y: 'np.ndarray', label: 'str' = '', color: 'str | None' = None, line_style: 'str' = '-', line_width...`: One data series. ``color`` is ``None`` (renderer picks) or ``#rrggbb``;
- class `SurfaceSpec(kind: 'str', x: 'np.ndarray', y: 'np.ndarray', z: 'np.ndarray', levels: 'int | tuple[float, ...] | None' = None, edge_color: 'str | None...`: Gridded data: ``surface``/``mesh`` (3-D) or ``contour``/``contourf`` (2-D).
- class `TextSpec(x: 'float', y: 'float', text: 'str', color: 'str | None' = None) -> None`: A text annotation at data coordinates (x, y).

### `engstudio.plotting.text`

MATLAB TeX subset for plot text (pure, no Qt, no Matplotlib).

- `GREEK` (dict)
- `SYMBOLS` (dict)
- `parse_tex(text: 'str') -> 'list[tuple[str, int]]'`: 
- `tex_to_html(text: 'str', interpreter: 'str' = 'tex') -> 'str'`: HTML for Qt rich text (``<sup>``/``<sub>``); plain text is escaped.
- `tex_to_mathtext(text: 'str', interpreter: 'str' = 'tex') -> 'str'`: Matplotlib label text: normal runs as text, sub/superscripts as ``$^{...}$``.
- `tex_to_plain(text: 'str', interpreter: 'str' = 'tex') -> 'str'`: 
- `tex_to_unicode(text: 'str', interpreter: 'str' = 'tex') -> 'str'`: Plain text for places without rich text (tick labels): sub/superscripts use Unicode

## selftest

### `engstudio.selftest`

Built-in self-test: proves that the installed or frozen application is healthy.

- `check_units() -> 'None'`: 
- `check_numpy() -> 'None'`: 
- `check_scipy() -> 'None'`: 
- `check_sympy() -> 'None'`: 
- `check_pandas_openpyxl() -> 'None'`: 
- `check_matplotlib() -> 'None'`: 
- `check_control() -> 'None'`: 
- `check_sqlite() -> 'None'`: 
- `check_qt_importable() -> 'None'`: 
- `check_process_roundtrip() -> 'None'`: 
- `check_process_terminate() -> 'None'`: 
- `run_checks(checks: 'list[Check]', out: 'Callable[[str], None]' = <built-in function print>) -> 'bool'`: 
- `run_selftest(checks: 'list[Check] | None' = None, out: 'Callable[[str], None]' = <built-in function print>) -> 'int'`: 
- `run_gui_check() -> 'int'`: Open a window for half a second on the real display, then close it.

## sim

### `engstudio.sim`


### `engstudio.sim.blocks`

Block library framework and math blocks (Phase 7, S2).

- `BLOCK_TYPES` (dict)
- class `BlockImpl(p: 'dict[str, object]') -> 'None'`: Runtime behaviour of one block instance (subclasses override what they need).
  - methods: sample, update, after_step, memory, restore, initial_state, outputs, derivatives, breakpoints
- class `BlockType(name: 'str', category: 'str', kind: 'str', params: 'tuple[ParamSpec, ...]', n_inputs: 'Callable[[dict], int]', n_outputs: 'Callable[[dic...`: BlockType(name: 'str', category: 'str', kind: 'str', params: 'tuple[ParamSpec, ...]', n_inputs: 'Callable[[dict], int]', n_outputs: 'Callable[[dict], int]', feedthrough: 'bool | Callable[[dict], bool]', impl: 'Callable[[dict], BlockImpl]', doc: 'str' = '', extra_check: 'Callable[[str, dict], None] | None' = None)
- class `ParamSpec(name: 'str', default: 'object', kind: 'str' = 'number', choices: 'tuple[str, ...]' = (), positive: 'bool' = False, doc: 'str' = '') -> None`: ParamSpec(name: 'str', default: 'object', kind: 'str' = 'number', choices: 'tuple[str, ...]' = (), positive: 'bool' = False, doc: 'str' = '')
  - methods: check
- `block_type(name: 'str') -> 'BlockType'`: 
- `feedthrough(block: 'Block') -> 'bool'`: True if the block's outputs depend directly on its current inputs.
- `ports(block: 'Block') -> 'tuple[int, int]'`: (inputs, outputs) of ``block``.
- `register(bt: 'BlockType') -> 'BlockType'`: 
- `register_ports_hook(type_name: 'str', fn: 'Callable[[Block], tuple[int, int]]') -> 'None'`: Port counts computed from the block itself (Subsystem: from its inner model).
- `resolve(block: 'Block') -> 'dict[str, object]'`: Checked parameters of ``block``: defaults overridden by the model's values.

### `engstudio.sim.blocks_continuous`

Continuous-time blocks (Phase 7, S4): Integrator, TransferFcn, StateSpace, Derivative.

- `CONTINUOUS_TYPES` (tuple)
- `tf_to_ss(num: 'np.ndarray', den: 'np.ndarray') -> 'tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]'`: Controllable canonical form of num(s)/den(s) (coefficients highest power first).

### `engstudio.sim.blocks_discrete`

Discrete-time blocks (Phase 7, S8): UnitDelay, ZeroOrderHold, DiscreteTransferFcn, DiscreteIntegrator.

- `DISCRETE_TYPES` (tuple)

### `engstudio.sim.blocks_nonlinear`

Nonlinear and control blocks (Phase 7, S9-S10): Saturation, DeadZone, Relay, Switch, Fcn, PIDController, TransportDelay.

- `NONLINEAR_TYPES` (tuple)
- `compile_expression(text: 'str')`: MATLAB-style expression of u and t -> function(t, u_vector) -> float.

### `engstudio.sim.blocks_sinks`

Sink blocks (Phase 7, S7): Scope, ToWorkspace, Display, Terminator.

- `SINK_TYPES` (tuple)

### `engstudio.sim.blocks_sources`

Source blocks (Phase 7, S3): Step, SineWave, Ramp, Clock, PulseGenerator, FromWorkspace.

- `SOURCE_TYPES` (tuple)

### `engstudio.sim.compiler`

Model compiler (Phase 7, S5): turns a ``Model`` into something the runner can execute.

- class `CompiledBlock(id: 'str', type: 'str', name: 'str', impl: 'BlockImpl', n_in: 'int', n_out: 'int', inputs: 'list[tuple[int, int]]', state: 'slice', feed...`: CompiledBlock(id: 'str', type: 'str', name: 'str', impl: 'BlockImpl', n_in: 'int', n_out: 'int', inputs: 'list[tuple[int, int]]', state: 'slice', feedthrough: 'bool', params: 'dict')
- class `CompiledModel(model: 'Model', blocks: 'list[CompiledBlock]', n_states: 'int', x0: 'np.ndarray') -> None`: CompiledModel(model: 'Model', blocks: 'list[CompiledBlock]', n_states: 'int', x0: 'np.ndarray')
  - methods: index, breakpoints, sample_times
- `compile_model(model: 'Model') -> 'CompiledModel'`: 
- `load_library() -> 'None'`: Import every block module so all block types are registered.

### `engstudio.sim.model`

Simulation model as plain immutable data (Phase 7, S1). No numerics, no Qt.

- `SOLVERS` (tuple)
- class `Block(id: 'str', type: 'str', name: 'str' = '', params: 'tuple[tuple[str, ParamValue], ...]' = (), position: 'tuple[float, float]' = (0.0, 0.0...`: One block. ``params`` is a tuple of (name, value) pairs (use ``param``/``with_params``);
  - methods: param, with_params
- class `Line(src: 'str', src_port: 'int', dst: 'str', dst_port: 'int', points: 'tuple[tuple[float, float], ...]' = ()) -> None`: A wire from output port ``src_port`` of ``src`` to input port ``dst_port`` of ``dst``.
- class `Model(name: 'str' = 'untitled', blocks: 'tuple[Block, ...]' = (), lines: 'tuple[Line, ...]' = (), settings: 'SolverSettings' = <factory>) -> None`: Model(name: 'str' = 'untitled', blocks: 'tuple[Block, ...]' = (), lines: 'tuple[Line, ...]' = (), settings: 'SolverSettings' = <factory>)
  - methods: block, new_id, inputs_of, add_block, remove_block, update_block, move_block, set_params, connect, disconnect, with_settings
- class `SolverSettings(start_time: 'float' = 0.0, stop_time: 'float' = 10.0, solver: 'str' = 'ode45', rel_tol: 'float' = 0.001, abs_tol: 'float' = 1e-06, max_s...`: SolverSettings(start_time: 'float' = 0.0, stop_time: 'float' = 10.0, solver: 'str' = 'ode45', rel_tol: 'float' = 0.001, abs_tol: 'float' = 1e-06, max_step: 'float' = inf, fixed_step: 'float' = 0.01)
- `param_value(name: 'str', value: 'object') -> 'ParamValue'`: Normalise a block parameter: number, bool, text, or (nested) tuple of numbers.

### `engstudio.sim.runner`

Simulation runner (Phase 7, S6): runs a compiled model and logs its signals.

- class `ScopeData(title: 'str', t: 'np.ndarray', signals: 'list[np.ndarray]') -> None`: ScopeData(title: 'str', t: 'np.ndarray', signals: 'list[np.ndarray]')
- class `SimResult(tout: 'np.ndarray', scopes: 'dict[str, ScopeData]' = <factory>, workspace: 'dict[str, np.ndarray]' = <factory>, outports: 'dict[int, np....`: SimResult(tout: 'np.ndarray', scopes: 'dict[str, ScopeData]' = <factory>, workspace: 'dict[str, np.ndarray]' = <factory>, outports: 'dict[int, np.ndarray]' = <factory>, displays: 'dict[str, np.ndarray]' = <factory>, steps: 'int' = 0, status: 'str' = 'ok')
- class `SimulationCancelled(...)`: 
- `run(model: 'Model | CompiledModel', progress: 'Callable[[float], None] | None' = None, should_stop: 'Callable[[], bool] | None' = None) -> '...`: Simulate ``model``; ``progress(fraction)`` is called now and then and

### `engstudio.sim.serialization`

``.esmodel`` files (Phase 7, S1): JSON with a ``schema_version``; older versions are migrated on load (``_MIGRATIONS``). Writes are atomic. Pure data, no numerics, no Qt.

- `SCHEMA_VERSION` (int)
- `dumps(model: 'Model') -> 'str'`: 
- `from_dict(data: 'dict') -> 'Model'`: 
- `load(path: 'Path | str') -> 'Model'`: 
- `loads(text: 'str') -> 'Model'`: 
- `save(model: 'Model', path: 'Path | str') -> 'Path'`: 
- `to_dict(model: 'Model') -> 'dict'`: 

### `engstudio.sim.subsystems`

Subsystems (Phase 7, S11): a ``Subsystem`` block holds an inner ``Model`` whose ``Inport`` and ``Outport`` blocks (parameter ``Port`` = 1, 2, ...) are the subsystem's ports.

- `flatten(model: 'Model') -> 'Model'`: 
- `subsystem_ports(block: 'Block') -> 'tuple[int, int]'`: (inputs, outputs) of a Subsystem block from its Inport/Outport blocks.

## toolboxes

### `engstudio.toolboxes`

Built-in engineering toolboxes. Listed explicitly (not discovered) so PyInstaller bundles them; the app layer binds their functions into the interpreter.


### `engstudio.toolboxes.aero`

Aerospace toolbox (Phase 8): standard atmosphere, airspeed, lift and drag, range, rockets, orbits.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.aero.functions`

Aerospace: ISA standard atmosphere, airspeed/Mach, lift and drag, stall speed, Breguet range and endurance, rocket equation, and orbital mechanics (circular/escape speeds, Kepler period, Hohmann transfer). SI units.

- `atmosisa(h: 'np.ndarray | float') -> 'tuple'`: International Standard Atmosphere (geopotential altitude 0-84 km), as MATLAB's
- class `Airspeed(mach: 'float', q: 'float', eas: 'float', T0: 'float', p0: 'float') -> None`: Airspeed(mach: 'float', q: 'float', eas: 'float', T0: 'float', p0: 'float')
- `airspeed(V: 'float', h: 'float' = 0.0) -> 'Airspeed'`: Mach number, dynamic pressure, EAS and isentropic stagnation conditions at altitude h.
- `lift_drag(V: 'float', S: 'float', CL: 'float', CD0: 'float' = 0.02, AR: 'float' = 8.0, e: 'float' = 0.8, rho: 'float' = 1.225) -> 'tuple[float, fl...`: Lift and drag with the parabolic drag polar CD = CD0 + CL^2/(pi e AR).
- `stall_speed(W: 'float', S: 'float', CLmax: 'float', rho: 'float' = 1.225) -> 'float'`: Level-flight stall speed sqrt(2 W / (rho S CLmax)).
- `breguet(kind: 'str', LD: 'float', W0: 'float', W1: 'float', c: 'float', V: 'float | None' = None, eta: 'float | None' = None) -> 'float'`: Breguet range (m) or endurance (s). Jets: c is TSFC in 1/s (range needs V). Propeller:
- `rocket_dv(Isp: 'float', m0: 'float', mf: 'float') -> 'float'`: Tsiolkovsky rocket equation dv = Isp g0 ln(m0/mf).
- class `Orbit(v_circular: 'float', v_escape: 'float', period: 'float', radius: 'float') -> None`: Orbit(v_circular: 'float', v_escape: 'float', period: 'float', radius: 'float')
- `orbit(h: 'float', mu: 'float' = 398600441800000.0, R: 'float' = 6371000.0) -> 'Orbit'`: Circular orbit at altitude h above a body (default Earth): speed sqrt(mu/r), escape
- class `Hohmann(dv1: 'float', dv2: 'float', dv_total: 'float', transfer_time: 'float') -> None`: Hohmann(dv1: 'float', dv2: 'float', dv_total: 'float', transfer_time: 'float')
- `hohmann(r1: 'float', r2: 'float', mu: 'float' = 398600441800000.0) -> 'Hohmann'`: Hohmann transfer between circular orbits of radii r1 and r2 (from the body's centre).

### `engstudio.toolboxes.electrical`

Electrical and Electronics toolbox (Phase 8): circuits, AC power, three-phase, op-amps, filters, diodes, 555 timer.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.electrical.functions`

Electrical circuits and electronics: resistor networks, dividers, RC/RL/RLC transients and second-order parameters, AC impedance and power, three-phase power, op-amp gains, RC filters, diode (Shockley), 555 timer. SI units (ohm, F, H, V, A, W, Hz).

- `resistors(R: 'np.ndarray', connection: 'str' = 'series') -> 'float'`: Equivalent resistance of resistors in series (sum) or parallel (1/sum(1/R)).
- `voltage_divider(Vin: 'float', R1: 'float', R2: 'float', Rload: 'float | None' = None) -> 'float'`: Vout across R2 (optionally loaded by Rload in parallel with R2).
- class `Rlc(wn: 'float', zeta: 'float', alpha: 'float', f0: 'float', Q: 'float', bandwidth: 'float', response: 'str') -> None`: Rlc(wn: 'float', zeta: 'float', alpha: 'float', f0: 'float', Q: 'float', bandwidth: 'float', response: 'str')
- `rlc(R: 'float', L: 'float', C: 'float', connection: 'str' = 'series') -> 'Rlc'`: Second-order RLC parameters: wn = 1/sqrt(LC); series zeta = R/2 sqrt(C/L), parallel
- `rc_step(R: 'float', C: 'float', V: 'float', t: 'np.ndarray | float', V0: 'float' = 0.0) -> 'tuple[np.ndarray, np.ndarray]'`: Capacitor charging from V0 towards V through R: vC = V + (V0 - V) e^(-t/RC).
- `rl_step(R: 'float', L: 'float', V: 'float', t: 'np.ndarray | float') -> 'tuple[np.ndarray, np.ndarray]'`: Current build-up in an RL circuit after a step V: i = V/R (1 - e^(-R t/L)).
- `impedance(kind: 'str', value: 'float', f: 'float') -> 'complex'`: Complex impedance at frequency f: R, j w L or 1/(j w C).
- class `AcPower(P: 'float', Q: 'float', S: 'float', pf: 'float', current: 'complex') -> None`: AcPower(P: 'float', Q: 'float', S: 'float', pf: 'float', current: 'complex')
- `ac_power(V: 'float', Z: 'complex') -> 'AcPower'`: Power drawn by impedance Z from an rms voltage V (phase 0): S = V I*.
- `three_phase_power(VL: 'float', IL: 'float', pf: 'float' = 1.0) -> 'tuple[float, float, float]'`: Balanced three-phase: S = sqrt(3) VL IL, P = S pf, Q = S sin(acos pf).
- `opamp_gain(config: 'str', Rf: 'float | None' = None, Rin: 'float | None' = None) -> 'float'`: Ideal op-amp closed-loop gain: inverting -Rf/Rin, non-inverting 1 + Rf/Rin, follower 1,
- `rc_filter(R: 'float', C: 'float', kind: 'str' = 'lowpass', f: 'np.ndarray | float | None' = None) -> 'tuple[float, np.ndarray]'`: First-order RC filter: cut-off fc = 1/(2 pi R C) and the complex response H(f).
- `diode_current(V: 'np.ndarray | float', Is: 'float' = 1e-14, n: 'float' = 1.0, T: 'float' = 300.0) -> 'np.ndarray | float'`: Shockley diode equation I = Is (exp(V/(n VT)) - 1), VT = k T / q.
- class `Timer555(f: 'float', duty: 'float', t_high: 'float', t_low: 'float') -> None`: Timer555(f: 'float', duty: 'float', t_high: 'float', t_low: 'float')
- `timer555(R1: 'float', R2: 'float', C: 'float') -> 'Timer555'`: Astable 555: t_high = ln2 (R1 + R2) C, t_low = ln2 R2 C.

### `engstudio.toolboxes.fluids`

Fluid Mechanics toolbox (Phase 8): Reynolds number, friction factors, pipe losses, Bernoulli, pumps, drag, orifices, channels.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.fluids.functions`

Fluid mechanics: Reynolds number, friction factor, pipe losses, Bernoulli, hydrostatics, pumps, drag, orifice flow, open channels. SI units; water at 20 C: rho = 998 kg/m^3, mu = 1.002e-3 Pa s; g = 9.81 m/s^2.

- `reynolds(V: 'float', D: 'float', rho: 'float' = 998.0, mu: 'float' = 0.001002) -> 'float'`: Reynolds number Re = rho V D / mu (water at 20 C by default).
- `friction_factor(Re: 'float', rel_roughness: 'float' = 0.0, method: 'str' = 'colebrook') -> 'float'`: Darcy friction factor: 64/Re for laminar flow (Re < 2300), else Colebrook-White (solved
- class `PipeFlow(Re: 'float', f: 'float', hf: 'float', dp: 'float', V: 'float', regime: 'str') -> None`: PipeFlow(Re: 'float', f: 'float', hf: 'float', dp: 'float', V: 'float', regime: 'str')
- `pipe_loss(Q: 'float', D: 'float', L: 'float', roughness: 'float' = 0.0, K_minor: 'float' = 0.0, rho: 'float' = 998.0, mu: 'float' = 0.001002) -> '...`: Darcy-Weisbach head loss hf = (f L/D + sum K) V^2/(2g) for flow Q in a round pipe.
- `bernoulli(p1: 'float', V1: 'float', z1: 'float', V2: 'float', z2: 'float', rho: 'float' = 998.0, head_loss: 'float' = 0.0) -> 'float'`: p2 from p1 + rho V1^2/2 + rho g z1 = p2 + rho V2^2/2 + rho g z2 + rho g hL.
- `hydrostatic(h: 'float', rho: 'float' = 998.0, p0: 'float' = 0.0) -> 'float'`: Pressure at depth h: p = p0 + rho g h (gauge pressure when p0 = 0).
- `pump_power(Q: 'float', H: 'float', efficiency: 'float' = 1.0, rho: 'float' = 998.0) -> 'float'`: Shaft power P = rho g Q H / efficiency.
- `drag_force(Cd: 'float', A: 'float', V: 'float', rho: 'float' = 1.225) -> 'float'`: Drag F = Cd A rho V^2 / 2 (air at sea level by default).
- `orifice_flow(Cd: 'float', A: 'float', dp: 'float', rho: 'float' = 998.0, beta: 'float' = 0.0) -> 'float'`: Q = Cd A sqrt(2 dp / (rho (1 - beta^4))), beta = d/D (0 for a tank orifice).
- `manning(n: 'float', A: 'float', P: 'float', S: 'float') -> 'float'`: Open-channel flow (SI): Q = (1/n) A R^(2/3) S^(1/2), R = A / P (hydraulic radius).
- `terminal_velocity(m: 'float', Cd: 'float', A: 'float', rho: 'float' = 1.225) -> 'float'`: Falling body: m g = Cd A rho V^2 / 2.

### `engstudio.toolboxes.heat`

Heat Transfer toolbox (Phase 8): conduction, convection, radiation, fins, heat exchangers, lumped transients.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.heat.functions`

Heat transfer: conduction resistances, convection correlations, radiation, fins, heat exchangers (LMTD, effectiveness-NTU), lumped-capacitance transients. SI units (W, m, K).

- `conduction_resistance(geometry: 'str', k: 'float', a: 'float', b: 'float', L: 'float' = 1.0) -> 'float'`: Thermal resistance. plane: thickness a, area b. cylinder: radii a < b, length L.
- `convection_resistance(h: 'float', A: 'float') -> 'float'`: R = 1 / (h A).
- `radiation(emissivity: 'float', A: 'float', Ts: 'float', Tsur: 'float') -> 'tuple[float, float]'`: Net radiation q = eps sigma A (Ts^4 - Tsur^4) and the radiation coefficient h_rad.
- `nusselt(correlation: 'str', Re: 'float', Pr: 'float', heating: 'str' = 'heating') -> 'float'`: Average Nusselt number: tube flow (Dittus-Boelter, n = 0.4 heating / 0.3 cooling;
- class `Fin(efficiency: 'float', q: 'float', m: 'float') -> None`: Fin(efficiency: 'float', q: 'float', m: 'float')
- `fin(h: 'float', k: 'float', P: 'float', Ac: 'float', L: 'float', dT: 'float') -> 'Fin'`: Straight fin with an adiabatic tip (corrected length Lc = L + Ac/P): efficiency
- `lmtd(Th_in: 'float', Th_out: 'float', Tc_in: 'float', Tc_out: 'float', flow: 'str' = 'counter') -> 'float'`: Log-mean temperature difference for counter- or parallel-flow exchangers.
- `effectiveness_ntu(NTU: 'float', Cr: 'float', flow: 'str' = 'counter') -> 'float'`: epsilon(NTU, Cr = Cmin/Cmax) for counter- or parallel-flow exchangers.
- class `Lumped(T: 'np.ndarray', tau: 'float', Bi: 'float', valid: 'bool') -> None`: Lumped(T: 'np.ndarray', tau: 'float', Bi: 'float', valid: 'bool')
- `lumped(T0: 'float', Tinf: 'float', h: 'float', A: 'float', V: 'float', rho: 'float', c: 'float', k: 'float', t: 'np.ndarray | float') -> 'Lumped'`: Lumped-capacitance cooling/heating T(t) = Tinf + (T0 - Tinf) exp(-t/tau); Bi = h (V/A)/k.

### `engstudio.toolboxes.materials`

Materials and Lab Data toolbox (Phase 8): material properties, tensile-test analysis, fatigue, composites.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.materials.functions`

Materials and lab data: a small property database, tensile-test analysis (modulus, 0.2 % offset yield, UTS, elongation, toughness), thermal stress, fatigue (Goodman/Soderberg/Gerber, Basquin) and composite rule of mixtures. SI units (Pa, kg/m^3, 1/K).

- class `Material(name: 'str', E: 'float', nu: 'float', G: 'float', rho: 'float', Sy: 'float', Su: 'float', alpha: 'float', k: 'float', cp: 'float') -> None`: Material(name: 'str', E: 'float', nu: 'float', G: 'float', rho: 'float', Sy: 'float', Su: 'float', alpha: 'float', k: 'float', cp: 'float')
- `material(name: 'str') -> 'Material'`: Typical properties of a common engineering material (E, nu, G, rho, Sy, Su, alpha, k,
- class `Tensile(E: 'float', Sy: 'float', Su: 'float', elongation: 'float', toughness: 'float', resilience: 'float', strain_at_Su: 'float') -> None`: Tensile(E: 'float', Sy: 'float', Su: 'float', elongation: 'float', toughness: 'float', resilience: 'float', strain_at_Su: 'float')
- `tensile_test(strain: 'np.ndarray', stress: 'np.ndarray', elastic_limit: 'float | None' = None, offset: 'float' = 0.002) -> 'Tensile'`: Analyse a stress-strain curve (e.g. lab data from readmatrix). E is the least-squares
- `thermal_stress(E: 'float', alpha: 'float', dT: 'float', restraint: 'float' = 1.0) -> 'float'`: Stress in a bar restrained against thermal growth: sigma = -restraint E alpha dT
- `fatigue_sf(sa: 'float', sm: 'float', Se: 'float', Su: 'float', Sy: 'float | None' = None, criterion: 'str' = 'goodman') -> 'float'`: Fatigue safety factor for alternating sa and mean sm stress: Goodman 1/n = sa/Se + sm/Su,
- `basquin_life(sa: 'float', sf: 'float', b: 'float' = -0.085) -> 'float'`: Cycles to failure from Basquin's law sa = sf' (2N)^b.
- `rule_of_mixtures(Ef: 'float', Em: 'float', Vf: 'float') -> 'tuple[float, float]'`: Composite moduli: along fibres Vf Ef + (1-Vf) Em (Voigt), across 1/(Vf/Ef + (1-Vf)/Em)

### `engstudio.toolboxes.mechanical`

Mechanical Engineering toolbox (Phase 8): mechanics of materials (sections, stress, Mohr's circle, von Mises, buckling, beams), vibrations (SDOF, forced response, transmissibility, logarithmic decrement, MDOF modes) and machine elements (springs, gears, shafts, four-bar linkages). Every function validates its arguments through ``@tb_function``.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a ``core.registry.Registry``.

### `engstudio.toolboxes.mechanical.machines`

Machine elements and mechanisms: helical springs, gear pairs, shafts, four-bar linkage.

- `fourbar(a: 'float', b: 'float', c: 'float', d: 'float', theta2: 'float', omega2: 'float' = 0.0, branch: 'str' = 'open') -> 'FourBar'`: Four-bar linkage position and velocity analysis (Norton's notation): ground d, input
- `gear_pair(N1: 'int', N2: 'int', module: 'float', w1: 'float' = 0.0, T1: 'float' = 0.0) -> 'GearPair'`: Spur gear pair: pitch diameters d = m N, center distance, speed and torque ratio.
- `shaft_diameter(T: 'float', tau_allow: 'float') -> 'float'`: Minimum solid shaft diameter for torque T: d = (16 T / (pi tau_allow))^(1/3).
- `shaft_power(T: 'float', rpm: 'float') -> 'float'`: Power transmitted P = T * omega with omega = 2 pi rpm / 60 (W).
- `spring_helical(d: 'float', D: 'float', n: 'float', G: 'float', F: 'float' = 0.0) -> 'Spring'`: Helical compression spring: wire diameter d, mean coil diameter D, n active coils,

### `engstudio.toolboxes.mechanical.solids`

Mechanics of materials: section properties, stresses, failure criteria, buckling, beams.

- `beam(L: 'float', E: 'float', I: 'float', support: 'str' = 'simply', P: 'np.ndarray | None' = None, a: 'np.ndarray | None' = None, w: 'float' ...`: Statically determinate beam: point loads P at positions a (downward positive) and a
- `buckling_euler(E: 'float', I: 'float', L: 'float', K: 'float' = 1.0) -> 'float'`: Euler critical load Pcr = pi^2 E I / (K L)^2. K: 1 pinned-pinned, 0.5 fixed-fixed,
- `mohr(sx: 'float', sy: 'float', txy: 'float') -> 'Mohr'`: Plane stress: principal stresses, max in-plane shear and principal angle (Mohr's
- `section_circle(d: 'float') -> 'Section'`: Solid circle of diameter d: A, I = pi d^4/64, J = pi d^4/32, ...
- `section_ibeam(bf: 'float', tf: 'float', h: 'float', tw: 'float') -> 'Section'`: Symmetric I-section: flange width bf and thickness tf, overall height h, web tw.
- `section_rect(b: 'float', h: 'float') -> 'Section'`: Rectangle b (width) x h (height): A, Ix, Iy, J (torsion constant), Sx, Sy, rx, ry, c.
- `section_tube(do: 'float', di: 'float') -> 'Section'`: Hollow circle (outer do, inner di).
- `safety_factor(stress: 'float', strength: 'float') -> 'float'`: Factor of safety n = strength / stress (e.g. yield strength / von Mises stress).
- `stress_axial(F: 'float', A: 'float') -> 'float'`: Normal stress sigma = F / A (tension positive).
- `stress_bending(M: 'float', c: 'float', I: 'float') -> 'float'`: Bending stress sigma = M c / I.
- `stress_torsion(T: 'float', r: 'float', J: 'float') -> 'float'`: Shear stress from torsion tau = T r / J (circular shafts).
- `von_mises(sx: 'float', sy: 'float' = 0.0, txy: 'float' = 0.0, sz: 'float' = 0.0, tyz: 'float' = 0.0, tzx: 'float' = 0.0) -> 'float'`: Von Mises equivalent stress (3-D; plane stress when the z terms are omitted).

### `engstudio.toolboxes.mechanical.vibrations`

Mechanical vibrations: single-degree-of-freedom (SDOF) systems and multi-degree-of-freedom (MDOF) modal analysis. Model: m x'' + c x' + k x = F(t). Units SI (kg, N*s/m, N/m, rad/s); frequencies are returned in rad/s (w*) and Hz (f*). Torsional systems work the same way with J, ct, kt in place of m, c, k.

- `log_decrement(x1: 'float', xn: 'float', n: 'int' = 1) -> 'Decrement'`: Damping from two peaks n cycles apart: delta = ln(x1/x(1+n)) / n,
- `modes(M: 'np.ndarray', K: 'np.ndarray') -> 'Modes'`: Undamped modal analysis of M x'' + K x = 0: generalized symmetric eigenproblem
- `sdof(m: 'float', c: 'float', k: 'float') -> 'Sdof'`: Natural frequency, damping ratio, damped frequency and regime of m x'' + c x' + k x = 0.
- `sdof_forced(m: 'float', c: 'float', k: 'float', F0: 'float', w: 'float') -> 'Forced'`: Steady-state response to F0 cos(w t): amplitude, phase lag, magnification factor and
- `sdof_free(m: 'float', c: 'float', k: 'float', x0: 'float', v0: 'float', t: 'np.ndarray | float') -> 'tuple[np.ndarray, np.ndarray]'`: Exact free response x(t), v(t) from x(0) = x0, x'(0) = v0 (all damping regimes).
- `transmissibility(zeta: 'float | np.ndarray', r: 'float | np.ndarray') -> 'float | np.ndarray'`: Displacement/force transmissibility sqrt(1+(2 zeta r)^2) / sqrt((1-r^2)^2+(2 zeta r)^2).

### `engstudio.toolboxes.robotics`

Robotics toolbox (Phase 8): transforms, DH kinematics, planar arms, inverse kinematics, trajectories.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.robotics.functions`

Robotics: rotation matrices and homogeneous transforms, Denavit-Hartenberg forward kinematics (with joint positions for plotting), planar-arm Jacobian, two-link inverse kinematics and joint trajectories (cubic, quintic, trapezoidal velocity). Angles in radians unless the argument says degrees.

- `rotx(theta: 'float') -> 'np.ndarray'`: 3-by-3 rotation about x by theta degrees (as MATLAB's rotx).
- `roty(theta: 'float') -> 'np.ndarray'`: 3-by-3 rotation about y by theta degrees.
- `rotz(theta: 'float') -> 'np.ndarray'`: 3-by-3 rotation about z by theta degrees.
- `transform(R: 'np.ndarray', p: 'np.ndarray') -> 'np.ndarray'`: 4-by-4 homogeneous transform from a rotation R and a translation p.
- `dh(a: 'float', alpha: 'float', d: 'float', theta: 'float') -> 'np.ndarray'`: Standard Denavit-Hartenberg link transform Rz(theta) Tz(d) Tx(a) Rx(alpha) (radians).
- class `Fk(T: 'np.ndarray', position: 'np.ndarray', joints: 'np.ndarray', euler_zyx: 'np.ndarray') -> None`: Fk(T: 'np.ndarray', position: 'np.ndarray', joints: 'np.ndarray', euler_zyx: 'np.ndarray')
- `fkine(dh_table: 'np.ndarray', q: 'np.ndarray', prismatic: 'np.ndarray | None' = None) -> 'Fk'`: Forward kinematics of a serial arm. dh_table rows [a alpha d theta_offset]; q the joint
- `planar_arm(L: 'np.ndarray', q: 'np.ndarray') -> 'tuple[np.ndarray, np.ndarray, np.ndarray]'`: Planar serial arm with revolute joints: joint x, y coordinates (base first, so
- `ik_2link(L1: 'float', L2: 'float', x: 'float', y: 'float', elbow: 'str' = 'down') -> 'tuple[float, float]'`: Inverse kinematics of a planar two-link arm (radians).
- `trajectory(q0: 'float', qf: 'float', tf: 'float', t: 'np.ndarray', kind: 'str' = 'quintic', v_max: 'float | None' = None) -> 'tuple[np.ndarray, np....`: Point-to-point joint trajectory from q0 to qf in tf seconds, at rest at both ends:

### `engstudio.toolboxes.structures`

Structures and FEA toolbox (Phase 8): 2-D trusses, frames and plane-stress plates.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.structures.functions`

2-D finite element analysis: pin-jointed trusses, rigid-jointed frames (with element distributed loads) and plane-stress plates meshed with bilinear Q4 elements (optionally with a central hole) whose node grids plot straight into contourf/surf. Node and element numbers are 1-based, as in MATLAB. SI units.

- class `Truss(u: 'np.ndarray', N: 'np.ndarray', stress: 'np.ndarray', reactions: 'np.ndarray', length: 'np.ndarray') -> None`: Truss(u: 'np.ndarray', N: 'np.ndarray', stress: 'np.ndarray', reactions: 'np.ndarray', length: 'np.ndarray')
- `truss2d(nodes: 'np.ndarray', elements: 'np.ndarray', E: 'np.ndarray | float', A: 'np.ndarray | float', supports: 'np.ndarray', loads: 'np.ndarra...`: Pin-jointed plane truss. nodes: [x y] rows; elements: [node1 node2] rows; E, A: one value
- class `Frame(u: 'np.ndarray', N: 'np.ndarray', V: 'np.ndarray', M: 'np.ndarray', reactions: 'np.ndarray', length: 'np.ndarray') -> None`: Frame(u: 'np.ndarray', N: 'np.ndarray', V: 'np.ndarray', M: 'np.ndarray', reactions: 'np.ndarray', length: 'np.ndarray')
- `frame2d(nodes: 'np.ndarray', elements: 'np.ndarray', E: 'np.ndarray | float', A: 'np.ndarray | float', I: 'np.ndarray | float', supports: 'np.nd...`: Rigid-jointed plane frame (Euler-Bernoulli elements). supports: [node fixX fixY fixRot]
- class `Plate(X: 'np.ndarray', Y: 'np.ndarray', ux: 'np.ndarray', uy: 'np.ndarray', sx: 'np.ndarray', sy: 'np.ndarray', txy: 'np.ndarray', von_mises: ...`: Plate(X: 'np.ndarray', Y: 'np.ndarray', ux: 'np.ndarray', uy: 'np.ndarray', sx: 'np.ndarray', sy: 'np.ndarray', txy: 'np.ndarray', von_mises: 'np.ndarray', max_von_mises: 'float', max_displacement: 'float')
- `plate2d(Lx: 'float', Ly: 'float', t: 'float', E: 'float', nu: 'float', nx: 'int' = 20, ny: 'int' = 10, support: 'str' = 'left', load_edge: 'str'...`: Plane-stress rectangular plate Lx-by-Ly (thickness t) meshed with nx-by-ny Q4 elements.

### `engstudio.toolboxes.thermo`

Thermodynamics toolbox (Phase 8): ideal gas, processes, cycles, COP, entropy.

- `DISPLAY_NAME` (str)
- `FUNCTIONS` (tuple)
- `NAME` (str)
- `register(registry) -> 'None'`: Add every function of this toolbox to a `core.registry.Registry`.

### `engstudio.toolboxes.thermo.functions`

Thermodynamics: ideal gas, processes, cycles, COP, entropy. SI units (Pa, m^3, K, kg, J).

- `ideal_gas(p: 'float | None' = None, V: 'float | None' = None, m: 'float | None' = None, T: 'float | None' = None, R: 'float' = 287.0) -> 'float'`: p V = m R T: give three of p, V, m, T (use [] for the unknown); returns the fourth.
- class `Process(p2: 'float', V2: 'float', T2: 'float', W: 'float', Q: 'float', dU: 'float') -> None`: Process(p2: 'float', V2: 'float', T2: 'float', W: 'float', Q: 'float', dU: 'float')
- `gas_process(kind: 'str', p1: 'float', V1: 'float', V2: 'float', m: 'float' = 1.0, n: 'float' = 1.3, R: 'float' = 287.0, cv: 'float' = 717.5000000000...`: Closed-system ideal-gas process from (p1, V1) to volume V2 ("isochoric" has no volume
- class `Cycle(efficiency: 'float', T_max: 'float', work_ratio: 'float') -> None`: Cycle(efficiency: 'float', T_max: 'float', work_ratio: 'float')
- `cycle_efficiency(kind: 'str', a: 'float', b: 'float' = 1.0, k: 'float' = 1.4) -> 'Cycle'`: Thermal efficiency: 'carnot' (a = T_hot, b = T_cold in K), 'otto' (a = compression ratio
- `cop(kind: 'str', T_cold: 'float', T_hot: 'float') -> 'float'`: Ideal (Carnot) coefficient of performance of a refrigerator or heat pump.
- `entropy_change(T1: 'float', T2: 'float', p1: 'float', p2: 'float', m: 'float' = 1.0, cp: 'float' = 1004.5000000000001, R: 'float' = 287.0) -> 'float'`: Ideal gas: dS = m (cp ln(T2/T1) - R ln(p2/p1)).
- `isentropic_temperature(T1: 'float', pressure_ratio: 'float', k: 'float' = 1.4) -> 'float'`: T2 = T1 (p2/p1)^((k-1)/k) for an isentropic ideal-gas process.

## version

### `engstudio.version`

Single source of truth for application name and version.
