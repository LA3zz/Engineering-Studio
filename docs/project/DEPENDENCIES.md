# DEPENDENCIES
Versions pinned 2026-11-18 (Python 3.11.9). Full transitive freeze: `requirements.lock.txt` (UTF-8). Table of direct dependencies at the end of this file.

## Runtime
| Package | Layer/use | License (verify at pin time) | Notes |
|---|---|---|---|
| Python 3.11 (64-bit) | all | PSF | pinned minor version |
| numpy | L0+ | BSD | |
| scipy | engine, sim | BSD | large; lazy-import |
| sympy | engine.symbolic | BSD | slow import; lazy |
| pandas | data | BSD | lazy |
| matplotlib | plotting.export | PSF-based | Agg only, no Qt backend in kernel |
| pyqtgraph | gui.plots | MIT | |
| PySide6 | gui | LGPL-3 | dynamic linking via onedir; ship license text |
| pyvista (+ pyvistaqt, vtk) | gui.plots3d | MIT/BSD | **optional**, added only in 3D task |
| control (python-control) | control | BSD | |
| openpyxl | data | MIT | |
| sqlite3 | data | stdlib | |

## Development / build
| Package | Use |
|---|---|
| pyinstaller | packaging |
| pytest, pytest-qt, pytest-cov | testing |
| ruff | lint/format |
| Inno Setup (external tool) | installer, not a Python dep |

## Policy
- New dependency requires written justification in this file and an ARCHITECTURE.md note.
- Rejected on purpose: Pint (own units module), lark/ply (handwritten parser), QScintilla, QtWebEngine.

## Pinned direct dependencies (2026-11-18)
| Package | Version |
|---|---|
| numpy | 2.4.6 |
| scipy | 1.17.1 |
| sympy | 1.14.0 |
| pandas | 3.1.1 |
| matplotlib | 3.11.2 |
| pyqtgraph | 0.14.0 |
| PySide6 | 6.12.0 |
| control | 0.10.2 |
| openpyxl | 3.1.5 |
| pyinstaller | 6.22.3 |
| pytest | 9.2.0 |
| pytest-qt | 4.5.0 |
| pytest-cov | 7.1.0 |
| ruff | 0.17.5 |
