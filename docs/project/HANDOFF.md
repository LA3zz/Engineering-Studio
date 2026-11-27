# HANDOFF
Last updated: 2026-11-27, version 0.8.0: Phases 1-9 done (9 engineering toolboxes, lab data
files, cd/pwd), P10a/P10b done (installer, GitHub). 2502 tests pass, numerics 170/170.
Full history: CHANGELOG.md and TASKS.md. The long pre-Phase-5 handoff is in the backup zip
`es_snapshot_before_P5_2.zip` (docs/project/HANDOFF.md).

## Resume in a new chat
Paste NEW_CHAT_PROMPT.md, attach this file + TASKS.md + only the files named in "Next task".

## State
- Project: C:\Users\ma704\Downloads\EngineeringStudio, venv `.venv`, Python 3.14.10 (old 3.11.9 venv kept as `.venv311`), Windows.
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
- User manual: `python tools/make_manual.py` rebuilds docs/manual/Engineering_Studio_User_Manual.pdf
  (chapters in docs/manual/chapters.html; references generated from app/help_core.py,
  app/help_toolbox.py and the block registry; needs Microsoft Edge; `--html` skips the PDF).
  Function help (Toolbox details pane, `help name`, call tips) uses the same help tables.
  `packaging/install_desktop.ps1` (re)creates shortcuts and Open with. Self-check script:
  `examples/full_feature_test.m` (PASS/FAIL lines, about 10 s); `examples/control_pid_example.m`.

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
Phase 10 wrap-up: publish the 0.8.0 release (with the user: GitHub Releases, tag v0.8.0, attach
installer_output\EngineeringStudio-Setup-0.8.0.exe and its .sha256; 0.7.0 was built but never
released) and the clean-PC test T2.7b (needs a second PC or a VM).
Toolboxes: `toolboxes/<name>` packages (toolbox.toml, `__init__.py` register, `functions.py` with
`@tb_function`); add the name to `toolboxes.BUILTIN`; `app/toolbox_bindings.py` binds them.
Data files and cd/pwd: `app/file_bindings.py`. Every example runs in
`tests/toolboxes/test_examples_run.py`; docs completeness in `tests/app/test_docs_pages.py`.
Backlogs: Phase 5 (yyaxis, tiledlayout, fill/patch, quiver, stacked bars, colormap matrices,
getframe/movie, Window menu); Phase 6 (MIMO responses, delays, pidTuner, discrete PID);
Phase 8 (3-D FEA, mesh import, modal FEA, steam tables, compressible flow); performance
(compile anonymous functions; `sum(x, 'all')`).## Known problems
- GUI test process sometimes aborts at Qt teardown (0xC0000409); a full single-process run
  hung twice on 2026-11-27 (not reproduced; folder-by-folder runs pass). faulthandler_timeout
  now prints the stack if it happens again.
- Clean-PC test T2.7b pending (Phase 10; needs a second PC or a VM).
- `readtable` returns a struct of columns (no table class); `T.Properties` is not available.
