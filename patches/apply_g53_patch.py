"""G5.3 patch: Save As (PNG/SVG/PDF) in the Figure window (exact-match, idempotent).
Run from the project root: python patches\\apply_g53_patch.py

Needs G5.2 applied (src\\engstudio\\gui\\figure_window.py) and matplotlib installed; if either
is missing it stops WITHOUT changing anything."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio")
WINDOW = SRC / "gui" / "figure_window.py"

if not WINDOW.exists():
    sys.exit(f"{WINDOW} not found: apply G5.2 first. Nothing was changed.")
try:
    import matplotlib
except ImportError:
    sys.exit("matplotlib is NOT installed in this environment. Nothing was changed. "
             "Tell Claude; do not install it before agreeing on the version.")
print(f"matplotlib {matplotlib.__version__} found")
_lock = Path("requirements.lock.txt")
if _lock.exists() and "matplotlib" not in _lock.read_text(encoding="utf-8-sig").lower():
    print("WARNING: matplotlib is installed but not listed in requirements.lock.txt")

EDITS = [
    ("from PySide6.QtCore import Qt, Signal\n"
     "from PySide6.QtGui import QCloseEvent\n"
     "from PySide6.QtWidgets import QMainWindow, QWidget\n",
     "from pathlib import Path\n\n"
     "from PySide6.QtCore import Qt, Signal\n"
     "from PySide6.QtGui import QAction, QCloseEvent, QKeySequence\n"
     "from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QWidget\n"),
    ("from engstudio.gui.plots import FigureView\n",
     "from engstudio.app.figure_export import EXPORT_FORMATS, save_figure\n"
     "from engstudio.core.errors import EngStudioError\n"
     "from engstudio.gui.plots import FigureView\n"),
    ("        self.resize(720, 480)\n",
     "        self.resize(720, 480)\n"
     "        self.spec: FigureSpec | None = None\n"
     "        self._create_menu()\n"),
    ("        self.view.set_figure(spec)\n",
     "        self.spec = spec\n        self.view.set_figure(spec)\n"),
    ("    def _show_warnings(self) -> None:\n",
     "    def _create_menu(self) -> None:\n"
     "        self.save_action = QAction(\"&Save As...\", self)\n"
     "        self.save_action.setShortcut(QKeySequence(\"Ctrl+S\"))\n"
     "        self.save_action.setStatusTip(\"Save the figure as PNG, SVG or PDF\")\n"
     "        self.save_action.triggered.connect(lambda _checked=False: self.save_as())\n"
     "        close_action = QAction(\"&Close\", self)\n"
     "        close_action.setShortcut(QKeySequence(\"Ctrl+W\"))\n"
     "        close_action.triggered.connect(lambda _checked=False: self.close())\n"
     "        menu = self.menuBar().addMenu(\"&File\")\n"
     "        menu.addActions([self.save_action, close_action])\n\n"
     "    def save_as(self) -> bool:\n"
     '        """Ask for a file name and save the figure there. False if cancelled or failed."""\n'
     "        if self.spec is None:\n"
     "            return False\n"
     '        filters = ";;".join(f"{label} (*.{ext})" for ext, label in EXPORT_FORMATS.items())\n'
     "        name, _ = QFileDialog.getSaveFileName(\n"
     "            self, \"Save figure\", str(Path.cwd() / f\"figure{self.number}.png\"), filters)\n"
     "        return bool(name) and self.save_to(name)\n\n"
     "    def save_to(self, path: Path | str) -> bool:\n"
     '        """Save the figure to ``path`` (``.png`` is added if there is no extension)."""\n'
     "        if self.spec is None:\n"
     "            return False\n"
     "        target = Path(path)\n"
     "        if not target.suffix:\n"
     '            target = target.with_suffix(".png")\n'
     "        try:\n"
     "            saved = save_figure(self.spec, target)\n"
     "        except EngStudioError as exc:\n"
     '            QMessageBox.warning(self, "Save figure failed", str(exc))\n'
     "            return False\n"
     '        self.statusBar().showMessage(f"Saved {saved}")\n'
     "        return True\n\n"
     "    def _show_warnings(self) -> None:\n"),
]


def patch(path: Path, edits: list[tuple[str, str]]) -> None:
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in edits:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue  # already applied
        if text.count(old) != 1:
            sys.exit(f"{path.name}: expected text not found exactly once:\n{old}")
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"patched {path.name}")


patch(WINDOW, EDITS)
