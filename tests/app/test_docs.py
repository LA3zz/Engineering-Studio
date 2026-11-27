"""DocService tests, including a link check over the shipped pages."""

from __future__ import annotations

import pytest

from engstudio.app.docs import INDEX, DocService, default_docs_root
from engstudio.core.errors import ValidationError


@pytest.fixture
def svc(tmp_path):
    (tmp_path / "index.md").write_text("# Home\n[A](a.md) [B](b)\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("no title here\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Bee\n", encoding="utf-8")
    (tmp_path / "Bad Name.md").write_text("# x\n", encoding="utf-8")
    return DocService(tmp_path)


def test_names_index_first_and_invalid_skipped(svc):
    assert svc.names() == ["index", "a", "b"]


def test_title_and_fallback(svc):
    assert svc.title("index") == "Home"
    assert svc.title("a") == "a"


def test_read_unknown_raises(svc):
    with pytest.raises(ValidationError):
        svc.read("nope")
    with pytest.raises(ValidationError):
        svc.read("../index")


def test_links(svc):
    assert svc.links("index") == ["a.md", "b"]


@pytest.mark.parametrize("href,expected", [
    ("a.md", "a"), ("b", "b"), ("a.md#sec", "a"), ("#sec", None), ("http://x.org/a.md", None),
    ("../a.md", None), ("sub/a.md", None), ("c:\\a.md", None), ("missing.md", None), ("", None),
])
def test_resolve(svc, href, expected):
    assert svc.resolve(href) == expected


def test_missing_root_gives_no_pages(tmp_path):
    assert DocService(tmp_path / "none").names() == []


def test_shipped_docs_are_consistent():
    s = DocService(default_docs_root())
    names = s.names()
    assert names and names[0] == INDEX
    for name in names:
        assert s.read(name).startswith("# "), name
        for href in s.links(name):
            assert s.resolve(href) is not None, f"{name}: broken link {href}"
    linked = {s.resolve(h) for h in s.links(INDEX)}
    assert set(names) - {INDEX} <= linked, "every page must be linked from the index"
