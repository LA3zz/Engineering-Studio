"""Sync docs after T3.2 (lang.ast). Exact-match, idempotent. Run from the project root."""
from pathlib import Path

D = Path("docs/project")
EDITS = {
    "TASKS.md": [
        ("- [ ] T3.2 `lang.ast` node dataclasses (not started)",
         "- [x] T3.2 `lang.ast` node dataclasses + tests (41 tests; pending user run)\n"
         "- [ ] T3.3 `lang.parser` (Pratt parser: tokens -> AST; not started)"),
    ],
    "HANDOFF.md": [
        ("Next in that series: T3.2 `lang.ast`.",
         "T3.2 `lang.ast` done (frozen slotted nodes, optional keyword-only `loc` ignored by `==`, "
         "`children`/`walk`). Next in that series: T3.3 `lang.parser`."),
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
            raise SystemExit(f"{name}: expected text not found: {old[:50]!r}")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
