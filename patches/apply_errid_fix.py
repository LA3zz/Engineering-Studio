"""Fix: error('msg') without identifier must give an empty err.identifier. Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = (
    '                ident = getattr(cause, "identifier", None) or getattr(exc, "code", "") or ""\n'
)
NEW = (
    '                ident = getattr(cause, "identifier", getattr(exc, "identifier", None))\n'
    '                if ident is None:\n'
    '                    ident = getattr(exc, "code", "") or ""\n'
)
path = ROOT / "src/engstudio/lang/interp.py"
with open(path, newline="", encoding="utf-8") as fh:
    text = fh.read()
nl = "\r\n" if "\r\n" in text else "\n"
old, new = OLD.replace("\n", nl), NEW.replace("\n", nl)
if new in text:
    print("already patched: interp.py")
elif text.count(old) != 1:
    raise SystemExit("interp.py: expected exactly one match for the catch identifier line")
else:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    print("patched: interp.py")
