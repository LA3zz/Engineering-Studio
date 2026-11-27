"""Workspace browser: live table of the kernel's variables.

Reads ``WorkspaceSummary`` events from a ``KernelBridge``; clearing goes back through the
kernel (``clear ...``), so the kernel stays the single owner of the workspace.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from engstudio.app.kernel.protocol import VariableInfo, WorkspaceSummary
from engstudio.core.errors import EngStudioError
from engstudio.gui.formatting import format_size
from engstudio.gui.kernel_bridge import KernelBridge

__all__ = ["WorkspaceModel", "WorkspacePanel"]

COLUMNS = ("Name", "Class", "Size", "Preview")
_ROOT = QModelIndex()  # shared 'no parent' index (avoids a call in argument defaults)


class WorkspaceModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vars: tuple[VariableInfo, ...] = ()

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._vars)

    def columnCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._vars):
            return None
        v = self._vars[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return (v.name, v.cls, format_size(v.size), v.preview)[index.column()]
        return None

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section]
        return None

    def variable(self, row: int) -> VariableInfo:
        return self._vars[row]

    def set_variables(self, variables: Iterable[VariableInfo]) -> None:
        """Replace the table contents. If only values changed (same names, same order) the
        rows are updated in place so the user's selection survives."""
        new = tuple(variables)
        if [v.name for v in new] == [v.name for v in self._vars]:
            changed = new != self._vars
            self._vars = new
            if changed and new:
                self.dataChanged.emit(self.index(0, 0), self.index(len(new) - 1, len(COLUMNS) - 1))
            return
        self.beginResetModel()
        self._vars = new
        self.endResetModel()


class WorkspacePanel(QWidget):
    def __init__(self, bridge: KernelBridge | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.model = WorkspaceModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter variables by name")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)
        self.save_button = QToolButton()
        self.save_button.setText("Save...")
        self.save_button.setToolTip("Save variables to a .mat file (selected ones, or all)")
        self.save_button.clicked.connect(lambda _c=False: self.save_workspace())
        self.load_button = QToolButton()
        self.load_button.setText("Load...")
        self.load_button.setToolTip("Load variables from a .mat file (also from MATLAB)")
        self.load_button.clicked.connect(lambda _c=False: self.load_workspace())
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.filter, 1)
        top.addWidget(self.save_button)
        top.addWidget(self.load_button)

        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setAlternatingRowColors(True)
        self.view.setShowGrid(False)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.status = QLabel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(top)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.status)
        self.setMinimumSize(160, 100)

        self.act_clear_selected = QAction("Clear Selected", self)
        self.act_clear_selected.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        self.act_clear_selected.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.act_clear_selected.triggered.connect(lambda _c=False: self.clear_selected())
        self.act_clear_all = QAction("Clear All", self)
        self.act_clear_all.triggered.connect(lambda _c=False: self.clear_all())
        self.act_save = QAction("Save to .mat...", self)
        self.act_save.triggered.connect(lambda _c=False: self.save_workspace())
        self.act_load = QAction("Load .mat...", self)
        self.act_load.triggered.connect(lambda _c=False: self.load_workspace())
        self.view.addActions([self.act_clear_selected, self.act_clear_all, self.act_save,
                              self.act_load])
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        self.view.selectionModel().selectionChanged.connect(lambda *_: self._refresh_ui())
        self.view.doubleClicked.connect(self._display_variable)
        if bridge is None:
            self.setEnabled(False)
            self.status.setText("No kernel connected")
        else:
            bridge.event.connect(self._on_event)
            self._refresh_ui()

    # -- queries ---------------------------------------------------------------
    def selected_names(self) -> list[str]:
        rows = self.view.selectionModel().selectedRows()
        return [self.model.variable(self.proxy.mapToSource(i).row()).name for i in rows]

    # -- actions -----------------------------------------------------------------
    def clear_selected(self) -> None:
        names = self.selected_names()
        if names:
            self._run("clear " + " ".join(names))

    def clear_all(self) -> None:
        if self.model.rowCount():
            self._run("clear")

    def save_workspace(self, path: str | None = None) -> None:
        """Save the selected variables (or all) with `save` in the kernel."""
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Save workspace",
                                                  str(Path.cwd() / "matlab.mat"),
                                                  "MAT-files (*.mat)")
        if path:
            names = "".join(f", '{n}'" for n in self.selected_names())
            self._run(f"save('{_quote(path)}'{names})")

    def load_workspace(self, path: str | None = None) -> None:
        """Load a .mat file with `load` in the kernel."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Load workspace", str(Path.cwd()),
                                                  "MAT-files (*.mat)")
        if path:
            self._run(f"load('{_quote(path)}')")

    def _display_variable(self, index: QModelIndex) -> None:
        name = self.model.variable(self.proxy.mapToSource(index).row()).name
        self._run(name)

    def _run(self, code: str) -> None:
        if self.bridge is None:
            return
        try:
            self.bridge.execute(code)
        except EngStudioError as exc:
            self.status.setText(f"Error: {exc}")

    # -- events ------------------------------------------------------------------
    def _on_event(self, event: object) -> None:
        if isinstance(event, WorkspaceSummary):
            self.model.set_variables(event.variables)
            self._refresh_ui()

    def _refresh_ui(self) -> None:
        n = self.model.rowCount()
        self.status.setText(f"{n} variable{'s' if n != 1 else ''}")
        self.act_clear_selected.setEnabled(bool(self.view.selectionModel().hasSelection()))
        self.act_clear_all.setEnabled(n > 0)
        self.save_button.setEnabled(n > 0)
        self.act_save.setEnabled(n > 0)


def _quote(path: str) -> str:
    return path.replace("'", "''")
