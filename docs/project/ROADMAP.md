# ROADMAP
Each phase = several independently testable tasks (see TASKS.md). Do not start a phase without approval.

| Phase | Name | Exit criteria |
|---|---|---|
| 1 | Architecture & docs | Docs approved. **DONE** |
| 2 | Foundation + packaging spike | Repo scaffold; `core` (errors, diagnostics, units, registry); architecture test; pytest green; frozen "hello" exe runs on a machine without Python, incl. multiprocessing |
| 3 | Interpreter core (headless) | Lexer, parser, evaluator: expressions, matrices, indexing, builtins basic; conformance tests |
| 4 | Kernel + minimal GUI | Kernel process + protocol; main window, Command Window, Workspace browser, history; Stop works |
| 5 | Language completion + editor | Control flow, functions, anonymous functions; Script Editor tabs, run, error panel; Current Folder |
| 6 | Plotting | `FigureSpec` model, figure windows (PyQtGraph), Matplotlib export, core plot commands |
| 7 | Engine breadth | calculus, solvers, ODE, interpolation, regression, optimization, stats, FFT, symbolic; validation suite |
| 8 | Toolbox framework + control | Manifest loader, toolbox browser, docs hook; `control` package; control/PID toolbox |
| 9 | Simulation engine (headless) | Model, compiler, solvers, core blocks, scopes data, save/load, validation vs analytic |
| 10 | Simulation editor GUI | Canvas, drag/drop, wiring, parameters dialogs, run/scope |
| 11 | Foundational toolboxes | Math, mechanical, electrical, electronics, signals, thermo, fluids, heat, materials, structural, optimization, data, robotics, aerospace (basic) |
| 12 | Docs, themes, projects, polish | Documentation panel, search, layouts, themes, project management |
| 13 | Installer & release | Inno Setup installer, clean-VM test, license notices |

Re-sequencing note: packaging is validated in Phase 2 (risk R2) and re-checked at the end of every phase via the smoke build.

Status 2026-11-18: Phase 1 done. Phase 2 done except T2.7b (manual clean-PC check). Phase 3 awaits approval.
