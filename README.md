# Engineering Studio

An offline, MATLAB-style desktop environment for engineering students, built with Python and Qt.
Write `.m` scripts, run them with F5, and get MATLAB-like output, figures and tools — no
licence server and no internet connection needed.

> Student project, version 0.8.2. Not affiliated with or endorsed by The MathWorks, Inc.;
> MATLAB is a trademark of The MathWorks, Inc.

## Features

- **Language:** MATLAB-like scripts and functions — matrices, indexing, `end`, control flow,
  user functions, anonymous functions, structs, cells, strings, try/catch, command syntax
  (`hold on`, `grid on`, `clear all`).
- **Desktop:** Command Window, tabbed script editor with syntax highlighting, Workspace,
  Current Folder, Toolbox browser, Diagnostics, Documentation, light/dark/custom themes.
- **Math engine:** linear algebra and decompositions, numerical calculus, root finding
  (`fzero`, `fsolve`), interpolation, regression (`polyfit`), optimization (`fminsearch`,
  `linprog`), statistics and t-tests, FFT, ODE solvers (`ode45`, `ode23`, `ode15s` with
  `odeset`), uncertainty propagation.
- **Symbolic math:** `syms`, `diff`, `int`, `limit`, `taylor`, `solve`, `laplace`,
  `ilaplace`, `simplify`, `subs`, `matlabFunction`.
- **Plotting:** `plot`, `subplot`, labels with TeX (`\theta_1`, `m/s^2`), legends, `bar`,
  `stem`, `stairs`, `area`, `scatter`, log plots, `histogram`, `errorbar`, `plot3`, `surf`,
  `mesh`, `contour(f)`, `polarplot`, animation (`drawnow`, `animatedline`), export to PNG,
  SVG, PDF and animated GIF.
- **Control systems:** `tf`, `zpk`, `ss`, `feedback`, `pole`, `damp`, `stepinfo`,
  `margin`, `c2d`, `step`, `impulse`, `lsim`, `bode`, `nyquist`, `rlocus`, `pzmap`, `pid`,
  `pidtune`.
- **Simulation (Simulink-style):** block-diagram editor with drag-and-drop library, wiring,
  parameter dialogs, Run/Stop and Scope windows; 34 blocks (sources, sinks, math, continuous,
  discrete, nonlinear, PID, transport delay, Fcn, subsystems); ode45/ode23/ode15s/ode113/RK4/
  Euler; `sim('model.esmodel')` from scripts.
- **Engineering toolboxes (9 toolboxes, 85 functions):**
  - *Mechanical:* sections, stress, Mohr's circle, von Mises, buckling, beams, vibrations (SDOF,
    forced response, transmissibility, MDOF modes), springs, gears, shafts, four-bar linkages.
  - *Thermodynamics, fluids, heat transfer:* ideal gas, processes, cycles, pipe flow and friction
    factors, Bernoulli, pumps, drag, conduction/convection/radiation, fins, heat exchangers.
  - *Electrical and electronics:* RLC, transients, impedance, AC and three-phase power, op-amps,
    filters, diodes, 555 timer.
  - *Materials and lab data:* property database, tensile-test analysis, fatigue, composites.
  - *Structures and 2-D FEA:* trusses, frames, plane-stress plates (stress contour plots).
  - *Robotics and aerospace:* DH kinematics, inverse kinematics, trajectories, standard
    atmosphere, aircraft performance, rockets and orbits.
- **Lab data files:** `readmatrix`, `readtable`, `writematrix`, `writetable` for CSV and
  Excel; `cd`/`pwd` with the Current Folder as the working folder.

Try `examples/full_feature_test.m` (self-checks across every feature) and the worked examples
in `examples/`: control/PID, simulation (with `examples/models`), mechanical, thermo-fluids,
electrical, FEA, lab data and robotics/aerospace.

## Install (Windows 10/11, 64-bit)

1. Download `EngineeringStudio-Setup-<version>.exe` from
   [Releases](https://github.com/LA3zz/Engineering-Studio/releases).
2. Run it. Windows may say *"Windows protected your PC"* because the installer is not
   code-signed: click **More info → Run anyway**.
3. No administrator rights are needed. Optional: a desktop shortcut and *Open with →
   Engineering Studio* for `.m` files (double-click keeps your default program).

**Updating:** *Help → Check for Updates* (it contacts GitHub only when you click it) offers
**Download and install**: the new installer is downloaded, its checksum is verified, the program
restarts on the new version, and your settings and scripts are kept. (From 0.8.2 on; older
versions open the download page instead.)

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock.txt
pip install -e .
python -m engstudio.gui
```

Tests: `python -m pytest -q` (about 2,500 tests) and `ruff check .`.
Build the app and installer: `.\packaging\build.ps1` then `.\packaging\make_installer.ps1`
(needs Inno Setup 6 or 7).

## Project status

Phases 1–9 are complete (architecture, foundation, math engine, scripting, plotting, control
systems, block-diagram simulation, engineering toolboxes, integration and QA); Phase 10
(packaging) is in progress. Ideas for later: 3-D FEA, more plot types, MIMO control.
Progress and design notes live in `docs/project/` (HANDOFF.md, TASKS.md, CHANGELOG.md).

## License notes

Engineering Studio bundles open-source libraries (NumPy, SciPy, SymPy, Matplotlib, PyQtGraph,
python-control, pandas, Qt for Python/PySide6 under LGPL v3, and others); the installed app
lists them in `THIRD_PARTY_NOTICES.txt`.
