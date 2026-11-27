"""Mark B2b-3 as verified in the docs. Idempotent."""
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "docs" / "project"
EDITS = {
    "TASKS.md": [("ode15s, fminsearch, fsolve (pending user run)",
                  "ode15s, fminsearch, fsolve (verified 2026-11-25, 1852 tests)")],
    "TEST_STATUS.md": [("PENDING user run (`python -m pytest -q`, `ruff check .`).",
                        "VERIFIED 2026-11-25: 1852 passed.")],
    "HANDOFF.md": [("Pending user run. Next: B2b-4",
                    "Verified 2026-11-25 (1852 tests). Next: B2b-4")],
}
for name, pairs in EDITS.items():
    path = D / name
    if not path.exists():
        print(f"SKIP (missing): {name}")
        continue
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    for old, new in pairs:
        text = text.replace(old, new)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
    print(f"patched: {name}")
