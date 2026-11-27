"""Wire the theme editor (G7) into theme.py and main_window.py. Idempotent, exact-match.

Run: python patches\apply_g7.py   (after the zip is expanded)
All edits are checked first; if any anchor is missing nothing is written. Backs up both files.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUI = ROOT / "src" / "engstudio" / "gui"

THEME_EDITS = [
    ('''           "contrast_ratio", "apply_theme"]
''', '''           "contrast_ratio", "apply_theme", "apply_palette"]
'''),
    ('''def apply_theme(app, name: str) -> None:
    """Apply a theme to a QApplication (Fusion style + palette + stylesheet)."""
    from PySide6.QtGui import QColor, QPalette

    p = get_palette(name)
    role = QPalette.ColorRole
''', '''def apply_theme(app, name: str) -> None:
    """Apply a built-in theme to a QApplication."""
    apply_palette(app, get_palette(name))


def apply_palette(app, p: Palette) -> None:
    """Apply any palette to a QApplication (Fusion style + palette + stylesheet)."""
    from PySide6.QtGui import QColor, QPalette

    role = QPalette.ColorRole
'''),
]

MAIN_EDITS = [
    ('''from engstudio.gui.theme import THEMES, apply_theme, get_palette
''', '''from engstudio.gui.theme import THEMES, apply_palette, apply_theme, get_palette
from engstudio.gui.theme_custom import CustomThemes
from engstudio.gui.theme_dialog import ThemeDialog
'''),
    ('''        self.figures: dict[int, FigureWindow] = {}
''', '''        self.figures: dict[int, FigureWindow] = {}
        self.custom_themes = CustomThemes.from_data(self.settings.get("custom_themes"))
        self._custom_actions: dict[str, QAction] = {}
        self._theme_group: QActionGroup | None = None
        self._themes_menu = None
        self._custom_sep = None
'''),
    ('''        self.set_theme(saved if saved in THEMES else "light", save=False)
''', '''        known = isinstance(saved, str) and (saved in THEMES or saved in self.custom_themes)
        self.set_theme(saved if known else "light", save=False)
'''),
    ('''        group = QActionGroup(self)
''', '''        group = self._theme_group = QActionGroup(self)
'''),
    ('''        self.act_about = self._action("&About", self.show_about)
''', '''        self.act_about = self._action("&About", self.show_about)
        self.act_customize = self._action("&Customize...", self.customize_theme,
                                          tip="Edit colours and save custom themes")
'''),
    ('''        themes = v.addMenu("&Theme")
        themes.addActions(list(self._theme_actions.values()))
        themes.addAction(self.act_toggle_theme)
''', '''        themes = self._themes_menu = v.addMenu("&Theme")
        themes.addActions(list(self._theme_actions.values()))
        self._custom_sep = themes.addSeparator()
        themes.addAction(self.act_toggle_theme)
        themes.addAction(self.act_customize)
        self._rebuild_custom_actions()
'''),
    ('''            window = FigureWindow(spec.number, self.theme, self)
''', '''            window = FigureWindow(spec.number, self.base_theme(), self)
'''),
    ('''    def set_theme(self, name: str, save: bool = True) -> None:
        get_palette(name)  # validates; raises ValueError for unknown names
        apply_theme(QApplication.instance(), name)
        self.theme = name
        self.tabs.set_theme(name)
        for window in self.figures.values():
            window.set_theme(name)
        if self.diagnostics_panel is not None:
            self.diagnostics_panel.set_theme(name)
        if self.docs_panel is not None:
            self.docs_panel.set_theme(name)
        self._theme_actions[name].setChecked(True)
        self.settings.set("theme", name)
        if save:
            self.settings.save()
        self.statusBar().showMessage(f"{name.capitalize()} theme", 3000)

    def toggle_theme(self) -> None:
        self.set_theme("dark" if self.theme == "light" else "light")
''', '''    def base_theme(self) -> str:
        """'light' or 'dark': the built-in theme that panels without custom colours follow."""
        if self.theme in self.custom_themes:
            return self.custom_themes.base_of(self.theme)
        return self.theme

    def set_theme(self, name: str, save: bool = True) -> None:
        custom = name in self.custom_themes
        if custom:
            apply_palette(QApplication.instance(), self.custom_themes.get(name))
            base = self.custom_themes.base_of(name)
        else:
            get_palette(name)  # validates; raises ValueError for unknown names
            apply_theme(QApplication.instance(), name)
            base = name
        self.theme = name
        self.tabs.set_theme(base)
        for window in self.figures.values():
            window.set_theme(base)
        if self.diagnostics_panel is not None:
            self.diagnostics_panel.set_theme(base)
        if self.docs_panel is not None:
            self.docs_panel.set_theme(base)
        action = self._custom_actions.get(name) if custom else self._theme_actions.get(name)
        if action is not None:
            action.setChecked(True)
        self.settings.set("theme", name)
        if save:
            self.settings.save()
        self.statusBar().showMessage(f"{name if custom else name.capitalize()} theme", 3000)

    def toggle_theme(self) -> None:
        self.set_theme("dark" if self.base_theme() == "light" else "light")

    def _make_theme_dialog(self) -> ThemeDialog:
        dialog = ThemeDialog(self.custom_themes, self.theme, self)
        dialog.preview_requested.connect(self._preview_palette)
        dialog.themes_changed.connect(self._persist_custom_themes)
        dialog.theme_activated.connect(self.set_theme)
        return dialog

    def customize_theme(self) -> None:
        dialog = self._make_theme_dialog()
        dialog.exec()
        self.set_theme(self.theme, save=False)  # drop any unsaved live preview
        dialog.deleteLater()

    def _preview_palette(self, palette) -> None:
        apply_palette(QApplication.instance(), palette)

    def _persist_custom_themes(self) -> None:
        self.settings.set("custom_themes", self.custom_themes.to_data())
        self.settings.save()
        self._rebuild_custom_actions()

    def _rebuild_custom_actions(self) -> None:
        menu, group, sep = self._themes_menu, self._theme_group, self._custom_sep
        if menu is None or group is None or sep is None:
            return
        for action in self._custom_actions.values():
            menu.removeAction(action)
            group.removeAction(action)
            action.deleteLater()
        self._custom_actions = {}
        for name in self.custom_themes.names():
            action = self._action(name.replace("&", "&&") + " (custom)",
                                  lambda n=name: self.set_theme(n), checkable=True)
            group.addAction(action)
            menu.insertAction(sep, action)
            action.setChecked(name == self.theme)
            self._custom_actions[name] = action
'''),
]


def _plan(path: Path, edits: list[tuple[str, str]]) -> tuple[str, str, str]:
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    out, todo = text, 0
    for old, new in edits:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in out:
            continue
        if out.count(old) != 1:
            sys.exit(f"{path.name}: anchor not found exactly once, nothing changed:\n{old[:200]}")
        out = out.replace(old, new, 1)
        todo += 1
    return text, out, f"{todo} edit(s)" if todo else "already applied"


def main() -> int:
    plans = {}
    for name, edits in (("theme.py", THEME_EDITS), ("main_window.py", MAIN_EDITS)):
        path = GUI / name
        if not path.is_file():
            sys.exit(f"missing {path}. Nothing changed.")
        plans[path] = _plan(path, edits)
    backup = ROOT / "patches" / f"backup_g7_{time.strftime('%Y%m%d_%H%M%S')}"
    if any(old != new for old, new, _ in plans.values()):
        backup.mkdir(parents=True, exist_ok=True)
    for path, (old, new, summary) in plans.items():
        if old != new:
            shutil.copy2(path, backup / path.name)
            tmp = path.with_suffix(".py.tmp")
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            os.replace(tmp, path)
        print(f"{path.name}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
