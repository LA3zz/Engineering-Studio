"""Write THIRD_PARTY_NOTICES.txt: every installed distribution bundled with the app, with its
version and license as declared in its metadata. Usage:
``python tools/third_party_notices.py dist/EngineeringStudio/THIRD_PARTY_NOTICES.txt``
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

SKIP = {"engstudio", "pytest", "pytest-cov", "pytest-qt", "pluggy", "iniconfig", "coverage",
        "ruff", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
        "pywin32-ctypes", "pyside6-webengine", "pyside6-pdf"}


def license_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    text = meta.get("License-Expression") or meta.get("License") or ""
    text = text.strip().splitlines()[0] if text.strip() else ""
    if not text or len(text) > 80:
        classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or []
                       if c.startswith("License ::")]
        text = ", ".join(classifiers) or (text[:77] + "..." if text else "see project")
    return text


def main(out: str) -> None:
    lines = ["Engineering Studio - third-party software", "",
             f"Python {sys.version.split()[0]} (Python Software Foundation License)", ""]
    rows = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"] or ""
        if not name or name.lower() in SKIP:
            continue
        home = dist.metadata.get("Home-page") or ""
        if not home:
            urls = dist.metadata.get_all("Project-URL") or []
            home = urls[0].split(",", 1)[-1].strip() if urls else ""
        rows.append((name.lower(), f"{name} {dist.version} - {license_of(dist)}"
                     + (f"\n    {home}" if home else "")))
    lines += [text for _, text in sorted(rows)]
    lines += ["", "Each package's full license text is in its *.dist-info folder inside "
              "_internal where provided by the package."]
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(rows)} packages)")


if __name__ == "__main__":
    main(sys.argv[1])
