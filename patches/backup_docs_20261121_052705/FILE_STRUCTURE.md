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


## Added 2026-11-18
- src/engstudio/lang/lexer.py - tokenizer (T3.1)
- src/engstudio/gui/theme.py - palettes, stylesheet, apply_theme
- src/engstudio/gui/settings.py - JSON UI settings
- src/engstudio/gui/panels.py - PanelSpec registry, placeholder panels
- src/engstudio/gui/editor_tabs.py - tabbed script editor
- src/engstudio/gui/main_window.py - MainWindow
- src/engstudio/gui/app_main.py, __main__.py - entry point (`python -m engstudio.gui [--smoke]`)
- tests/lang/test_lexer.py; tests/gui/test_gui_theme.py, test_gui_settings.py, test_gui_main_window.py
- src/engstudio/app/kernel/{__init__,protocol,client,stub}.py; tests/app/test_kernel_stub.py (G2.1)

- src/engstudio/gui/{history,kernel_bridge,command_window}.py; tests/gui/test_gui_{history,command_window}.py; patches/apply_g22_patch.py (G2.2, one-off, can be deleted)

- src/engstudio/gui/{formatting,workspace_panel}.py; tests/gui/test_gui_{formatting,workspace}.py; patches/apply_g23_patch.py (one-off)

- src/engstudio/gui/folder_panel.py
- tests/gui/test_folder_panel.py

- src/engstudio/gui/toolbox_panel.py
- tests/gui/test_gui_toolbox_panel.py
- tests/app/test_kernel_toolboxes.py

- src/engstudio/app/syntax.py
- src/engstudio/gui/highlight_rules.py
- src/engstudio/gui/highlighter.py
- tests/gui/test_highlight_rules.py
- tests/gui/test_gui_highlighter.py
- tests/app/test_syntax_info.py

- src/engstudio/plotting/model.py
- tests/plotting/test_plotting_model.py
- tests/app/test_kernel_figure.py

- src/engstudio/plotting/model.py
- tests/plotting/test_plotting_model.py
- tests/app/test_kernel_figure.py

- src/engstudio/gui/plot_params.py
- src/engstudio/gui/plots.py
- src/engstudio/gui/figure_window.py
- tests/gui/test_plot_params.py
- tests/gui/test_gui_figures.py
- tests/app/test_kernel_demo_plot.py

- src/engstudio/gui/plot_params.py
- src/engstudio/gui/plots.py
- src/engstudio/gui/figure_window.py
- tests/gui/test_plot_params.py
- tests/gui/test_gui_figures.py
- tests/app/test_kernel_demo_plot.py

- src/engstudio/plotting/export.py
- src/engstudio/app/figure_export.py
- tests/plotting/test_plotting_export.py
- tests/app/test_figure_export_app.py
- tests/gui/test_gui_figure_export.py

- src/engstudio/gui/plot_params.py
- src/engstudio/gui/plots.py
- src/engstudio/gui/figure_window.py
- tests/gui/test_plot_params.py
- tests/gui/test_gui_figures.py
- tests/app/test_kernel_demo_plot.py

- src/engstudio/plotting/export.py
- src/engstudio/app/figure_export.py
- tests/plotting/test_plotting_export.py
- tests/app/test_figure_export_app.py
- tests/gui/test_gui_figure_export.py

- src/engstudio/gui/diagnostic_log.py
- src/engstudio/gui/diagnostics_panel.py
- tests/gui/test_diagnostic_log.py
- tests/gui/test_gui_diagnostics_panel.py

- src/engstudio/gui/plot_params.py
- src/engstudio/gui/plots.py
- src/engstudio/gui/figure_window.py
- tests/gui/test_plot_params.py
- tests/gui/test_gui_figures.py
- tests/app/test_kernel_demo_plot.py

- src/engstudio/plotting/export.py
- src/engstudio/app/figure_export.py
- tests/plotting/test_plotting_export.py
- tests/app/test_figure_export_app.py
- tests/gui/test_gui_figure_export.py

- src/engstudio/gui/diagnostic_log.py
- src/engstudio/gui/diagnostics_panel.py
- tests/gui/test_diagnostic_log.py
- tests/gui/test_gui_diagnostics_panel.py

- src/engstudio/gui/plot_params.py
- src/engstudio/gui/plots.py
- src/engstudio/gui/figure_window.py
- tests/gui/test_plot_params.py
- tests/gui/test_gui_figures.py
- tests/app/test_kernel_demo_plot.py

- src/engstudio/plotting/export.py
- src/engstudio/app/figure_export.py
- tests/plotting/test_plotting_export.py
- tests/app/test_figure_export_app.py
- tests/gui/test_gui_figure_export.py

- src/engstudio/gui/diagnostic_log.py
- src/engstudio/gui/diagnostics_panel.py
- tests/gui/test_diagnostic_log.py
- tests/gui/test_gui_diagnostics_panel.py

## Added in G6.2 and E1-E3
- src/engstudio/app/docs.py, src/engstudio/app/docs_pages/*.md (documentation pages)
- src/engstudio/gui/docs_panel.py
- src/engstudio/engine/validation.py, linalg.py, decomp.py, calculus.py
- tests/app/test_docs.py, tests/gui/test_docs_panel.py
- tests/engine/test_engine_validation.py, test_engine_linalg.py, test_engine_decomp.py, test_engine_calculus.py

<!-- docs-catchup E2-E8 -->
## Added in E4-E8 (2026-11-20)
- src/engstudio/engine/roots.py, interp.py, regression.py, optimize.py, stats.py
- tests/engine/test_roots.py, test_interp.py, test_regression.py, test_optimize.py,
  test_stats.py
- scripts/dump_api.py (read-only helper that writes scripts/api_dump.txt; can be deleted)

<!-- docs E9 -->
## Added in E9 (2026-11-20)
- src/engstudio/engine/ode.py
- tests/engine/test_ode.py

<!-- docs E10 -->
## Added in E10 (2026-11-20)
- src/engstudio/engine/transforms.py
- tests/engine/test_transforms.py
