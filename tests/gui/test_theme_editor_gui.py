"""Theme editor (G7): dialog and main-window integration. Headless; no colour dialog opened."""

from __future__ import annotations

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest  # noqa: E402
from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402
from engstudio.gui.theme import DARK  # noqa: E402
from engstudio.gui.theme_custom import CustomThemes, make_palette  # noqa: E402
from engstudio.gui.theme_dialog import ThemeDialog  # noqa: E402


def _night_data():
    t = CustomThemes()
    t.set("Night", make_palette("Night", {"accent": "#ff8800"}, DARK), "dark")
    return t.to_data()


@pytest.fixture
def window(qapp):
    win = MainWindow(UiSettings(None))
    yield win
    win.close()


def test_builtin_themes_still_work(window):
    window.set_theme("dark")
    assert window.theme == "dark" and window.base_theme() == "dark"
    with pytest.raises(ValueError):
        window.set_theme("nope")


def test_saved_custom_theme_is_listed_applied_and_restored(qapp):
    settings = UiSettings(None)
    settings.set("custom_themes", _night_data())
    settings.set("theme", "Night")
    win = MainWindow(settings)
    try:
        assert win.theme == "Night" and win.base_theme() == "dark"
        assert win._custom_actions["Night"].isChecked()
        window_colour = QApplication.instance().palette().color(QPalette.ColorRole.Window)
        assert window_colour.name() == DARK.window
        win.toggle_theme()  # a dark-based custom theme toggles to light
        assert win.theme == "light"
    finally:
        win.close()


def test_unknown_saved_theme_falls_back_to_light(qapp):
    settings = UiSettings(None)
    settings.set("theme", "Gone")
    win = MainWindow(settings)
    try:
        assert win.theme == "light"
    finally:
        win.close()


def test_dialog_edit_validate_save_delete(qapp):
    themes = CustomThemes()
    dialog = ThemeDialog(themes, "light")
    previews, changes = [], []
    dialog.preview_requested.connect(previews.append)
    dialog.themes_changed.connect(lambda: changes.append(1))
    dialog.set_role_color("accent", "#F00")
    assert previews[-1].accent == "#ff0000"
    with pytest.raises(ValueError):
        dialog.set_role_color("accent", "zzz")
    dialog.name_edit.setText("Dark")  # reserved
    assert dialog.save_theme() is False and len(themes) == 0
    dialog.name_edit.setText("Mine")
    assert dialog.save_theme() is True and themes.get("Mine").accent == "#ff0000"
    assert changes == [1]
    text = dialog.to_json_text()
    dialog.reset_to_base()
    assert dialog.current_palette().accent != "#ff0000"
    dialog.load_json_text(text)
    assert dialog.current_palette().accent == "#ff0000"
    assert dialog.delete_theme() is True and len(themes) == 0
    dialog.deleteLater()


def test_dialog_contrast_warning(qapp):
    dialog = ThemeDialog(CustomThemes(), "light")
    assert dialog.summary.text() == "No contrast problems."
    dialog.set_role_color("text", "#ffffff")  # white text on a light background
    assert "warning" in dialog.summary.text()
    row = list(dialog._roles).index("text")
    assert "text on base" in dialog.table.item(row, 2).text()
    dialog.deleteLater()


def test_window_saves_and_activates_custom_theme(window):
    dialog = window._make_theme_dialog()
    dialog.set_role_color("accent", "#ff8800")
    dialog.name_edit.setText("Mine")
    assert dialog.save_theme()
    assert window.theme == "Mine" and "Mine" in window._custom_actions
    stored = window.settings.get("custom_themes")
    assert stored["Mine"]["colors"]["accent"] == "#ff8800"
    assert dialog.delete_theme()
    assert window.theme == "light" and "Mine" not in window._custom_actions
    assert "Mine" not in window.settings.get("custom_themes")
    dialog.deleteLater()
