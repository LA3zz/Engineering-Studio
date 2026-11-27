"""Help > Check for updates: version comparison and release parsing (no network in tests)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest

from engstudio.gui.updates import RELEASES_PAGE, is_newer, parse_release


@pytest.mark.parametrize("latest, current, newer", [
    ("v0.7.0", "0.6.0", True), ("0.6.1", "0.6.0", True), ("v1.0", "0.9.9", True),
    ("v0.6.0", "0.6.0", False), ("v0.5.9", "0.6.0", False), ("0.6", "0.6.0", False),
    ("v0.10.0", "0.9.0", True), ("nightly", "0.6.0", False), ("v0.7.0-beta", "0.6.0", True),
])
def test_is_newer(latest, current, newer):
    assert is_newer(latest, current) is newer


def test_parse_release():
    payload = json.dumps({"tag_name": "v0.7.0",
                          "html_url": "https://github.com/x/y/releases/tag/v0.7.0"}).encode()
    assert parse_release(payload) == ("v0.7.0", "https://github.com/x/y/releases/tag/v0.7.0")
    assert parse_release(json.dumps({"tag_name": "v1"}).encode())[1] == RELEASES_PAGE
    with pytest.raises(ValueError):
        parse_release(b"{}")


def test_help_menu_has_check_for_updates(qtbot):
    from engstudio.app.kernel.stub import StubKernelClient
    from engstudio.gui.main_window import MainWindow
    from engstudio.gui.settings import UiSettings

    win = MainWindow(UiSettings(None), StubKernelClient())
    qtbot.addWidget(win)
    help_menu = next(a.menu() for a in win.menuBar().actions() if a.text() == "&Help")
    texts = [a.text() for a in help_menu.actions()]
    assert "Check for &Updates..." in texts and "&About" in texts
