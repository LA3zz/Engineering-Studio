"""Doc sync after T3.4b (lang.indexing). Exact-match, idempotent. Run at project root."""
from pathlib import Path

D = Path("docs") / "project"
EDITS = {
    "TASKS.md": [
        ("concatenation) (pending user run)", "concatenation) (verified 2026-11-21, 1119 tests)"),
        ("- [ ] T3.4b indexing and indexed assignment (`A(i,j)`, `A(i)=x`, `c{i}`, deletion)",
         "- [x] T3.4b `lang.indexing`: indexing, indexed assignment, growth, deletion, `c{i}`, "
         "struct fields (pending user run)"),
    ],
    "HANDOFF.md": [
        ("Next in that series: T3.4b indexing/assignment, then T3.4c evaluator + workspace.",
         "T3.4b done: `lang.indexing` (COLON, index_value, cell_contents, end_value, "
         "assign_index incl. growth and `A(i)=[]` deletion, assign_cell_content, get_field, "
         "set_field; 2-D only, no struct arrays). CharArray keeps char(0) as '' because numpy "
         "drops NUL from '<U1'. Next in that series: T3.4c evaluator + workspace."),
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
