"""Doc sync after B1a (lang.builtins_core). Exact-match, idempotent. Run at the project root."""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("user functions, cancel(), error stack frames (pending user run)",
         "user functions, cancel(), error stack frames (verified 2026-11-22)"),
        ("- [ ] B1 builtins part 1: size/numel/zeros/ones/eye/linspace, elementwise math, "
         "sum/prod/min/max/mean, disp, error, isempty, class, ...",
         "- [x] B1a `lang.builtins_core`: constants, constructors, size/type queries, "
         "elementwise math, reductions, sort/find/diff, linalg bindings (inv, det, norm, ...), "
         "disp/sprintf/fprintf/num2str/error/warning (pending user run)\n"
         "- [ ] B1b builtins part 1b: strings (strcmp, upper, strrep, ...), struct/cell "
         "(struct, fieldnames, cellfun, arrayfun), random, tic/toc, feval (after K1)"),
    ],
    "HANDOFF.md": [
        ("Next in that series: B1 builtins part 1, B2 engine bindings (eig, inv, ...), K1 "
         "in-process kernel + Command Window hookup (first usable version).",
         "B1a done: `lang.builtins_core` (`install_core(interp)`, `core_functions(interp)`, "
         "`format_text` = sprintf engine, `UserError` with identifier; Host gained `write(text)`; "
         "try/catch identifier comes from the underlying error). Complex matrices are not "
         "supported by inv/det/norm/...; min/max reject complex. Next in that series: K1 "
         "in-process kernel + Command Window and Run hookup (first usable version), then B1b "
         "(strings, struct/cell, cellfun/arrayfun, random, tic/toc) and B2 engine bindings "
         "(eig and the rest: attach the needed engine/*.py files)."),
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
