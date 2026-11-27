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
- [ ] T3.2 `lang.ast` node dataclasses (not started)

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
- [ ] G7 custom theme editor: View > Theme > Customize... with QColorDialog per colour role, live preview, contrast warnings, named custom themes saved in UiSettings, JSON import/export (pure logic module + headless tests); after E12b

### Later phases (the user pastes each phase prompt when it is reached)
- [ ] Phase 4 scripting: AST, parser, interpreter, functions, control flow, error lines,
  real kernel process, Run/F5, conformance tests
- [ ] Phase 5 plotting commands: plot/subplot/xlabel/..., 3D, histogram, contour, surface,
  animation, figure manager (FigureSpec, window and export already exist)
- [ ] Phase 6 control systems and PID
- [ ] Phase 7 simulation environment (17 incremental steps)
- [ ] Phase 8 engineering toolboxes (one at a time)
- [ ] Phase 9 integration and quality assurance
- [ ] Phase 10 packaging (GUI in the PyInstaller spec, installer, clean-PC test T2.7b)
