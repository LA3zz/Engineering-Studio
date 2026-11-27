# TASKS
Legend: [ ] todo, [~] in progress, [x] done

## Phase 1
- [x] T1.1 Architecture design and documentation set

## Phase 2 - Foundation + packaging spike
- [x] **T2.1 Repo scaffold** - pyproject.toml, src layout, empty packages with `__init__.py`, `python -m engstudio --version`, ruff config, pytest config, `.gitignore`
- [x] T2.2 `core.errors` + `core.diagnostics` (+ tests)
- [x] T2.3 `tests/architecture/test_import_rules.py` (AST-based layer check)
- [x] T2.4 `core.units` (SI conversion table, explicit `convert`) + tests vs known factors
- [x] T2.5 `core.registry` + `core.plugin` (toolbox manifest, `@tb_function`) + tests
- [x] T2.6 Test guard: block sockets during tests (offline enforcement)
- [x] T2.7 Packaging spike: PyInstaller onedir "hello" (PySide6 window + multiprocessing child + NumPy/SciPy import), run on machine without Python
- [x] T2.8 Dependency pinning: `requirements.lock.txt`, fill versions in DEPENDENCIES.md

- [ ] T2.7b (DEFERRED by user 2026-11-18: repeat on final frozen build incl. GUI) Clean-PC verification (manual): copy `dist\EngineeringStudio` to a PC without Python, run `EngineeringStudio.exe --selftest`, record the result

## Phase 3 - Interpreter core
- [x] T3.1 `lang.lexer` + tests (42 tests, verified 2026-11-18)
- [x] T3.2 `lang.ast` node dataclasses + tests (verified 2026-11-21, 1034 tests)
- [x] T3.3 `lang.parser` + tests (pending user run)
- [x] T3.4a `lang.values` (value model) + `lang.ops` (operators, ranges, concatenation) (verified 2026-11-21, 1119 tests)
- [x] T3.4b `lang.indexing`: indexing, indexed assignment, growth, deletion, `c{i}`, struct fields (verified 2026-11-21)
- [x] T3.4c `lang.interp` (Interpreter, Workspace, EvalError, Host) + `\`, `/`, integer matrix powers via engine.linalg (verified 2026-11-22)
- [x] T3.4d `lang.display`: format_value, format_disp, unparse, handle_text (verified 2026-11-22)
- [x] T3.5 control flow, user functions, cancel(), error stack frames (verified 2026-11-22)
- [x] B1a `lang.builtins_core`: constants, constructors, size/type queries, elementwise math, reductions, sort/find/diff, linalg bindings (inv, det, norm, ...), disp/sprintf/fprintf/num2str/error/warning (verified 2026-11-22)
- [x] B1b `lang.builtins_text` + `lang.builtins_extra`: strings, struct/cell, cellfun/arrayfun, feval, sets, operator functions, random, tic/toc (pending user run)
- [x] B2a `lang.builtins_decomp`: eig, lu, qr, chol, svd (verified 2026-11-22)
- [x] B2b remaining engine bindings (split into slices; closed 2026-11-27)
  - [x] B2b-1 `lang.builtins_poly`: poly, roots, polyval, polyfit; `close` (no-op until Phase 5) and `format short g` accepted (verified 2026-11-24)
  - [x] B2b-2 `lang.builtins_data`: trapz, cumtrapz, interp1, std, var, median, rms, zscore, fft, ifft (verified 2026-11-24, 1837 tests, ruff clean)
  - [x] B2b-3 `lang.builtins_funcs`: fzero, integral/quad/quadgk, integral2, ode45/ode23/ode15s, fminsearch, fsolve (verified 2026-11-25, 1852 tests)
  - [x] B2b-4 `lang.builtins_analysis`: interp2, fminbnd/fminunc, linprog, quantile/prctile, ttest/ttest2 (verified 2026-11-27: full suite + examples/full_feature_test.m)
  - [x] B2b-5 symbolic values + builtins (`SymValue`, `lang.symops`, `lang.builtins_sym`) (verified 2026-11-27); matlabFunction added 2026-11-27
- [x] K1 `app.kernel.inprocess.InProcessKernelClient` (worker thread, cancel, workspace summary, command syntax for clear/clc/format/more, real toolbox list); GUI starts it by default (`--stub` = old stub) (verified 2026-11-22)
- [x] K2 Run Script (F5), Run Selection or Line (F9), Stop (Shift+F5), Run menu and toolbar, running-state tracking in KernelBridge, diagnostics double-click opens the line in the editor (verified 2026-11-22)
- [x] K3 multi-line Command Window input: continuation prompt `...`, Esc cancels, multi-line paste runs as a block (`app.input_state.needs_more`) (pending user run)

## GUI series (G-milestones)
- [x] G1 GUI shell: main window, menus, toolstrip, themes, dockable panels + visibility controls, tabbed script editor (new/open/save), persisted layout (verified 2026-11-18)
- [x] G2.1 Stub kernel interface: protocol, KernelClient, StubKernelClient (30 tests, verified 2026-11-18)
- [x] G2.2 Command Window + KernelBridge + history (210 tests + manual window check verified 2026-11-18)
- [x] G2.3 Workspace browser (227 tests + manual window check verified 2026-11-18)
- [x] G3.1 Current Folder browser (238 tests, verified 2026-11-19)
- [x] G3.2 Toolbox browser (stub catalogue; 254 tests, verified 2026-11-19)
- [x] G4 Script editor syntax highlighting (282 tests, verified 2026-11-19)
- [x] G5.1 Figure data model + FigureUpdate event (324 tests, verified 2026-11-19)
- [x] G5.2 Figure window (354 tests, verified 2026-11-19)
- [x] G5.3 Figure export PNG/SVG/PDF (388 tests, verified 2026-11-19)
- [x] G6.1 Diagnostics panel (412 tests, verified 2026-11-20)
- [x] G6.2 Documentation panel (470 tests, verified 2026-11-20)

## Backlog (not scheduled)
- [ ] Save/Load Workspace (GUI buttons, save/load commands), after the real kernel
- [ ] Restore open script tabs on startup (unscheduled)
- [ ] Find the root cause of the intermittent Qt teardown crash in the GUI test process (workaround in tests/gui/conftest.py) (unscheduled)
See ROADMAP.md phases 3-13.

## Agreed plan (set 2026-11-20)
Order: G6.2 -> Phase 3 math engine -> Phase 4 scripting -> Phase 5 plotting commands ->
Phase 6 control -> Phase 7 simulation -> Phase 8 toolboxes -> Phase 9 integration/QA ->
Phase 10 packaging. Numbering follows the user's phase prompts: the earlier heading
"Phase 3 - Interpreter core" above is the user's Phase 4 (lexer T3.1 is done).
Per milestone: build, user tests on Windows, fix, then update docs. About 3-4 exchanges each.

### Phase 3 - Math engine (package engstudio.engine: pure functions, typed errors, Result
dataclasses per ARCHITECTURE section 6, every result checked against analytic values)
- [x] E1 (verified 2026-11-20, 470 tests) engine scaffold + validation helpers + linear algebra (matrix/vector ops, solve with
  rcond, inv, det, norm, rank, cond)
- [x] E2 (verified 2026-11-20, 510 tests) decompositions + eigenvalues/eigenvectors
- [x] E3 (verified 2026-11-20, 510 tests) numerical differentiation and integration
- [x] E4 (verified 2026-11-20, 548 tests) root finding and equation solving (scalar, systems, polynomials)
- [x] E5 (verified 2026-11-20, 575 tests) interpolation
- [x] E6 (verified 2026-11-20, 599 tests) regression and curve fitting
- [x] E7 (verified 2026-11-20) numerical optimization
- [x] E8 (verified 2026-11-20, 638 tests) statistics
- [x] E9 (verified 2026-11-20, 721 tests) ODE solvers
- [x] E10 (verified 2026-11-20, 765 tests) Fourier transforms/spectral tools
- [x] E11 (verified 2026-11-20, 858 tests) symbolic mathematics (SymExpr: diff, integrate, solve, series, Laplace/inverse)
- [x] E12 (verified 2026-11-21, 901 tests) uncertainty propagation (GUM linear + Monte Carlo)
- [x] E12b (verified 2026-11-21, 928 tests) engine API docs page (app/docs_pages/engine-api.md)
- [x] G7 (verified 2026-11-21, 993 tests) custom theme editor: View > Theme > Customize..., QColorDialog per colour role, live preview, contrast warnings, named custom themes in UiSettings, JSON import/export (gui.theme_custom, gui.theme_dialog)

### Later phases (the user pastes each phase prompt when it is reached)
- [x] (verified 2026-11-26, 1983 tests, validate_numerics 170/170) Phase 4 scripting: AST, parser, interpreter, functions, control flow, error lines,
  real kernel process, Run/F5, conformance tests
- [x] (verified 2026-11-27, 2184 tests) Phase 5 plotting commands (P5.1-P5.5), see below
- [x] Phase 6 control systems and PID (done 2026-11-27). Picks: wrap python-control in
  `engstudio.control` (lazy import: it costs 3 s), own immutable `LtiSystem` data (tf/zpk/ss,
  continuous or discrete, SISO first), interpreter value class for systems, response plots
  through the Phase 5 figure machinery.
  - [x] (2026-11-27) C1 engine `control.lti`: tf/zpk/ss, conversions, series/parallel/feedback, poles,
    zeros, dcgain, damp, stability, step/impulse/initial/lsim, bode/nyquist data, margins,
    stepinfo, c2d, root-locus data, PID (parallel/standard) and pidtune (target phase margin)
  - [x] (2026-11-27) C2 interpreter: system values (class tf/zpk/ss/pid), display, operators, tf, zpk, ss,
    pid, feedback, series, parallel, pole, zero, dcgain, damp, isstable, stepinfo, c2d, tfdata
  - [x] (2026-11-27) C3 plots: step, impulse, initial, lsim, bode, nyquist, rlocus, pzmap, margin
  - [x] (2026-11-27) C4 pidtune command, docs page control-systems.md, examples/control_pid_example.m,
    control section in examples/full_feature_test.m (132 checks)
  - Backlog: MIMO responses, time delays, pid objects/pidTuner app, discrete PID, sisotool
- [~] Phase 7 simulation environment (started 2026-11-27; ARCHITECTURE section 8)
  - [x] (2026-11-27) S1 `sim.model` (Model, Block, Line, SolverSettings) + `sim.serialization` (.esmodel JSON)
  - [x] (2026-11-27) S2 block framework (`sim.blocks`: ports, parameters, kinds) + math blocks: Gain, Sum,
    Product, Constant, Abs, Math Function
  - [x] (2026-11-27) S3 sources: Step, Sine Wave, Ramp, Clock, Pulse Generator, From Workspace
  - [x] (2026-11-27) S4 continuous: Integrator (initial condition, limits), Transfer Fcn, State-Space, Derivative
  - [ ] S5 compiler: validation, topological sort, algebraic-loop error, state-vector layout
  - [ ] S6 solver/runner: solve_ivp variable step + fixed-step RK4/Euler, cancel, progress
  - [ ] S7 sinks: Scope (data), To Workspace, Display; analytic validation suite
  - [ ] S8 discrete: Unit Delay, Zero-Order Hold, Discrete TF; hybrid scheduling
  - [ ] S9 nonlinear: Saturation, Dead Zone, Relay, Switch, MATLAB Function (handle)
  - [ ] S10 control blocks: PID Controller (from control.lti), Transport Delay
  - [ ] S11 subsystems (flatten in the compiler)
  - [ ] S12 kernel integration: `sim('model.esmodel')`, results to workspace, scope figures
  - [ ] S13 GUI canvas: block library, drag and drop, move/select/delete
  - [ ] S14 wiring: ports, lines, branching, routing
  - [ ] S15 block parameter dialogs
  - [ ] S16 Run/Stop toolbar, scope windows, simulation settings
  - [ ] S17 open/save .esmodel, example models (mass-spring-damper, PID loop), docs page
- [~] Phase 8 engineering toolboxes (one at a time)
  - [x] (2026-11-27) Mechanical Engineering: sections, stress, Mohr, von Mises, buckling, beams,
    vibrations (sdof, sdof_free, sdof_forced, transmissibility, log_decrement, modes), springs,
    gears, shafts, four-bar; app/toolbox_bindings.py binds toolboxes into the interpreter
  - [ ] Next toolboxes: thermodynamics, fluids, heat transfer, electrical, materials, structural/FEA (2D)
- [ ] Phase 9 integration and quality assurance
- [~] Phase 10 packaging: [x] P10a desktop shortcut, Open with for .m, single instance (2026-11-27);
  [~] P10b (2026-11-27): GUI in the PyInstaller spec (EngineeringStudio.exe windowed +
  engstudio-console.exe), Inno Setup installer (per user, Open with, uninstaller, notices),
  Help > Check for Updates (GitHub Releases), README, GitHub repo LA3zz/Engineering-Studio;
  [ ] clean-PC test T2.7b (needs a second PC or a VM)
- Backlog: compile anonymous functions for ODE speed; sum/mean/... 'all' option; struct arrays.

## Phase 5 plotting (done 2026-11-27)
- Design picks: 1 PyQtGraph 2D + embedded Matplotlib canvas for 3D/contour/polar, 2A spec
  extension, 3A numeric handles, 4A own TeX subset, 5A throttled drawnow + GIF, 6A separate
  windows.
- [x] P5.1 figure state: figure, gcf, gca, clf, cla, close, hold, ishold, plot, drawnow
- [x] P5.2 subplot (grids, spans, mnp), axes, title, xlabel, ylabel, sgtitle, grid, box, legend,
  xlim, ylim, axis, xticks/yticks, xticklabels/yticklabels, text, set, get; TeX labels
- [x] P5.3 bar (grouped), stem, stairs, area, scatter, semilogx/semilogy/loglog, histogram,
  hist, histcounts; odeset options for ode45/23/15s; deg2rad, rad2deg
- [x] P5.4 plot3, scatter3, surf, mesh, contour, contourf, zlabel, zlim, view, colormap,
  colorbar, shading, polarplot, errorbar, xline, yline (Matplotlib canvas in the window)
- [x] P5.5 animation (30 fps throttle, drawnow pacing, limitrate, pause, animatedline,
  addpoints, clearpoints), saveas, print, exportgraphics (PNG/SVG/PDF, animated GIF),
  figure('Position') sets the window size, closing a window resets that figure in the kernel
- Acceptance met: the user's Code.m (MECH 322) and Lab 3/5/6 scripts run end to end with F5.
- Backlog: yyaxis, tiledlayout, fill/patch, quiver, stacked bars, colormap matrices,
  getframe/movie, Window menu listing figures.