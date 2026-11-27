"""Validation tool fix: vector-norm references must use 1-D arrays. Idempotent."""
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "tools" / "validate_numerics.py"
PAIRS = [
    ('"n", np.linalg.norm(v, 1))', '"n", np.linalg.norm(v.ravel(), 1))'),
    ('"n", np.linalg.norm(v, np.inf))', '"n", np.linalg.norm(v.ravel(), np.inf))'),
]
with open(path, newline="", encoding="utf-8") as fh:
    text = fh.read()
changed = False
for old, new in PAIRS:
    if new in text:
        continue
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one match for {old!r}")
    text = text.replace(old, new)
    changed = True
if changed:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
print("patched: validate_numerics.py" if changed else "already patched: validate_numerics.py")
