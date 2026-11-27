# HANDOFF
Last updated: 2026-11-27. App version 0.8.2 built (one-click update, figure editing, save/load, tab restore,
faster anonymous functions);
not published yet. Latest published release: 0.8.1 (0.8.0 = pre-release, 0.6.0 = first). Phases 1-10 done (except the clean-PC test
T2.7b, deferred: friends are testing 0.8.1). All tests pass (see TEST_STATUS.md).
Full history: CHANGELOG.md and TASKS.md. Plan and backlogs: ROADMAP.md.

## Resume in a new chat
Paste NEW_CHAT_PROMPT.md, attach this file + TASKS.md + only the files named in "Next task".
For questions about structure attach ARCHITECTURE.md; API_REFERENCE.md (generated) lists every
module, function and signature.

## State
- Project: C:\Users\ma704\Downloads\EngineeringStudio, Windows 11, PowerShell 5.1.
  Python 3.14.10 in `.venv` (old 3.11.9 env kept as `.venv311`; the code still runs on 3.11).
- What the app is: offline MATLAB-style desktop app (PySide6 GUI). Interpreter for `.m`
  scripts (`lang`), math engine (`engine`), plotting (2-D PyQtGraph, 3-D embedded Matplotlib),
  control systems (`control`, python-control), Simulink-style block diagrams (`sim` +
  `gui/sim_editor.py`), 9 engineering toolboxes / 85 functions (`toolboxes/*`), lab data files
  (`app/file_bindings.py`), `save`/`load` .mat (`app/workspace_files.py`), `cd`/`pwd`.
- Kernel: `app/kernel/inprocess.py`, a worker thread in the GUI process (not a separate
  process). GUI talks to it only through `app/kernel/protocol.py` events.
- Help everywhere from one source: `app/help_core.py` (core commands), `app/help_toolbox.py`
  (toolbox input meanings + examples), `app/function_help.py`; shown in the Toolbox details
  pane, by `help name`, as call tips while typing (`gui/calltip.py`) and in the manual.
- User manual: `python tools/make_manual.py` -> docs/manual/Engineering_Studio_User_Manual.pdf
  (chapters in docs/manual/chapters.html; references generated; examples run during the build;
  needs Microsoft Edge). API reference: `python tools/make_api_reference.py`.
- Self-checks: `examples/full_feature_test.m` (~155 PASS lines), `python tools/validate_numerics.py`
  (170/170). Every example script runs in `tests/toolboxes/test_examples_run.py`.
- Run GUI from source: `python -m engstudio.gui [file.m]` (single instance); installed app:
  desktop shortcut. Open script tabs and the Current Folder are restored at start-up.

## Release workflow
- GitHub: https://github.com/LA3zz/Engineering-Studio (branch main). Git = GitHub Desktop's git
  (`%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe`). Commit and push after
  every milestone; zip the changed files to `C:\Users\ma704\Downloads\EngineeringStudio Backup files`.
- New version: bump `src/engstudio/version.py`, rebuild the manual, then `.\packaging\build.ps1`
  (venv active; checks self-test, full_feature_test in the frozen app, GUI smoke) and
  `.\packaging\make_installer.ps1` (Inno Setup 6) -> installer_output\EngineeringStudio-Setup-<v>.exe.
  Copy installer + .sha256 to `Downloads\Apps\Engineering Studio\v<version>\`, manual to
  `Downloads\Apps\Engineering Studio\`.
- Publish (the user clicks Publish): GitHub Releases, tag `v<version>`, attach the setup .exe,
  its .sha256 and the manual PDF; must NOT be a pre-release, or Help > Check for Updates (which
  reads /releases/latest) will not offer it. Keep the installer name
  `EngineeringStudio-Setup-<version>.exe`: the one-click updater (0.8.2+) looks for it, verifies its
  SHA-256 and runs it with `/SILENT /UPDATE` (installer.iss restarts the app after /UPDATE).

## Conventions and gotchas
- Project root: README, pyproject, requirements.lock.txt and folders only; docs in docs/project,
  build logs in build/, one-off probes in scripts/probes.
- PowerShell 5.1: write files UTF-8 without BOM ([IO.File]::WriteAllText + UTF8Encoding($false))
  with absolute paths (.NET's current folder differs from PowerShell's); `>` writes UTF-16.
- ruff: line length 100, isort ignores case, B008 forbids calls in argument defaults.
- Layers (tests/architecture/test_import_rules.py): gui never imports lang/engine/toolboxes;
  gui may use only `plotting.model`/`plotting.text`; Matplotlib only in `plotting.export` and
  `gui.mpl_view`; toolboxes never import each other.
- New builtin: `xxx_functions(...) -> dict[name, fn(args, nargout) -> list]`, name in exactly one
  `_CATEGORIES` entry in `app/kernel/inprocess.py`, and an entry in `app/help_core.py` (a test
  fails otherwise). Command syntax words live in `inprocess._COMMAND` / `_MIDLINE_WORDS`.
- New toolbox function: `@tb_function` in `toolboxes/<name>/functions.py`, add it to
  `FUNCTIONS`, describe every input + an example in `app/help_toolbox.py`, mention it in a docs
  page (tests check all three).
- `Cancelled` passes through builtins; long builtins call `interp.check_cancel()`.
- GUI tests are headless (QT_QPA_PLATFORM=offscreen). Delete widgets you create (or use
  qtbot.addWidget); tests/gui/conftest.py deletes leftovers before Qt shuts down. Run the
  GUI folder and the rest in separate pytest processes. Qt's "Cannot find font directory"
  warning is harmless (set QT_QPA_FONTDIR=C:\Windows\Fonts for readable offscreen screenshots).

## Next task
Nothing scheduled. Wait for feedback from the users of 0.8.1 (fix reported bugs first), then
pick from ROADMAP.md "Possible next steps". Files to attach depend on the task, e.g. a
toolbox bug: the toolbox's functions.py + app/help_toolbox.py; a GUI bug: the gui module.

## Known problems / differences from MATLAB
- Clean-PC test T2.7b not done on a PC without Python (friends' installs will show it).
- `readtable` returns a struct of columns (no table class); no struct arrays, classdef,
  global/persistent, `format long`, multi-output `unique`, generalized `eig(K, M)` (use
  `modes`); symbolic systems use cells `solve({eq1, eq2}, {x, y})`.
- `save` stores logical arrays as numbers; function handles, sym values and systems are skipped.
