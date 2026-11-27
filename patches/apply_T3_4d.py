"""Doc sync after T3.4d (lang.display). Exact-match, idempotent. Run at the project root."""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("integer matrix powers via engine.linalg (pending user run)",
         "integer matrix powers via engine.linalg (verified 2026-11-22)"),
        ("- [ ] T3.4d `lang.display`: MATLAB-style display of values, anonymous function text",
         "- [x] T3.4d `lang.display`: format_value, format_disp, unparse, handle_text "
         "(pending user run)"),
    ],
    "HANDOFF.md": [
        ("Next in that series: T3.4d `lang.display`, then T3.5 control flow/functions, then "
         "builtins (eig, inv, ...), in-process kernel, Command Window hookup.",
         "T3.4d done: `lang.display` (`format_value(name, v)` -> Command Window text, "
         "`format_disp(v)`, `unparse(expr)` with round-trip guarantee, `handle_text`); output "
         "approximates MATLAB format short (rules in the module docstring). Test file names in "
         "tests/lang must differ from tests/engine (no __init__.py): evaluator tests are "
         "test_evaluator.py. Next in that series: T3.5 control flow and user functions, then "
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
