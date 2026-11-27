# TASKS
Legend: [ ] todo, [~] in progress, [x] done

## Phase 1
- [x] T1.1 Architecture design and documentation set

## Phase 2 — Foundation + packaging spike
- [x] **T2.1 Repo scaffold** — pyproject.toml, src layout, empty packages with `__init__.py`, `python -m engstudio --version`, ruff config, pytest config, `.gitignore`
- [x] T2.2 `core.errors` + `core.diagnostics` (+ tests)
- [x] T2.3 `tests/architecture/test_import_rules.py` (AST-based layer check)
- [x] T2.4 `core.units` (SI conversion table, explicit `convert`) + tests vs known factors
- [x] T2.5 `core.registry` + `core.plugin` (toolbox manifest, `@tb_function`) + tests
- [x] T2.6 Test guard: block sockets during tests (offline enforcement)
- [x] T2.7 Packaging spike: PyInstaller onedir "hello" (PySide6 window + multiprocessing child + NumPy/SciPy import), run on machine without Python
- [x] T2.8 Dependency pinning: `requirements.lock.txt`, fill versions in DEPENDENCIES.md

- [ ] T2.7b Clean-PC verification (manual): copy `dist\EngineeringStudio` to a PC without Python, run `EngineeringStudio.exe --selftest`, record the result

## Backlog (not scheduled)
See ROADMAP.md phases 3–13.
