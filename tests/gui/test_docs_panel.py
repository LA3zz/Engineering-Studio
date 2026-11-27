"""Headless tests for the Documentation panel."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from engstudio.app.docs import DocService  # noqa: E402
from engstudio.gui.docs_panel import DocsPanel  # noqa: E402


@pytest.fixture
def panel(tmp_path):
    (tmp_path / "index.md").write_text("# Home\n[A](a.md)\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("# Page A\n[B](b.md)\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Page B\n", encoding="utf-8")
    p = DocsPanel(DocService(tmp_path))
    yield p
    p.close()
    p.deleteLater()


def test_starts_at_index(panel):
    assert panel.current_page == "index"
    assert "Home" in panel.browser.toPlainText()
    assert not panel.back_button.isEnabled() and not panel.forward_button.isEnabled()


def test_link_back_forward_home(panel):
    assert panel.open_link("a.md")
    assert panel.open_link("b.md")
    assert panel.current_page == "b" and panel.can_back()
    assert panel.back() and panel.current_page == "a" and panel.can_forward()
    assert panel.forward() and panel.current_page == "b"
    panel.home()
    assert panel.current_page == "index"
    assert panel.back() and panel.current_page == "b"


def test_new_navigation_clears_forward(panel):
    panel.open_link("a.md")
    panel.back()
    assert panel.can_forward()
    panel.open_link("b.md")
    assert not panel.can_forward()


def test_external_and_unknown_links_ignored(panel):
    assert not panel.open_link("https://example.com")
    assert not panel.open_link("zzz.md")
    assert panel.current_page == "index"


def test_unknown_page_shows_message(panel):
    assert not panel.show_page("zzz")
    assert "Page not found" in panel.browser.toPlainText()
    assert panel.current_page == "index"


def test_back_forward_noop_when_empty(panel):
    assert not panel.back() and not panel.forward()


def test_theme(panel):
    panel.open_link("a.md")
    panel.set_theme("dark")
    assert panel.theme == "dark" and panel.current_page == "a"
    with pytest.raises(ValueError):
        panel.set_theme("pink")
    with pytest.raises(ValueError):
        DocsPanel(theme="pink")


def test_shipped_docs_load():
    p = DocsPanel()
    try:
        assert "Engineering Studio" in p.browser.toPlainText()
    finally:
        p.close()
        p.deleteLater()
