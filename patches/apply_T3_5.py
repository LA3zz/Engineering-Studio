"""Doc sync after T3.5 (control flow, user functions). Exact-match, idempotent.

Run at the project root.
"""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("format_value, format_disp, unparse, handle_text (pending user run)",
         "format_value, format_disp, unparse, handle_text (verified 2026-11-22)"),
        ("- [ ] T3.5 control flow, user functions, error lines, builtins; then real kernel",
         "- [x] T3.5 control flow, user functions, cancel(), error stack frames "
         "(pending user run)\n"
         "- [ ] B1 builtins part 1: size/numel/zeros/ones/eye/linspace, elementwise math, "
         "sum/prod/min/max/mean, disp, error, isempty, class, ...\n"
         "- [ ] B2 builtins part 2: engine bindings (eig, inv, det, norm, polyfit, interp1, "
         "trapz, fzero, ode45, ...)\n"
         "- [ ] K1 in-process kernel client + Command Window and Run/F5 hookup "
         "(first usable version)"),
    ],
    "HANDOFF.md": [
        ("Control flow and user functions raise EvalError until T3.5. ", ""),
        ("Next in that series: T3.5 control flow and user functions, then "
         "builtins (eig, inv, ...), in-process kernel, Command Window hookup.",
         "T3.5 done: `lang.interp` runs if/for/while/switch/try/break/continue/return and user "
         "functions (own scope, nargin/nargout/varargin/varargout, recursion, "
         "functions registered before a program runs, EvalError.stack frames, "
         "Interpreter.cancel() from another thread raises Cancelled, "
         "Interpreter.call(f, args, nargout) for Python builtins). `for` materialises its "
         "range (huge ranges hit the 50M element limit). Next in that series: B1 builtins "
         "part 1, B2 engine bindings (eig, inv, ...), K1 in-process kernel + Command Window "
         "hookup (first usable version)."),
    ],
}
for name, pairs in EDITS.items():
    p = D / name
    with open(p, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new and new in text:
            print(f"{name}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"{name}: patched")
        elif not new:
            print(f"{name}: already applied")
        else:
            raise SystemExit(f"{name}: expected text not found: {old[:60]!r}")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
