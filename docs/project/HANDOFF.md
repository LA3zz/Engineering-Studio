# HANDOFF
Last updated: 2026-11-27, version 0.6.0: Phases 1-6 done, P10a done, B2b closed.
Full history: CHANGELOG.md and TASKS.md. The long pre-Phase-5 handoff is in the backup zip
`es_snapshot_before_P5_2.zip` (docs/project/HANDOFF.md).

## Resume in a new chat
Paste NEW_CHAT_PROMPT.md, attach this file + TASKS.md + only the files named in "Next task".

## State
- Project: C:\Users\ma704\Downloads\EngineeringStudio, venv `.venv`, Python 3.11.9, Windows.
- Done: engine (E1-E12: linalg, decomp, calculus, roots, interp, regression, optimize, stats,
  ode, transforms, symbolic, uncertainty), interpreter (lexer, parser, evaluator, functions,
  control flow, ~300 builtins), in-process kernel (worker thread, Stop, F5/F9), GUI (Command
  Window, editor, workspace, folder, toolbox, diagnostics, docs, themes), plotting (Phase 5),
  control systems (Phase 6: `control.lti`, `lang.builtins_control` with `LtiValue`,
  `lang.builtins_controlplot`; python-control imported lazily).
- Phase 5 modules: `plotting.model` (FigureSpec/AxesSpec/SeriesSpec/SurfaceSpec/TextSpec),
  `plotting.text` (TeX subset), `plotting.export` (Matplotlib: PNG/SVG/PDF, GIF frames),
  `lang.figstate` (FigureManager, subplot grids), `lang.builtins_plot` (+Publisher throttle),
  `builtins_plotaxes` (labels/axes/set/get), `builtins_plot2d`, `builtins_plot3d`,
  `builtins_plotio` (pause/animatedline/saveas/print/exportgraphics), `gui.plots`
  (PyQtGraph 2-D), `gui.mpl_view` (embedded Matplotlib for 3-D/polar/contour/surface).
- The user's vibrations scripts (Code.m, Lab 3/5/6) run end to end with F5.
- Run GUI: desktop shortcut, or `python -m engstudio.gui [file.m]` (single instance).
  `packaging/install_desktop.ps1` (re)creates shortcuts and Open with. Self-check script:
  `examples/full_feature_test.m` (132 PASS lines, about 10 s); `examples/control_pid_example.m`.

## Release workflow (Phase 10)
- GitHub: https://github.com/LA3zz/Engineering-Studio (branch main). Git = GitHub Desktop's
  git (`%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe`); sign-in via Git
  Credential Manager. Commit and push after every milestone.
- Build: `.\packaging\build.ps1` (dist\EngineeringStudio) then `.\packaging\make_installer.ps1`
  (installer_output\EngineeringStudio-Setup-<version>.exe). Bump `engstudio/version.py` first.
- Publish: GitHub Releases, tag `v<version>`, attach the setup .exe and its .sha256.

## Conventions and gotchas
- Project root holds only README, pyproject, requirements and folders; docs live in docs/project,
  build logs in build/, one-off probe scripts in scripts/probes. Use absolute paths with
  [IO.File] in PowerShell (.NET's current folder differs from PowerShell's).
- PowerShell 5.1: write files UTF-8 without BOM ([IO.File]::WriteAllText + UTF8Encoding($false));
  `>` writes UTF-16. Wrap stderr-writing tools with `cmd /c "... 2>&1"`.
- Delivery for the free chat: zip of new/changed files (Expand-Archive -Force at project root)
  + `patches\apply_*.py` for edits (exact-match, idempotent, `open(..., newline="")`). Copy each
  zip to `C:\Users\ma704\Downloads\EngineeringStudio Backup files`.
- ruff: line length 100, isort ignores case, B008 forbids calls in argument defaults.
- Layers (tests/architecture/test_import_rules.py): gui never imports lang/engine; gui may use
  only `plotting.model`/`plotting.text`; Matplotlib only in `plotting.export` and `gui.mpl_view`.
- Builtin pattern: `xxx_functions(...) -> dict[name, fn(args, nargout) -> list]`; every
  function name in exactly one `_CATEGORIES` entry in `app/kernel/inprocess.py`.
- Command syntax words (`hold on`, `grid on`, `axis tight`, `colormap jet`, ...) are rewritten in
  `inprocess._COMMAND`/`_MIDLINE_WORDS`.
- Figure updates are throttled to 30/s per figure; `drawnow` paces loops, `drawnow limitrate`
  skips frames, the kernel flushes the last frame when a run ends. Closing a figure window
  tells the kernel (`KernelClient.figure_closed`).
- `Cancelled` passes through builtins (`Interpreter._guard`); long builtins call
  `interp.check_cancel()`.
- GUI tests are headless (QT_QPA_PLATFORM=offscreen); clear `document().setModified(False)`
  before closing editor tabs in fixtures. Qt's "Cannot find font directory" is harmless.

## Next task
Mechanical toolbox done (Phase 8, 2026-11-27): `toolboxes/mechanical` + `app/toolbox_bindings.py`.
New toolboxes follow the same pattern (package with toolbox.toml, FUNCTIONS, register; add the
name to `toolboxes.BUILTIN`).
Phase 7 S5: compiler `sim/compiler.py`: resolve every block (sim.blocks.resolve), check ports
(every input connected, port numbers in range), topological sort of direct-feedthrough blocks,
algebraic-loop error naming the blocks, continuous state-vector layout (offsets per block),
breakpoint collection. Done: S1 model/.esmodel, S2 framework + math, S3 sources (breakpoints),
S4 continuous (Integrator with limits, TransferFcn via own tf_to_ss, StateSpace, Derivative;
`sim.blocks.feedthrough(block)` may depend on parameters). Plan S1-S17 in TASKS.md.
Attach: TASKS.md, ARCHITECTURE.md section 8, `sim/model.py`, `sim/blocks.py`.
Backlogs: Phase 5 (yyaxis, tiledlayout, fill/patch, quiver, stacked bars, colormap matrices,
getframe/movie, Window menu); Phase 6 (MIMO responses, delays, pidTuner, discrete PID);
performance (compile anonymous functions; `sum(x, 'all')`).
## Known problems
- GUI test process sometimes aborts at Qt teardown (0xC0000409); a full single-process run
  hung twice on 2026-11-27 (not reproduced; folder-by-folder runs pass). faulthandler_timeout
  now prints the stack if it happens again.
- GUI not yet in the PyInstaller spec; clean-PC test T2.7b pending (Phase 10).
- Relative file names in saveas/print/exportgraphics use the process working folder, not the
  Current Folder panel (no `cd`/`pwd` yet).
