"""Toolbox browser (G3.2): tree of toolboxes and their functions, with a filter box.

Data arrives as a ``ToolboxList`` event through the KernelBridge (the GUI never imports
toolboxes). Double-clicking a function emits ``insert_requested`` with its name.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engstudio.app.kernel.protocol import ToolboxInfo, ToolboxList
from engstudio.core.errors import EngStudioError
from engstudio.gui.kernel_bridge import KernelBridge

__all__ = ["ToolboxPanel"]

_ROLE = Qt.ItemDataRole.UserRole  # function items store their name; toolbox items store None


class ToolboxPanel(QWidget):
    insert_requested = Signal(str)  # function name to insert into the Command Window

    def __init__(self, bridge: KernelBridge | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        # per toolbox: (top item, lowercase name text, [(child item, name_l, summary_l)])
        self._index: list[tuple[QTreeWidgetItem, str, list[tuple[QTreeWidgetItem, str, str]]]] = []

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter functions...")
        self.filter_edit.setClearButtonEnabled(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.status)
        self.setMinimumSize(140, 80)

        self.filter_edit.textChanged.connect(self.apply_filter)
        self.tree.itemDoubleClicked.connect(lambda item, _col: self.activate_item(item))
        if bridge is None:
            self.status.setText("No kernel connected.")
        else:
            bridge.event.connect(self._on_event)
            self.refresh()

    # -- public API ---------------------------------------------------------
    def refresh(self) -> None:
        """Ask the kernel for the toolbox list (answered by a ``ToolboxList`` event)."""
        if self._bridge is None:
            return
        try:
            self._bridge.list_toolboxes()
        except EngStudioError as exc:
            self.populate(())
            self.status.setText(f"Toolbox list not available: {exc}")

    def populate(self, toolboxes: Iterable[ToolboxInfo]) -> None:
        self._index = []
        self.tree.clear()
        for tb in toolboxes:
            top = QTreeWidgetItem([tb.display_name])
            top.setToolTip(0, f"{tb.name}: {len(tb.functions)} functions")
            self.tree.addTopLevelItem(top)
            kids: list[tuple[QTreeWidgetItem, str, str]] = []
            for fn in tb.functions:
                child = QTreeWidgetItem([fn.name])
                child.setData(0, _ROLE, fn.name)
                tip = f"{fn.signature}\n{fn.summary}".strip()
                if tip:
                    child.setToolTip(0, tip)
                top.addChild(child)
                kids.append((child, fn.name.lower(), fn.summary.lower()))
            top.setExpanded(False)  # collapsed: click the arrow to see a toolbox's functions
            self._index.append((top, f"{tb.name} {tb.display_name}".lower(), kids))
        self.apply_filter()

    def apply_filter(self, text: str | None = None) -> None:
        """Show functions whose name or summary contains ``text`` (case-insensitive);
        a match on the toolbox name shows all of its functions. While filtering, toolboxes
        with matches open; clearing the filter collapses them again."""
        needle = (self.filter_edit.text() if text is None else text).strip().lower()
        total = shown = 0
        for top, top_text, kids in self._index:
            top_match = bool(needle) and needle in top_text
            visible = 0
            for child, name_l, summary_l in kids:
                match = not needle or top_match or needle in name_l or needle in summary_l
                child.setHidden(not match)
                visible += match
            total += len(kids)
            shown += visible
            top.setHidden(bool(needle) and visible == 0)
            top.setExpanded(bool(needle) and visible > 0)
        if not self._index:
            self.status.setText("No toolboxes available.")
        elif needle:
            self.status.setText(f"{shown} of {total} functions")
        else:
            self.status.setText(f"{len(self._index)} toolboxes, {total} functions")

    def activate_item(self, item: QTreeWidgetItem) -> bool:
        """Function item: request insertion of its name. Toolbox item: nothing."""
        name = item.data(0, _ROLE)
        if isinstance(name, str) and name:
            self.insert_requested.emit(name)
            return True
        return False

    # -- internals ----------------------------------------------------------
    def _on_event(self, event: object) -> None:
        if isinstance(event, ToolboxList):
            self.populate(event.toolboxes)
