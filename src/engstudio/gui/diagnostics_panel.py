"""Diagnostics panel (G6.1): table of kernel diagnostics kept across executions."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from engstudio.app.kernel.protocol import Diagnostics
from engstudio.gui.diagnostic_log import (
    SEVERITIES,
    SEVERITY_COLORS,
    DiagnosticEntry,
    DiagnosticLog,
)
from engstudio.gui.kernel_bridge import KernelBridge

__all__ = ["DiagnosticsPanel"]

_HEADERS = ("Severity", "Code", "Message", "Location", "Run")
_PLURAL = {"error": "Errors", "warning": "Warnings", "info": "Info"}


class DiagnosticsPanel(QWidget):
    # file (str or None), line, column of a located diagnostic that was double-clicked
    location_activated = Signal(object, int, int)

    def __init__(
        self, bridge: KernelBridge | None = None, theme: str = "light",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if theme not in SEVERITY_COLORS:
            raise ValueError(f"unknown theme {theme!r}; expected one of {sorted(SEVERITY_COLORS)}")
        self.log = DiagnosticLog()
        self.theme = theme
        self._rows: list[DiagnosticEntry] = []

        self.filter_buttons: dict[str, QToolButton] = {}
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        for sev in SEVERITIES:
            button = QToolButton()
            button.setCheckable(True)
            button.setChecked(True)
            button.setToolTip(f"Show or hide {_PLURAL[sev].lower()}")
            button.toggled.connect(lambda _checked: self.refresh())
            self.filter_buttons[sev] = button
            top.addWidget(button)
        top.addStretch(1)
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear")
        self.clear_button.setToolTip("Remove all diagnostics")
        self.clear_button.clicked.connect(lambda _checked=False: self.clear())
        top.addWidget(self.clear_button)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(lambda row, _col: self.activate_row(row))

        self.status = QLabel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status)
        self.setMinimumSize(140, 80)

        if bridge is not None:
            bridge.event.connect(self._on_event)
        self.refresh()

    # -- public API ---------------------------------------------------------
    def visible_entries(self) -> list[DiagnosticEntry]:
        return list(self._rows)

    def clear(self) -> None:
        self.log.clear()
        self.refresh()

    def set_theme(self, name: str) -> None:
        if name not in SEVERITY_COLORS:
            raise ValueError(f"unknown theme {name!r}; expected one of {sorted(SEVERITY_COLORS)}")
        self.theme = name
        self.refresh()

    def activate_row(self, row: int) -> bool:
        """Emit ``location_activated`` for a row that has a location; False otherwise."""
        if not 0 <= row < len(self._rows):
            return False
        e = self._rows[row]
        if e.line is None:
            return False
        self.location_activated.emit(e.file, e.line, e.col if e.col is not None else 1)
        return True

    def refresh(self) -> None:
        shown = {sev for sev, b in self.filter_buttons.items() if b.isChecked()}
        self._rows = self.log.visible(shown)
        colors = SEVERITY_COLORS[self.theme]
        self.table.setRowCount(len(self._rows))
        for r, e in enumerate(self._rows):
            cells = (e.severity.capitalize(), e.code, e.message, e.location_text,
                     f"#{e.request_id}")
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(e.message)
                if c == 0:
                    item.setForeground(QBrush(QColor(colors[e.severity])))
                self.table.setItem(r, c, item)
        counts = self.log.counts()
        for sev, button in self.filter_buttons.items():
            button.setText(f"{_PLURAL[sev]} ({counts[sev]})")
        total = sum(counts.values())
        note = f", {self.log.dropped} older dropped" if self.log.dropped else ""
        self.status.setText(f"{len(self._rows)} of {total} shown{note}")
        if self._rows:
            self.table.scrollToBottom()

    # -- internals ----------------------------------------------------------
    def _on_event(self, event: object) -> None:
        if isinstance(event, Diagnostics) and self.log.add(event):
            self.refresh()
