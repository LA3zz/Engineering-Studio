"""The built-in documentation is complete and its links work (Phase 9 QA)."""

import re
from pathlib import Path

import engstudio.app

PAGES = Path(engstudio.app.__file__).parent / "docs_pages"
LINK = re.compile(r"\]\(([^)#]+\.md)(?:#[^)]*)?\)")


def test_every_page_is_linked_from_the_index():
    index = (PAGES / "index.md").read_text(encoding="utf-8")
    linked = set(LINK.findall(index))
    pages = {p.name for p in PAGES.glob("*.md")} - {"index.md"}
    assert pages <= linked, f"pages missing from index.md: {sorted(pages - linked)}"


def test_every_link_resolves_and_pages_link_back():
    for page in PAGES.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            assert (PAGES / target).is_file(), f"{page.name}: broken link to {target}"
        if page.name != "index.md":
            assert "(index.md)" in text, f"{page.name} has no link back to the index"


def test_toolbox_pages_mention_every_function():
    from engstudio.app.toolbox_bindings import toolbox_builtins

    text = "\n".join(p.read_text(encoding="utf-8") for p in PAGES.glob("*.md"))
    builtins, _ = toolbox_builtins()
    missing = [n for n in builtins if f"`{n}" not in text and f"{n}(" not in text]
    assert not missing, f"toolbox functions without documentation: {missing}"
