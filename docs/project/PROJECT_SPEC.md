# PROJECT_SPEC — Engineering Studio (working name)

Status: Phase 1 (architecture) complete. Version of this doc: 1.0

## 1. Goal
Offline Windows desktop engineering environment inspired by MATLAB/Simulink workflow: command window, workspace, script editor, plotting, toolboxes, block-diagram simulation. No cloud, no API keys, no internet for normal operation. No MATLAB/Simulink branding or assets. No claim of full MATLAB compatibility.

## 2. Non-negotiable principles
1. Never fabricate numerical results. Errors over silent wrong answers.
2. Engine, interpreter, simulation, GUI are independent (see ARCHITECTURE.md layers).
3. SI units by default; conversions explicit.
4. Every numerical function has tests against independently known results.
5. One milestone at a time; no unrelated rewrites; no removal of features without permission.
6. Established libraries (NumPy/SciPy/SymPy/python-control) over custom algorithms.

## 3. Target users
University engineering students; lab analysis; technical projects.

## 4. Scope by area
| Area | v1 target | Later |
|---|---|---|
| Computation engine | linalg, complex, diff/integration, root finding, ODE, interpolation, regression, fitting, optimization, statistics, FFT, Laplace (symbolic) | uncertainty MC, advanced PDE |
| Language | subset defined in §5 | classes, cell/struct completeness, int types |
| Plotting | plot, subplot, title/labels/legend/grid, hold, figure, bar, scatter, semilogx/y, loglog, stem, histogram, surf/contour (3D later) | animation |
| Simulation | continuous + fixed-step discrete, core blocks, scopes, save/load | subsystems, zero-crossing events, code gen (out of scope) |
| Toolboxes | 15 categories, foundational functions first | CFD/FEA/aerospace sims deferred |
| GUI | dockable panels, tabs, dark/light, history | layout presets, plugins UI |

## 5. Language subset v1 (contract)
Supported: numeric/complex/logical/char scalars & N-d arrays (2-D first); literals `[1 2;3 4]`, ranges `a:s:b`; operators `+ - * / \ ^ .* ./ .^ ' .'` and comparison/logical `== ~= < > <= >= & | ~ && ||`; indexing (1-based, `end`, `:`, logical masks, linear & subscript) and indexed assignment with growth; `if/elseif/else`, `for`, `while`, `break`, `continue`, `switch`, `try/catch`; functions in scripts/files (`function [a,b]=f(x,y)`, `nargin/nargout`), anonymous functions `@(x) ...`, handles; strings with single quotes; `disp`, `fprintf`, `error`, `warning`; comments `%`, continuation `...`; command-style calls only for a fixed list (`hold on`, `close all`, `clear`, `clc`, `format`).
Not in v1: classes, packages, global/persistent (candidate v1.1), eval/evalin, integer types, sparse, tables.
Any unsupported construct must produce a clear "not supported" diagnostic with line/column.

## 6. Numerical requirements
Dimension validation, singular/ill-conditioned handling, structured diagnostics, optional calculation trace, uncertainty propagation where appropriate, tolerance documentation per function.

## 7. Offline requirements
Windows installer, no Python needed, bundled docs, local settings/projects, no network calls (enforced by test).

## 8. Files & formats
| Item | Extension/Location |
|---|---|
| Script/function | `.m` (UTF-8) |
| Project | folder with `project.esproj.json` |
| Simulation model | `.esmodel` (JSON, versioned schema) |
| Workspace save | `.esmat` (NumPy `.npz` + JSON manifest) |
| User data | `%APPDATA%\EngineeringStudio\` (SQLite `app.db`, layouts, user toolboxes) |

## 9. Out of scope (until explicitly approved)
CFD, FEA, aerospace simulation, code generation, cloud/collab, Simulink file import, MATLAB toolbox compatibility.
