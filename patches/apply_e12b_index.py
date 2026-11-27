"""Link the engine API page from docs_pages/index.md (idempotent, exact match).

Run: python patches\apply_e12b_index.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "src" / "engstudio" / "app" / "docs_pages" / "index.md"
ANCHOR = "- [Layout and themes](layout-and-themes.md)"
NEW = "- [Math engine API](engine-api.md)"


def main() -> int:
    with open(INDEX, encoding="utf-8", newline="") as fh:
        text = fh.read()
    if "engine-api.md" in text:
        print("index.md: already linked, skipped")
        return 0
    if text.count(ANCHOR) != 1:
        sys.exit("index.md: anchor line not found exactly once, nothing changed")
    nl = "\r\n" if "\r\n" in text else "\n"
    tmp = INDEX.with_suffix(".md.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(ANCHOR, ANCHOR + nl + NEW, 1))
    os.replace(tmp, INDEX)
    print("index.md: link added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
