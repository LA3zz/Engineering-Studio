"""Fix ruff B905 in tests/engine/test_interp.py (exact-match, idempotent)."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "tests" / "engine" / "test_interp.py"
with open(p, encoding="utf-8", newline="") as fh:
    t = fh.read()
old = "for a, b in zip((xs, ys, q), snap):"
new = "for a, b in zip((xs, ys, q), snap, strict=True):"
if new in t:
    print("already applied")
elif old in t:
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(t.replace(old, new, 1))
    print("patched")
else:
    raise SystemExit("expected text not found")
