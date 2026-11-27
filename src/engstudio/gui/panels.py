"""Dock panel registry. Panels not yet implemented are placeholders; each is replaced by a
real component in its own module in later milestones (G2.3 workspace, G3 folder/toolboxes...)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from engstudio.gui.command_window import CommandWindow
from engstudio.gui.diagnostics_panel import DiagnosticsPanel
from engstudio.gui.folder_panel import FolderPanel
from engstudio.gui.kernel_bridge import KernelBridge
from engstudio.gui.settings import UiSettings
from engstudio.gui.toolbox_panel import ToolboxPanel
from engstudio.gui.workspace_panel import WorkspacePanel

__all__ = ["PanelContext", "PanelSpec", "PlaceholderPanel", "default_panels"]

_AREA = Qt.DockWidgetArea


@dataclass
class PanelContext:
    """Shared services handed to every panel factory."""

    bridge: KernelBridge | None = None
    history_items: list[str] = field(default_factory=list)
    settings: UiSettings | None = None


class PlaceholderPanel(QWidget):
    """Empty panel that states which milestone provides its real content."""

    def __init__(self, title: str, milestone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        label = QLabel(f"{title}\n\nNot implemented yet (planned: {milestone}).")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        self.setMinimumSize(140, 80)


@dataclass(frozen=True)
class PanelSpec:
    id: str
    title: str
    area: Qt.DockWidgetArea
    create: Callable[[PanelContext], QWidget]
    tab_with: str | None = None  # id of the dock this one is tabbed with by default
    shortcut: str | None = None  # toggles visibility


def _placeholder(title: str, milestone: str) -> Callable[[PanelContext], QWidget]:
    return lambda ctx: PlaceholderPanel(title, milestone)


def _command_window(ctx: PanelContext) -> QWidget:
    return CommandWindow(ctx.bridge, ctx.history_items)


def _workspace(ctx: PanelContext) -> QWidget:
    return WorkspacePanel(ctx.bridge)


def _folder(ctx: PanelContext) -> QWidget:
    return FolderPanel(ctx.settings)


def _toolboxes(ctx: PanelContext) -> QWidget:
    return ToolboxPanel(ctx.bridge)


def _diagnostics(ctx: PanelContext) -> QWidget:
    return DiagnosticsPanel(ctx.bridge)


def default_panels() -> list[PanelSpec]:
    return [
        PanelSpec("folder", "Current Folder", _AREA.LeftDockWidgetArea,
                  _folder, None, "Ctrl+Shift+1"),
        PanelSpec("toolboxes", "Toolboxes", _AREA.LeftDockWidgetArea,
                  _toolboxes, "folder", "Ctrl+Shift+2"),
        PanelSpec("workspace", "Workspace", _AREA.RightDockWidgetArea,
                  _workspace, None, "Ctrl+Shift+3"),
        PanelSpec("docs", "Documentation", _AREA.RightDockWidgetArea,
                  _placeholder("Documentation", "G6"), "workspace", "Ctrl+Shift+4"),
        PanelSpec("command", "Command Window", _AREA.BottomDockWidgetArea,
                  _command_window, None, "Ctrl+Shift+5"),
        PanelSpec("diagnostics", "Diagnostics", _AREA.BottomDockWidgetArea,
                  _diagnostics, "command", "Ctrl+Shift+6"),
    ]
