# FILE_STRUCTURE (target; folders created in T2.1)
```
EngineeringStudio/
├─ pyproject.toml
├─ README.md
├─ requirements.lock.txt              (T2.8)
├─ docs/
│  ├─ project/                        PROJECT_SPEC, ARCHITECTURE, ROADMAP, TASKS, DEPENDENCIES,
│  │                                  FILE_STRUCTURE, API_REFERENCE, CHANGELOG, TEST_STATUS, HANDOFF
│  └─ user/                           end-user documentation (bundled into app)
├─ src/engstudio/
│  ├─ __init__.py  __main__.py  version.py  selftest.py
│  ├─ core/        errors.py diagnostics.py trace.py units.py registry.py plugin.py paths.py logging.py
│  ├─ engine/      linalg.py calculus.py solvers.py ode.py interpolation.py regression.py
│  │               optimize.py stats.py transforms.py symbolic.py uncertainty.py validation.py
│  ├─ control/     models.py pid.py response.py analysis.py
│  ├─ data/        store.py settings.py history.py projects.py io_csv.py io_excel.py workspace_io.py
│  ├─ plotting/    model.py export.py
│  ├─ lang/        lexer.py parser.py ast.py interpreter.py values.py interop.py builtins/ host.py
│  ├─ sim/         model.py blocks/ compiler.py solvers.py runner.py serialization.py
│  ├─ toolboxes/   __init__.py (explicit list)
│  │  ├─ mathematics/ mechanical/ aerospace/ control_pid/ electrical/ electronics/
│  │  ├─ signals/ robotics/ thermodynamics/ fluids/ heat_transfer/ materials/
│  │  └─ structural/ optimization/ data_analysis/     (each: toolbox.toml, __init__, functions, docs/, examples/, tests/)
│  ├─ app/         session.py project_manager.py toolbox_manager.py doc_service.py sim_service.py
│  │  └─ kernel/   protocol.py worker.py client.py inprocess.py
│  └─ gui/         main_window.py docks/ editor/ console/ workspace/ folder/ toolbox_browser/
│                  plots/ sim_editor/ docs_panel/ diagnostics/ themes/ resources.py
├─ resources/      icons/ themes/ docs/ examples/
├─ tests/          unit/ validation/ conformance/ architecture/ gui/ integration/ conftest.py
├─ packaging/      engstudio.spec entry.py installer.iss build.ps1
└─ scripts/        dev helpers
```
Rules: no module in `src` over ~600 lines without review; one responsibility per module; new top-level packages require an ARCHITECTURE.md update.
