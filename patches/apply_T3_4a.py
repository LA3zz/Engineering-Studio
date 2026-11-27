"""Doc sync after T3.4a (lang.values, lang.ops). Exact-match, idempotent. Run at project root."""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("- [ ] T3.4 interpreter core: value model, evaluator (not started; scope to agree)",
         "- [x] T3.4a `lang.values` (value model) + `lang.ops` (operators, ranges, concatenation) "
         "(pending user run)\n"
         "- [ ] T3.4b indexing and indexed assignment (`A(i,j)`, `A(i)=x`, `c{i}`, deletion)\n"
         "- [ ] T3.4c evaluator + workspace; `\\`, `/` and negative matrix powers via "
         "engine.linalg (attach linalg.py)\n"
         "- [ ] T3.5 control flow, user functions, error lines, builtins; then real kernel"),
    ],
    "HANDOFF.md": [
        ("Next in that series: T3.4 interpreter core (scope to agree).",
         "T3.4a done: `lang.values` (CharArray, CellArray, StructValue, FunctionHandle, "
         "to_value, is_true; 2-D only; values immutable by convention) and `lang.ops` "
         "(binary_op/unary_op/transpose, colon_range, horzcat/vertcat, build_matrix/build_cell; "
         "`/` `\\\\` need scalar divisor and `^` non-negative integer power until T3.4c). "
         "Next in that series: T3.4b indexing/assignment, then T3.4c evaluator + workspace."),
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
