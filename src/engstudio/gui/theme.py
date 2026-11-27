"""Light/dark themes. Palettes and the stylesheet are plain data (no Qt import at module level)."""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

__all__ = ["Palette", "LIGHT", "DARK", "THEMES", "get_palette", "build_stylesheet",
           "contrast_ratio", "apply_theme", "apply_palette"]


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    base: str
    alt_base: str
    text: str
    text_dim: str
    border: str
    accent: str
    accent_text: str
    button: str
    hover: str
    toolbar: str
    selection: str


LIGHT = Palette(
    name="light", window="#f3f4f6", base="#ffffff", alt_base="#f4f6f8", text="#1f2933",
    text_dim="#52606d", border="#c5ccd3", accent="#0b5cad", accent_text="#ffffff",
    button="#e4e7eb", hover="#d3dde8", toolbar="#e9edf1", selection="#cfe3f7",
)
DARK = Palette(
    name="dark", window="#1e2227", base="#14171b", alt_base="#191d22", text="#e4e7eb",
    text_dim="#9aa5b1", border="#3e4650", accent="#4da3ff", accent_text="#0b1620",
    button="#2b313a", hover="#36404b", toolbar="#242a31", selection="#264f78",
)
THEMES = {"light": LIGHT, "dark": DARK}


def get_palette(name: str) -> Palette:
    try:
        return THEMES[name]
    except KeyError:
        raise ValueError(f"unknown theme {name!r}; expected one of {sorted(THEMES)}") from None


_QSS = Template("""
QMainWindow, QDialog { background: ${window}; }
QWidget { color: ${text}; }
QMenuBar { background: ${toolbar}; border-bottom: 1px solid ${border}; }
QMenuBar::item { padding: 4px 10px; background: transparent; }
QMenuBar::item:selected { background: ${hover}; }
QMenu { background: ${base}; border: 1px solid ${border}; padding: 4px 0; }
QMenu::item { padding: 5px 28px 5px 24px; }
QMenu::item:selected { background: ${accent}; color: ${accent_text}; }
QMenu::separator { height: 1px; background: ${border}; margin: 4px 8px; }
QToolBar { background: ${toolbar}; border: 0; border-bottom: 1px solid ${border};
  spacing: 4px; padding: 3px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 4px;
  padding: 4px 8px; }
QToolButton:hover { background: ${hover}; border-color: ${border}; }
QToolButton:pressed, QToolButton:checked { background: ${selection}; }
QDockWidget { font-weight: 600; }
QDockWidget::title { background: ${toolbar}; padding: 5px 8px; border: 1px solid ${border}; }
QTabWidget::pane { border: 1px solid ${border}; background: ${base}; top: -1px; }
QTabBar::tab { background: ${button}; color: ${text_dim}; padding: 5px 12px;
  border: 1px solid ${border}; border-bottom: none; margin-right: 2px; }
QTabBar::tab:selected { background: ${base}; color: ${text}; border-top: 2px solid ${accent}; }
QTabBar::tab:hover:!selected { background: ${hover}; }
QPlainTextEdit, QTextEdit, QTreeView, QListView, QTableView, QLineEdit {
  background: ${base}; alternate-background-color: ${alt_base}; border: 1px solid ${border};
  selection-background-color: ${selection}; selection-color: ${text}; }
QStatusBar { background: ${toolbar}; border-top: 1px solid ${border}; color: ${text_dim}; }
QToolTip { background: ${base}; color: ${text}; border: 1px solid ${border}; }
QScrollBar:vertical { background: ${window}; width: 12px; margin: 0; }
QScrollBar:horizontal { background: ${window}; height: 12px; margin: 0; }
QScrollBar::handle:vertical { background: ${border}; min-height: 24px; border-radius: 5px;
  margin: 2px; }
QScrollBar::handle:horizontal { background: ${border}; min-width: 24px; border-radius: 5px;
  margin: 2px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: ${text_dim}; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QMainWindow::separator { background: ${window}; width: 5px; height: 5px; }
QMainWindow::separator:hover { background: ${accent}; }
""")


def build_stylesheet(p: Palette) -> str:
    return _QSS.substitute(
        {k: getattr(p, k) for k in Palette.__dataclass_fields__ if k != "name"}
    )


def _luminance(hex_color: str) -> float:
    def ch(i: int) -> float:
        c = int(hex_color[1 + 2 * i: 3 + 2 * i], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(0) + 0.7152 * ch(1) + 0.0722 * ch(2)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio between two ``#rrggbb`` colours."""
    a, b = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def apply_theme(app, name: str) -> None:
    """Apply a built-in theme to a QApplication."""
    apply_palette(app, get_palette(name))


def apply_palette(app, p: Palette) -> None:
    """Apply any palette to a QApplication (Fusion style + palette + stylesheet)."""
    from PySide6.QtGui import QColor, QPalette

    role = QPalette.ColorRole
    pal = QPalette()
    for r, c in [
        (role.Window, p.window), (role.WindowText, p.text), (role.Base, p.base),
        (role.AlternateBase, p.alt_base), (role.ToolTipBase, p.base), (role.ToolTipText, p.text),
        (role.Text, p.text), (role.Button, p.button), (role.ButtonText, p.text),
        (role.Highlight, p.selection), (role.HighlightedText, p.text),
        (role.PlaceholderText, p.text_dim), (role.Link, p.accent),
    ]:
        pal.setColor(r, QColor(c))
    for r in (role.Text, role.ButtonText, role.WindowText):
        pal.setColor(QPalette.ColorGroup.Disabled, r, QColor(p.text_dim))
    app.setStyle("Fusion")
    app.setPalette(pal)
    app.setStyleSheet(build_stylesheet(p))
