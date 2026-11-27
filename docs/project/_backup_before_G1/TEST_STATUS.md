# TEST_STATUS
Last updated: 2026-11-18 (end of Phase 2)

| Suite | Location | Status |
|---|---|---|
| all tests | pytest -q | 94 passed in 8.98s |
| unit | tests/unit | included above (version, errors/diagnostics, units, plugin/registry, offline guard, selftest) |
| architecture (import rules) | tests/architecture | 17 tests, included above |
| offline guard | tests/conftest.py | active for every test |
| lint | ruff check . | All checks passed |
| frozen smoke (build) | packaging\build.ps1 | PASSED on dev PC: onedir 282 MB; `--version`, `--selftest` (11/11, normal and minimal PATH), `--selftest-gui` all exit 0 |
| frozen startup time | same | selftest wall time 19.4 s first run, 6.3 s on later run (scipy import dominates) |
| clean PC (no Python) | manual | NOT YET DONE (task T2.7b) |
| numerical validation | tests/validation | not created |
| interpreter conformance | tests/conformance | not created |
| GUI (pytest-qt, offscreen) | tests/gui | not created |
| integration (kernel e2e) | tests/integration | not created |

Environment: Windows 10 (build 26300), Python 3.11.9. See DEPENDENCIES.md for versions.