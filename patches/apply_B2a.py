"""Doc sync after B2a (lang.builtins_decomp). Exact-match, idempotent. Run at the project root."""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("GUI starts it by default (`--stub` = old stub) (pending user run)",
         "GUI starts it by default (`--stub` = old stub) (verified 2026-11-22)"),
        ("- [ ] B2 builtins part 2: engine bindings (eig, inv, det, norm, polyfit, interp1, "
         "trapz, fzero, ode45, ...)",
         "- [x] B2a `lang.builtins_decomp`: eig, lu, qr, chol, svd (pending user run)\n"
         "- [ ] B2b remaining engine bindings (trapz, polyfit, interp1, fzero, ode45, fft, "
         "std, ...); attach engine calculus/roots/regression/interp/stats/ode/transforms .py"),
    ],
    "HANDOFF.md": [
        ("Next in that series: K2 (Run/F5 in the script editor, multi-line Command Window "
         "input; attach gui/main_window.py and the editor file), then B1b (strings, "
         "struct/cell, cellfun/arrayfun, random, tic/toc) and B2 engine bindings (eig and the "
         "rest: attach the needed engine/*.py files).",
         "B2a done: `lang.builtins_decomp` (`install_decomp`; eig lu qr chol svd bound to "
         "engine.decomp; real matrices only; symmetric input uses eigh; installed by "
         "InProcessKernelClient in toolbox category 'decomp'). Next in that series: K2 "
         "(Run/F5 in the script editor, multi-line Command Window input, Stop, diagnostics "
         "click-to-line; main_window.py is known, still needed: gui/editor_tabs.py and "
         "gui/diagnostics_panel.py), then B1b (strings, struct/cell, cellfun/arrayfun, "
         "random, tic/toc) and B2b (remaining engine bindings; attach the engine files)."),
    ],
}
for name, pairs in EDITS.items():
    p = D / name
    with open(p, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            print(f"{name}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"{name}: patched")
        else:
            raise SystemExit(f"{name}: expected text not found: {old[:60]!r}")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
