"""B1b: doc sync and the one existing GUI test affected by K2 (the new Run menu).

Exact-match, idempotent. Run at the project root.
"""
from pathlib import Path

ROOT = Path(".")
D = ROOT / "docs" / "project"
EDITS = {
    ROOT / "tests" / "gui" / "test_gui_main_window.py": [
        ('    assert titles == ["File", "View", "Help"]\n',
         '    assert titles == ["File", "View", "Run", "Help"]\n'),
    ],
    D / "TASKS.md": [
        ("diagnostics double-click opens the line in the editor (pending user run)",
         "diagnostics double-click opens the line in the editor (verified 2026-11-22)"),
        ("- [ ] B1b builtins part 1b: strings (strcmp, upper, strrep, ...), struct/cell "
         "(struct, fieldnames, cellfun, arrayfun), random, tic/toc, feval (after K1)",
         "- [x] B1b `lang.builtins_text` + `lang.builtins_extra`: strings, struct/cell, "
         "cellfun/arrayfun, feval, sets, operator functions, random, tic/toc "
         "(pending user run)"),
    ],
    D / "HANDOFF.md": [
        ("Command Window input is still one line. Next in that series: B1b (strings, "
         "struct/cell, cellfun/arrayfun, random, tic/toc) and B2b (remaining engine "
         "bindings; attach the engine files).",
         "Command Window input is still one line. B1b done: `lang.builtins_text` (string "
         "functions) and `lang.builtins_extra` (`install_extra(interp)`: struct/fieldnames/"
         "isfield/..., cell/cell2mat/num2cell/deal, cellfun/arrayfun with UniformOutput and "
         "ErrorHandler, feval/func2str/str2func, unique/ismember/nnz, operator functions "
         "plus..colon, rand/randn/randi/randperm/rng with one NumPy generator per "
         "interpreter, tic/toc); installed by InProcessKernelClient with its own toolbox "
         "categories (every function must be in exactly one category). No struct arrays. "
         "Next in that series: B2b (remaining engine bindings: attach engine/calculus.py, "
         "roots.py, regression.py, interp.py, stats.py, ode.py, transforms.py), then Phase 5 "
         "plotting commands; optional K3 multi-line Command Window input."),
    ],
}
for path, pairs in EDITS.items():
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            print(f"{path.name}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"{path.name}: patched")
        else:
            raise SystemExit(f"{path}: expected text not found: {old[:70]!r}")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
