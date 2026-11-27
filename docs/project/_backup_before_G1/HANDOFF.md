# HANDOFF
Last updated: 2026-11-18, end of Phase 2.

## How to resume in a new conversation
Paste the short role/rules prompt, then attach this file, ARCHITECTURE.md, TASKS.md, and only the source files named below.

## State
- Phase 1 (architecture) and Phase 2 (foundation + packaging spike) done, except T2.7b (manual clean-PC test).
- Project: C:\Users\ma704\Downloads\EngineeringStudio, venv `.venv`, Python 3.11.9, Windows 10. Versions: DEPENDENCIES.md, `requirements.lock.txt`.
- Implemented: core.errors, core.diagnostics, core.units, core.plugin, core.registry, selftest, CLI (`--version`, `--selftest`, `--selftest-gui`), offline test guard, architecture import-rule test, PyInstaller spec/build script.
- Frozen build: `.\packaging\build.ps1` (log: build_log.txt). onedir 282 MB; 11/11 selftest checks pass frozen, incl. spawn child + terminate; selftest wall time 19.4 s first run, 6.3 s later (scipy import dominates; use lazy imports in the GUI).
- Decisions in force: Python 3.11, `.m` scripts, kernel in a separate process (D2, not yet implemented), explicit Registry (D9), normalised validated args (D10).

## Conventions and gotchas
- Windows PowerShell 5.1: write files UTF-8 *without BOM* ([IO.File]::WriteAllText with UTF8Encoding($false)); `>` writes UTF-16 (breaks pip -r and TOML). Native tools writing to stderr (PyInstaller) abort scripts under `$ErrorActionPreference="Stop"`; wrap them with `cmd /c "... 2>&1"`.
- ruff isort ignores case (pyqtgraph sorts before PySide6). Line length 100.
- tests/conftest.py blocks non-loopback network; tests that deliberately trigger it use the `blocked_attempts` fixture.
- Architecture test (tests/architecture/test_import_rules.py) holds the layer table; update it together with ARCHITECTURE.md.
- Sandbox used for development has no PowerShell/pytest/PyInstaller: results marked verified only after the user's Windows run.

## Waiting on the user
1. T2.7b: copy `dist\EngineeringStudio` to a PC without Python, run `EngineeringStudio.exe --selftest`, report output.
2. Approve starting Phase 3 (interpreter core).

## Next task (after approval)
**T3.1** `lang.lexer`: tokens for the v1 subset (numbers incl. complex `3i`, identifiers, keywords, operators, single-quote string vs transpose disambiguation, whitespace-sensitive matrix literals, `%` comments, `...` continuation), with SourceLoc on every token and conformance tests. No parser yet.

## Files that matter now
src/engstudio/core/*.py, src/engstudio/selftest.py, src/engstudio/__main__.py, packaging/*, tests/conftest.py, tests/architecture/test_import_rules.py.

## Known problems
None known. Unverified: behaviour on a PC without Python (T2.7b).