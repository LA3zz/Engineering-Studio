# ROADMAP
Status 2026-11-27: version 0.8.1 released (GitHub Releases, latest). Phases 1-9 done, Phase 10
done except the clean-PC test T2.7b (deferred). Details per milestone: TASKS.md.

The original 13-phase plan (Phase 1 design) was re-sequenced on 2026-11-20 into the order the
user's phase prompts followed:

| Phase | Name | Status |
|---|---|---|
| 1 | Architecture & docs | Done |
| 2 | Foundation + packaging spike | Done (T2.7b clean-PC check deferred) |
| G | GUI shell (G1-G7): panels, command window, workspace, folder, toolbox browser, editor, figures, diagnostics, docs, themes | Done |
| 3 | Math engine (E1-E12): linalg, calculus, roots, interpolation, regression, optimisation, stats, ODE, FFT, symbolic, uncertainty | Done |
| 4 | Scripting: lexer, parser, interpreter, builtins, kernel, Run/F5 | Done |
| 5 | Plotting commands (2-D, 3-D, animation, export) | Done |
| 6 | Control systems and PID | Done |
| 7 | Block-diagram simulation (engine + editor GUI) | Done |
| 8 | Engineering toolboxes (9 toolboxes, 85 functions) + lab data files | Done |
| 9 | Integration and QA (examples in tests, Current Folder = working folder, docs checks) | Done |
| 10 | Packaging and release: installer, GitHub, update check, Python 3.14, manual | Done (T2.7b open) |
| Extras | Function help + call tips, user manual PDF, splash, save/load workspace, restore tabs | Done |

## Possible next steps (not scheduled; pick with the user)
- Feedback from the first users of 0.8.1 (bugs first).
- Clean-PC test T2.7b on a second PC or VM.
- Plotting backlog: yyaxis, tiledlayout, fill/patch, quiver, stacked bars, colormap matrices,
  getframe/movie, Window menu.
- Control backlog: MIMO responses, time delays, discrete PID, pidTuner-style app.
- Language backlog: struct arrays, `format long`, multi-output `unique`, generalized `eig`,
  `sum(x, 'all')`, faster anonymous functions in ODE loops.
- Toolbox backlog: 3-D FEA, mesh import, modal FEA, steam tables, compressible flow.
- User toolboxes folder (load extra toolboxes from `%APPDATA%`).

Rule kept from Phase 1: one milestone at a time; every phase ends with tests, docs, a commit
and a backup zip.
