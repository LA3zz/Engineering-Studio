# CHANGELOG
Format: Keep a Changelog style. Newest first.

## [Unreleased]
### Added
- T2.7: packaging spike - `engstudio.selftest` (11 bundle checks incl. spawned child process and terminate), `--selftest`/`--selftest-gui` flags, `packaging/engstudio.spec`, `entry.py`, `build.ps1`. PyInstaller onedir build passes on the dev PC (282 MB).
- T2.8: dependency versions pinned (`requirements.lock.txt` UTF-8, table in DEPENDENCIES.md).
- T2.6: test-session offline guard (`tests/conftest.py`): blocks non-loopback connect/DNS/UDP, records attempts and fails tests that make them (even if the error is swallowed).
- T2.5: `core.plugin` (`@tb_function` with automatic argument validation, `Arg`/`Ret`, `@sim_block` metadata, `toolbox.toml` manifest loader, `PLUGIN_API_VERSION`), `core.registry` (explicit `Registry`), `PluginError`; tests incl. beam-deflection reference case.
- T2.4: `core.units` - explicit unit conversion (exact rational factors, compound expressions, offset temperatures, angle as separate dimension) with tests.
- T2.3: architecture test enforcing layer rules, Qt/matplotlib placement, toolbox isolation and import cycles (checker itself tested on synthetic trees).
- T2.2: `core.errors` (typed error hierarchy) and `core.diagnostics` (Diagnostic, SourceLoc) with unit tests.
- T2.1: repo scaffold (pyproject, src layout, `python -m engstudio --version`, pytest/ruff config).
- Phase 1: architecture design and project documentation set (no application code).
