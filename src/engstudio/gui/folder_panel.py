"""Current Folder browser: file tree rooted at a chosen folder (G3.1).

Pure GUI component: it never touches the kernel. Double-clicking a folder enters it,
double-clicking a ``.m`` file emits ``open_file_requested``. The chosen folder is stored in
``UiSettings`` under ``current_folder``. It does not change the process working directory
itself: the main window follows ``folder_changed`` with a chdir (the Current Folder is the
working folder, as in MATLAB), and moves the panel when a script runs ``cd``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLineEdit,
    QStyle,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from engstudio.gui.settings import UiSettings

__all__ = ["FolderPanel", "SETTINGS_KEY"]

SETTINGS_KEY = "current_folder"
SCRIPT_SUFFIX = ".m"


class FolderPanel(QWidget):
    open_file_requested = Signal(str)  # absolute path of a script to open
    open_model_requested = Signal(str)  # absolute path of a .esmodel simulation model
    folder_changed = Signal(str)  # absolute path of the new root folder

    def __init__(self, settings: UiSettings | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._folder = self._initial_folder()

        style = self.style()
        self.up_button = QToolButton()
        self.up_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogToParent))
        self.up_button.setToolTip("Up one folder")
        self.browse_button = QToolButton()
        self.browse_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.browse_button.setToolTip("Browse for folder...")
        self.path_edit = QLineEdit()
        self.path_edit.setToolTip("Type a folder path and press Enter")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.up_button)
        top.addWidget(self.browse_button)
        top.addWidget(self.path_edit, 1)

        self.model = QFileSystemModel(self)
        self.model.setReadOnly(True)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        self.setMinimumSize(140, 80)

        self.up_button.clicked.connect(lambda _c=False: self.go_up())
        self.browse_button.clicked.connect(lambda _c=False: self.browse())
        self.path_edit.returnPressed.connect(self._path_entered)
        self.tree.doubleClicked.connect(self._on_double_clicked)
        self._show(self._folder)

    # -- public API ---------------------------------------------------------
    @property
    def folder(self) -> Path:
        return self._folder

    def set_folder(self, path: Path | str) -> bool:
        """Make ``path`` the root. Returns False (state unchanged) if it is not a folder."""
        try:
            p = Path(path).resolve()
            ok = p.is_dir()
        except (OSError, RuntimeError):
            ok = False
        if not ok:
            self.path_edit.setText(str(self._folder))
            return False
        changed = p != self._folder
        self._folder = p
        self._show(p)
        if self._settings is not None:
            self._settings.set(SETTINGS_KEY, str(p))
        if changed:
            self.folder_changed.emit(str(p))
        return True

    def go_up(self) -> bool:
        parent = self._folder.parent
        return parent != self._folder and self.set_folder(parent)

    def browse(self) -> None:
        name = QFileDialog.getExistingDirectory(self, "Select folder", str(self._folder))
        if name:
            self.set_folder(name)

    def activate_path(self, path: Path | str) -> bool:
        """Folder: enter it. ``.m`` file: request opening in the editor. ``.esmodel``: request
        opening in the model editor. Anything else: ignored."""
        p = Path(path)
        if p.is_dir():
            return self.set_folder(p)
        if p.is_file() and p.suffix.lower() == SCRIPT_SUFFIX:
            self.open_file_requested.emit(str(p.resolve()))
            return True
        if p.is_file() and p.suffix.lower() == ".esmodel":
            self.open_model_requested.emit(str(p.resolve()))
            return True
        return False

    # -- internals ----------------------------------------------------------
    def _initial_folder(self) -> Path:
        if self._settings is not None:
            saved = self._settings.get(SETTINGS_KEY)
            if isinstance(saved, str) and saved:
                try:
                    p = Path(saved).resolve()
                    if p.is_dir():
                        return p
                except (OSError, RuntimeError):
                    pass
        return Path.cwd().resolve()

    def _show(self, folder: Path) -> None:
        self.model.setRootPath(str(folder))
        self.tree.setRootIndex(self.model.index(str(folder)))
        self.path_edit.setText(str(folder))
        self.path_edit.setToolTip(str(folder))
        self.up_button.setEnabled(folder.parent != folder)

    def _path_entered(self) -> None:
        self.set_folder(self.path_edit.text().strip())

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if index.isValid():
            self.activate_path(self.model.filePath(index))
