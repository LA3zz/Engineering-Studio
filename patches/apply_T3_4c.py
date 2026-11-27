"""Doc sync after T3.4c (lang.interp, linalg-backed division). Exact-match, idempotent.

Run at the project root.
"""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("struct fields (pending user run)", "struct fields (verified 2026-11-21)"),
        ("- [ ] T3.4c evaluator + workspace; `\\`, `/` and negative matrix powers via "
         "engine.linalg (attach linalg.py)",
         "- [x] T3.4c `lang.interp` (Interpreter, Workspace, EvalError, Host) + `\\`, `/`, "
         "integer matrix powers via engine.linalg (pending user run)\n"
         "- [ ] T3.4d `lang.display`: MATLAB-style display of values, anonymous function text"),
    ],
    "HANDOFF.md": [
        ("Next in that series: T3.4c evaluator + workspace.",
         "T3.4c done: `lang.interp` (Interpreter(workspace, functions, host, max_depth): "
         "expressions, nested assignment, calls via `functions[name](args, nargout) -> list`, "
         "anonymous functions with captured variables, end, short-circuit, ans; "
         "Host.display/diagnostic callbacks; EvalError carries SourceLoc). `lang.ops` now binds "
         "`A\\B`, `B/A`, integer `A^n` to engine.linalg (singular raises SingularMatrixError; "
         "ill-conditioned appends a warning Diagnostic; complex matrix division unsupported). "
         "Control flow and user functions raise EvalError until T3.5. "
         "Next in that series: T3.4d `lang.display`, then T3.5 control flow/functions, then "
         "builtins (eig, inv, ...), in-process kernel, Command Window hookup."),
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
