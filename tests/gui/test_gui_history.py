"""CommandHistory tests (no Qt needed)."""

from __future__ import annotations

import pytest

from engstudio.gui.history import CommandHistory


def test_add_ignores_blank_and_immediate_repeat():
    h = CommandHistory()
    for s in ["a = 1", "", "   ", "a = 1", "b = 2", "a = 1"]:
        h.add(s)
    assert h.items() == ["a = 1", "b = 2", "a = 1"]


def test_items_returns_copy():
    h = CommandHistory(["x"])
    h.items().append("y")
    assert h.items() == ["x"]


def test_navigation_with_draft():
    h = CommandHistory(["one", "two", "three"])
    assert h.next() is None  # not navigating
    assert h.previous("draft") == "three"
    assert h.previous("ignored") == "two"
    assert h.previous("ignored") == "one"
    assert h.previous("ignored") is None  # at oldest: stays
    assert h.next() == "two"
    assert h.next() == "three"
    assert h.next() == "draft"  # past newest: draft restored
    assert h.next() is None


def test_empty_history():
    h = CommandHistory()
    assert h.previous("x") is None and h.next() is None


def test_add_resets_navigation():
    h = CommandHistory(["one", "two"])
    assert h.previous("") == "two"
    h.add("three")
    assert h.previous("") == "three"


def test_reset_navigation():
    h = CommandHistory(["one", "two"])
    h.previous("typing")
    h.reset()
    assert h.next() is None
    assert h.previous("new") == "two"


def test_max_size_trims_oldest():
    h = CommandHistory(max_size=3)
    for i in range(5):
        h.add(f"c{i}")
    assert h.items() == ["c2", "c3", "c4"]
    assert CommandHistory(["a", "b", "c", "d"], max_size=2).items() == ["c", "d"]


def test_constructor_filters_bad_items():
    assert CommandHistory(["ok", "", "  ", 5, None, "fine"]).items() == ["ok", "fine"]


def test_invalid_max_size():
    with pytest.raises(ValueError):
        CommandHistory(max_size=0)
