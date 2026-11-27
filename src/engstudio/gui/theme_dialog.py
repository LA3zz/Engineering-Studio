"""Theme editor dialog (G7). Qt only; the colour logic lives in ``theme_custom``.

The dialog edits a draft palette and emits ``preview_requested`` after every change so the
main window can show it live. ``Save`` stores the draft in the shared ``CustomThemes`` object
(``themes_changed``) and asks the window to activate it (``theme_activated``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from engstudio.gui.theme import THEMES, get_palette
from engstudio.gui.theme_custom import (
    MIN_CONTRAST,
    ROLE_LABELS,
    CustomThemes,
    contrast_issues,
    make_palette,
    palette_from_json,
    palette_to_json,
    parse_hex,
    readable_text_colour,
    role_issues,
)

__all__ = ["ThemeDialog"]

MAX_IMPORT_BYTES = 65536
_BASES = ("light", "dark")


class ThemeDialog(QDialog):
    preview_requested = Signal(object)  # Palette
    themes_changed = Signal()
    theme_activated = Signal(str)

    def __init__(self, themes: CustomThemes, active: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Customize Theme")
        self.resize(680, 600)
        self.themes = themes
        self._active = active
        self._roles = list(ROLE_LABELS)
        self._base = "light"
        self._colors: dict[str, str] = {r: getattr(get_palette("light"), r) for r in self._roles}
        self._build_ui()
        self._fill_sources(active)
        self.load_theme(active)

    # -- construction -----------------------------------------------------------
    def _build_ui(self) -> None:
        self.source = QComboBox()
        self.source.activated.connect(lambda _i: self.load_theme(self.source.currentData()))
        self.base_combo = QComboBox()
        for b in _BASES:
            self.base_combo.addItem(b.capitalize(), b)
        self.base_combo.activated.connect(self._on_base)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Name for the saved theme")
        self.name_edit.setMaxLength(60)

        top = QHBoxLayout()
        for label, widget in (("Start from:", self.source), ("Base theme:", self.base_combo)):
            top.addWidget(QLabel(label))
            top.addWidget(widget, 1)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        name_row.addWidget(self.name_edit, 1)

        self.table = QTableWidget(len(self._roles), 3)
        self.table.setHorizontalHeaderLabels(["Colour role", "Colour", "Contrast warning"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for row, role in enumerate(self._roles):
            for col in range(3):
                item = QTableWidgetItem(ROLE_LABELS[role] if col == 0 else "")
                item.setFlags(flags)
                self.table.setItem(row, col, item)
        self.table.currentCellChanged.connect(lambda r, _c, _pr, _pc: self._on_row(r))
        self.table.cellDoubleClicked.connect(lambda r, _c: self._pick(r))

        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#rrggbb")
        self.hex_edit.setMaxLength(9)
        self.hex_edit.editingFinished.connect(self._apply_hex)
        pick = QPushButton("Pick...")
        pick.setToolTip("Open the colour dialog (spectrum, hex field, screen picker)")
        pick.clicked.connect(lambda: self._pick(self.table.currentRow()))
        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Selected colour:"))
        edit_row.addWidget(self.hex_edit, 1)
        edit_row.addWidget(pick)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        buttons = QHBoxLayout()
        for text, slot in (("Save", self.save_theme), ("Delete", self._on_delete),
                           ("Reset to base", self.reset_to_base), ("Import...", self.import_theme),
                           ("Export...", self.export_theme)):
            b = QPushButton(text)
            b.clicked.connect(lambda _checked=False, s=slot: s())
            buttons.addWidget(b)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        for part in (top, name_row):
            layout.addLayout(part)
        layout.addWidget(self.table, 1)
        layout.addLayout(edit_row)
        layout.addWidget(self.summary)
        layout.addLayout(buttons)
        layout.addWidget(self.status)

    # -- state --------------------------------------------------------------------
    def current_palette(self):
        name = self.name_edit.text().strip() or "custom"
        return make_palette(name, self._colors, get_palette(self._base))

    def _fill_sources(self, select: str) -> None:
        self.source.blockSignals(True)
        self.source.clear()
        for name in THEMES:
            self.source.addItem(name.capitalize(), name)
        for name in self.themes.names():
            self.source.addItem(f"{name} (custom)", name)
        index = self.source.findData(select)
        self.source.setCurrentIndex(max(index, 0))
        self.source.blockSignals(False)

    def _set_draft(self, palette, base: str) -> None:
        self._base = base
        self._colors = {r: getattr(palette, r) for r in self._roles}
        self.base_combo.blockSignals(True)
        self.base_combo.setCurrentIndex(_BASES.index(base))
        self.base_combo.blockSignals(False)
        self._changed()
        self._on_row(max(self.table.currentRow(), 0))

    def load_theme(self, name: str) -> None:
        """Load a built-in or saved theme into the editor (name field only for saved ones)."""
        palette = self.themes.resolve(name)
        custom = name in self.themes
        self.name_edit.setText(name if custom else "")
        self._set_draft(palette, self.themes.base_of(name) if custom else name)

    def set_role_color(self, role: str, text: str) -> None:
        """Set one colour role (any ``parse_hex`` format); ValueError if invalid."""
        if role not in self._colors:
            raise ValueError(f"unknown colour role {role!r}")
        value = parse_hex(text)
        if value != self._colors[role]:
            self._colors[role] = value
            self._changed()

    def _changed(self) -> None:
        palette = self.current_palette()
        issues = contrast_issues(palette)
        for row, role in enumerate(self._roles):
            item = self.table.item(row, 1)
            item.setText(self._colors[role])
            item.setBackground(QColor(self._colors[role]))
            item.setForeground(QColor(readable_text_colour(self._colors[role])))
            self.table.item(row, 2).setText(role_issues(issues, role))
        if issues:
            self.summary.setText(
                f"{len(issues)} contrast warning(s): text below {MIN_CONTRAST}:1 on its "
                "background is hard to read. You can still save the theme.")
        else:
            self.summary.setText("No contrast problems.")
        self.preview_requested.emit(palette)

    def _message(self, text: str, error: bool = False) -> None:
        self.status.setText(f"Error: {text}" if error else text)

    # -- editing ------------------------------------------------------------------
    def _on_row(self, row: int) -> None:
        if 0 <= row < len(self._roles):
            self.hex_edit.setText(self._colors[self._roles[row]])

    def _apply_hex(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self._roles):
            return
        role = self._roles[row]
        try:
            self.set_role_color(role, self.hex_edit.text())
        except ValueError as exc:
            self._message(str(exc), error=True)
        self.hex_edit.setText(self._colors[role])

    def _pick(self, row: int) -> None:
        if not 0 <= row < len(self._roles):
            self._message("Select a colour role first.", error=True)
            return
        role = self._roles[row]
        colour = QColorDialog.getColor(
            QColor(self._colors[role]), self, f"Colour: {ROLE_LABELS[role]}",
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if colour.isValid():
            self.set_role_color(role, colour.name())
            self._on_row(row)

    def _on_base(self, _index: int) -> None:
        self._base = self.base_combo.currentData()

    def reset_to_base(self) -> None:
        self._set_draft(get_palette(self._base), self._base)
        self._message(f"Colours reset to the {self._base} theme.")

    # -- saving -------------------------------------------------------------------
    def save_theme(self) -> bool:
        try:
            name = self.themes.set(self.name_edit.text(), self.current_palette(), self._base)
        except ValueError as exc:
            self._message(str(exc), error=True)
            return False
        self.name_edit.setText(name)
        self._active = name
        self._fill_sources(name)
        self.themes_changed.emit()
        self.theme_activated.emit(name)
        self._message(f"Saved theme {name!r}.")
        return True

    def delete_theme(self) -> bool:
        name = self.name_edit.text().strip()
        if name not in self.themes:
            self._message(f"No saved custom theme named {name!r}.", error=True)
            return False
        base = self.themes.delete(name)
        self._fill_sources(base)
        self.themes_changed.emit()
        if name == self._active:
            self._active = base
            self.theme_activated.emit(base)
        self._message(f"Deleted theme {name!r}.")
        return True

    def _on_delete(self) -> None:
        name = self.name_edit.text().strip()
        if name not in self.themes:
            self.delete_theme()  # shows the error message
            return
        answer = QMessageBox.question(self, "Delete theme", f"Delete the theme {name!r}?")
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_theme()

    # -- import / export ----------------------------------------------------------
    def to_json_text(self) -> str:
        return palette_to_json(self.current_palette(), self._base)

    def load_json_text(self, text: str) -> None:
        theme = palette_from_json(text)
        self.name_edit.setText(theme.name)
        self._set_draft(theme.palette, theme.base)

    def import_theme(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import theme", "", "Theme files (*.json);;All files (*)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > MAX_IMPORT_BYTES:
                raise ValueError("file is too large for a theme file")
            self.load_json_text(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            self._message(f"import failed: {exc}", error=True)
            return
        self._message("Imported. Press Save to keep the theme.")

    def export_theme(self) -> None:
        name = self.name_edit.text().strip() or "theme"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export theme", f"{name}.json", "Theme files (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(self.to_json_text(), encoding="utf-8")
        except OSError as exc:
            self._message(f"export failed: {exc}", error=True)
            return
        self._message(f"Exported to {path}")
