"""P5.1 docs patch: appends a section to TASKS, HANDOFF, CHANGELOG, TEST_STATUS (idempotent)."""

from pathlib import Path

D = Path("docs/project")
MARK = "P5.1 figure state"

SECTIONS = {
    "TASKS.md": (
        "\n## Phase 5 progress (P5.1 figure state, 2026-11-26)\n"
        "- Design picks: 1 PyQtGraph 2D + embedded Matplotlib canvas for 3D/contour/polar "
        "(PyVista optional add-on later, only if justified), 2A spec extension, 3A numeric "
        "handles, 4A own TeX subset, 5A throttled drawnow + GIF, 6A separate windows.\n"
        "- [~] P5.1 command layer: figure, gcf, gca, clf, cla, close, hold, ishold, plot, "
        "drawnow (pending user run)\n"
        "- [ ] P5.2 subplot/annotations/axes, P5.3 more 2D types (bar, set needed for Code.m), "
        "P5.4 .. P5.9 as in the Phase 5 prompt\n"
    ),
    "HANDOFF.md": (
        "\n## P5.1 figure state (2026-11-26)\n"
        "- `lang.figstate` (FigureManager, build_series, parse_linespec/color; pure) and "
        "`lang.builtins_plot` (`install_plot(interp, publish, retire)`) added; installed by "
        "InProcessKernelClient after install_sym. `close` is real now (FigureClosed event, "
        "MainWindow.close_figure). FigureSpec gained `name` (window title only). Command "
        "syntax now also works after `;` or `,` (`bar(..); hold on`) and for hold, figure, "
        "clf, cla, drawnow.\n"
        "- Not yet: subplot, bar, set/get, title/labels, grid, legend (P5.2/P5.3). Code.m "
        "needs them, so F5 on the whole file still fails until P5.3.\n"
        "- Handles: figures = number (1..100000); axes/lines > 100000.\n"
        "- Next: P5.2 (needs gui/plot_params.py, plotting/export.py, gui/plots.py).\n"
    ),
    "CHANGELOG.md": (
        "\n## P5.1 figure state (2026-11-26)\n"
        "- Added lang.figstate, lang.builtins_plot; FigureClosed kernel event; FigureSpec.name; "
        "command syntax after separators; `close` no longer a no-op.\n"
    ),
    "TEST_STATUS.md": (
        "\n## P5.1 figure state (2026-11-26)\n"
        "- New: tests/lang/test_figstate.py (27, ran in the sandbox), "
        "tests/lang/test_builtins_plot.py and tests/app/test_kernel_plot.py (written, not run "
        "in the sandbox: it has no lang/engine). Pending: full pytest + ruff on the user's PC.\n"
    ),
}

for name, text in SECTIONS.items():
    path = D / name
    with open(path, encoding="utf-8", newline="") as f:
        current = f.read()
    if MARK in current:
        print(f"already applied: {name}")
        continue
    nl = "\r\n" if "\r\n" in current else "\n"
    with open(path, "a", encoding="utf-8", newline="") as f:
        if current and not current.endswith(("\n", "\r\n")):
            f.write(nl)
        f.write(text.replace("\n", nl))
    print(f"patched: {name}")
