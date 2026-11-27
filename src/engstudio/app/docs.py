"""Local documentation service (G6.2): lists, reads and links Markdown pages.

Pages live in ``engstudio/app/docs_pages`` (flat folder of ``<name>.md``). The location is
found relative to this package, which is valid both in development and in a PyInstaller
build that ships the folder as data under ``engstudio/app/docs_pages``.
"""

from __future__ import annotations

import re
from pathlib import Path

from engstudio.core.errors import ValidationError

__all__ = ["DocService", "default_docs_root", "INDEX"]

INDEX = "index"
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def default_docs_root() -> Path:
    return Path(__file__).resolve().parent / "docs_pages"


class DocService:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else default_docs_root()

    def names(self) -> list[str]:
        """Page names, ``index`` first, the rest alphabetical."""
        if not self.root.is_dir():
            return []
        found = sorted(p.stem for p in self.root.glob("*.md") if _NAME.match(p.stem))
        return ([INDEX] if INDEX in found else []) + [n for n in found if n != INDEX]

    def exists(self, name: str) -> bool:
        return bool(_NAME.match(name)) and (self.root / f"{name}.md").is_file()

    def read(self, name: str) -> str:
        if not self.exists(name):
            raise ValidationError(f"unknown documentation page {name!r}")
        return (self.root / f"{name}.md").read_text(encoding="utf-8")

    def title(self, name: str) -> str:
        for line in self.read(name).splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return name

    def links(self, name: str) -> list[str]:
        return _LINK.findall(self.read(name))

    def resolve(self, href: str) -> str | None:
        """Map a link target to a page name; None for external, unsafe or unknown targets."""
        target = href.split("#", 1)[0].strip()
        if not target or ":" in target or "/" in target or "\\" in target:
            return None
        if target.endswith(".md"):
            target = target[:-3]
        return target if self.exists(target) else None
