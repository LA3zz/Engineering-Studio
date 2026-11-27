"""Main window: menus, toolstrip, dockable panels, themes, persisted layout."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStyle,
)

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import FigureUpdate
from engstudio.gui.command_window import CommandWindow
from engstudio.gui.diagnostics_panel import DiagnosticsPanel
from engstudio.gui.docs_panel import DocsPanel
from engstudio.gui.editor_tabs import ScriptTabs
from engstudio.gui.figure_window import FigureWindow
from engstudio.gui.folder_panel import FolderPanel
from engstudio.gui.kernel_bridge import KernelBridge
from engstudio.gui.panels import PanelContext, PanelSpec, default_panels
from engstudio.gui.settings import UiSettings
from engstudio.gui.theme import THEMES, apply_theme, get_palette
from engstudio.gui.toolbox_panel import ToolboxPanel
from engstudio.plotting.model import FigureSpec

APP_NAME = "Engineering Studio"
STATE_VERSION = 1  # bump when the set of docks/toolbars changes (invalidates saved layouts)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: UiSettings | None = None,
        kernel: KernelClient | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings if settings is not None else UiSettings(None)
        self.theme = "light"
        self.layout_restored = False
        self.docks: dict[str, QDockWidget] = {}
        self._specs: list[PanelSpec] = default_panels()
        self._theme_actions: dict[str, QAction] = {}
        self.bridge = KernelBridge(kernel, self) if kernel is not None else None
        self.command_window = None
        self.figures: dict[int, FigureWindow] = {}

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(640, 420)
        D = QMainWindow.DockOption
        self.setDockOptions(D.AnimatedDocks | D.AllowTabbedDocks | D.AllowNestedDocks)

        self.tabs = ScriptTabs(self)
        self.setCentralWidget(self.tabs)
        self._create_docks()
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self.statusBar().showMessage("Ready")

        saved = self.settings.get("theme", "light")
        self.set_theme(saved if saved in THEMES else "light", save=False)
        self._restore_window()

    # -- construction ----------------------------------------------------------
    def _create_docks(self) -> None:
        F = QDockWidget.DockWidgetFeature
        ctx = PanelContext(self.bridge, self._history_items(), self.settings)
        for spec in self._specs:
            dock = QDockWidget(spec.title, self)
            dock.setObjectName(f"dock_{spec.id}")
            dock.setWidget(spec.create(ctx))
            dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
            dock.setFeatures(F.DockWidgetClosable | F.DockWidgetMovable | F.DockWidgetFloatable)
            self.docks[spec.id] = dock
            self.addDockWidget(spec.area, dock)
            if spec.shortcut:
                dock.toggleViewAction().setShortcut(QKeySequence(spec.shortcut))
        widget = self.docks["command"].widget()
        self.command_window = widget if isinstance(widget, CommandWindow) else None
        folder = self.docks["folder"].widget()
        self.folder_panel = folder if isinstance(folder, FolderPanel) else None
        if self.folder_panel is not None:
            self.folder_panel.open_file_requested.connect(self.tabs.open_path)
        tools = self.docks["toolboxes"].widget()
        self.toolbox_panel = tools if isinstance(tools, ToolboxPanel) else None
        if self.toolbox_panel is not None:
            self.toolbox_panel.insert_requested.connect(self.insert_in_command)
        if self.bridge is not None:
            self.bridge.event.connect(self._on_kernel_event)
        diagnostics = self.docks["diagnostics"].widget()
        self.diagnostics_panel = (
            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None
        )
        self.docs_panel = None
        doc_id = next((k for k in self.docks if k.startswith("doc")), None)
        if doc_id is not None:
            old = self.docks[doc_id].widget()
            self.docs_panel = DocsPanel(theme=self.theme)
            self.docks[doc_id].setWidget(self.docs_panel)
            if old is not None:
                old.deleteLater()

    def _action(self, text, slot, shortcut=None, icon=None, checkable=False, tip=None) -> QAction:
        a = QAction(text, self)
        if icon is not None:
            a.setIcon(self.style().standardIcon(icon))
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setStatusTip(tip)
        a.setCheckable(checkable)
        a.triggered.connect(lambda _checked=False, s=slot: s())
        return a

    def _create_actions(self) -> None:
        P = QStyle.StandardPixmap
        self.act_new = self._action("&New Script", self.new_script, "Ctrl+N", P.SP_FileIcon,
                                    tip="Create a new script")
        self.act_open = self._action("&Open...", self.open_script, "Ctrl+O",
                                     P.SP_DialogOpenButton, tip="Open a script file")
        self.act_save = self._action("&Save", self.tabs.save, "Ctrl+S", P.SP_DialogSaveButton,
                                     tip="Save the current script")
        self.act_save_as = self._action("Save &As...", self.tabs.save_as, "Ctrl+Shift+S")
        self.act_close_tab = self._action("&Close Script", self._close_current, "Ctrl+W")
        self.act_exit = self._action("E&xit", self.close, "Ctrl+Q")
        self.act_reset = self._action("&Reset Layout", self.reset_layout, "Ctrl+Shift+R",
                                      tip="Restore the default panel arrangement")
        self.act_show_all = self._action("Show &All Panels", lambda: self.set_all_panels(True))
        self.act_hide_all = self._action("&Hide All Panels", lambda: self.set_all_panels(False))
        self.act_focus_cmd = self._action("Focus &Command Window", self.focus_command,
                                          "Ctrl+0")
        self.act_clear_cmd = self._action("Clear Command &Window", self.clear_command,
                                          "Ctrl+Shift+L")
        self.act_fullscreen = self._action("&Full Screen", self.toggle_fullscreen, "F11")
        self.act_toggle_theme = self._action("Toggle Light/Dark", self.toggle_theme,
                                             "Ctrl+Shift+T")
        self.act_about = self._action("&About", self.show_about)
        group = QActionGroup(self)
        group.setExclusive(True)
        for name in THEMES:
            a = self._action(f"{name.capitalize()} theme", lambda n=name: self.set_theme(n),
                             checkable=True)
            group.addAction(a)
            self._theme_actions[name] = a

    def _create_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&File")
        m.addActions([self.act_new, self.act_open])
        m.addSeparator()
        m.addActions([self.act_save, self.act_save_as, self.act_close_tab])
        m.addSeparator()
        m.addAction(self.act_exit)

        v = mb.addMenu("&View")
        panels = v.addMenu("&Panels")
        for spec in self._specs:
            panels.addAction(self.docks[spec.id].toggleViewAction())
        panels.addSeparator()
        panels.addActions([self.act_show_all, self.act_hide_all])
        v.addAction(self.act_reset)
        v.addActions([self.act_focus_cmd, self.act_clear_cmd])
        v.addSeparator()
        themes = v.addMenu("&Theme")
        themes.addActions(list(self._theme_actions.values()))
        themes.addAction(self.act_toggle_theme)
        v.addAction(self.act_fullscreen)

        mb.addMenu("&Help").addAction(self.act_about)

    def _create_toolbar(self) -> None:
        tb = self.addToolBar("Home")
        tb.setObjectName("toolbar_home")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.addActions([self.act_new, self.act_open, self.act_save])
        tb.addSeparator()
        tb.addAction(self.docks["command"].toggleViewAction())
        tb.addAction(self.docks["workspace"].toggleViewAction())
        tb.addSeparator()
        tb.addAction(self.act_toggle_theme)

    # -- layout --------------------------------------------------------------
    def _default_size(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1200, 760)
            return
        r = screen.availableGeometry()
        w, h = min(1500, int(r.width() * 0.85)), min(950, int(r.height() * 0.85))
        self.resize(max(w, 640), max(h, 420))
        self.move(r.x() + (r.width() - self.width()) // 2,
                  r.y() + (r.height() - self.height()) // 2)

    def _apply_default_layout(self) -> None:
        for spec in self._specs:
            dock = self.docks[spec.id]
            dock.setFloating(False)
            self.removeDockWidget(dock)
            self.addDockWidget(spec.area, dock)
            dock.show()
        for spec in self._specs:
            if spec.tab_with:
                self.tabifyDockWidget(self.docks[spec.tab_with], self.docks[spec.id])
        for spec in self._specs:
            if not spec.tab_with:
                self.docks[spec.id].raise_()
        w, h = self.width(), self.height()
        self.resizeDocks([self.docks["folder"], self.docks["workspace"]],
                         [int(w * 0.20), int(w * 0.22)], Qt.Orientation.Horizontal)
        self.resizeDocks([self.docks["command"]], [int(h * 0.28)], Qt.Orientation.Vertical)

    def reset_layout(self) -> None:
        self._apply_default_layout()
        self.statusBar().showMessage("Layout reset", 3000)

    def set_all_panels(self, visible: bool) -> None:
        for dock in self.docks.values():
            dock.setVisible(visible)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # -- persistence -----------------------------------------------------------
    def _restore_window(self) -> None:
        geo = self.settings.get_bytes("window_geometry")
        if not (geo and self.restoreGeometry(QByteArray(geo))):
            self._default_size()
        self._apply_default_layout()
        state = self.settings.get_bytes("window_state")
        if state and self.settings.get("layout_version") == STATE_VERSION:
            self.layout_restored = bool(self.restoreState(QByteArray(state), STATE_VERSION))
            if not self.layout_restored:
                self._apply_default_layout()

    def _save_window(self) -> None:
        s = self.settings
        s.set_bytes("window_geometry", bytes(self.saveGeometry().data()))
        s.set_bytes("window_state", bytes(self.saveState(STATE_VERSION).data()))
        s.set("layout_version", STATE_VERSION)
        s.set("theme", self.theme)
        s.save()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self.tabs.maybe_close_all():
            event.ignore()
            return
        if self.command_window is not None:
            self.settings.set("command_history", self.command_window.history.items())
        self._save_window()
        if self.bridge is not None:
            self.bridge.shutdown()
        for window in list(self.figures.values()):
            window.close()
        event.accept()

    # -- command window ----------------------------------------------------------
    def _history_items(self) -> list[str]:
        raw = self.settings.get("command_history", [])
        return [s for s in raw if isinstance(s, str)] if isinstance(raw, list) else []

    def focus_command(self) -> None:
        if self.command_window is not None:
            self.docks["command"].show()
            self.docks["command"].raise_()
            self.command_window.focus_input()

    def insert_in_command(self, text: str) -> None:
        """Insert ``text`` at the cursor of the Command Window input and focus it."""
        if self.command_window is None:
            return
        self.docks["command"].show()
        self.docks["command"].raise_()
        self.command_window.input.insert(text)
        self.command_window.focus_input()

    def _on_kernel_event(self, event: object) -> None:
        if isinstance(event, FigureUpdate):
            self.show_figure(event.figure)

    def show_figure(self, spec: FigureSpec) -> FigureWindow:
        """Open the window for ``spec.number`` or update it if it already exists."""
        window = self.figures.get(spec.number)
        if window is None:
            window = FigureWindow(spec.number, self.theme, self)
            window.closed.connect(self._figure_closed)
            self.figures[spec.number] = window
        window.set_figure(spec)
        window.show()
        window.raise_()
        return window

    def _figure_closed(self, number: int) -> None:
        self.figures.pop(number, None)

    def clear_command(self) -> None:
        if self.command_window is not None:
            self.command_window.clear_output()

    # -- actions ---------------------------------------------------------------
    def set_theme(self, name: str, save: bool = True) -> None:
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

    def new_script(self) -> None:
        self.tabs.new_script()

    def open_script(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self, "Open script", str(Path.cwd()), "Scripts (*.m);;All files (*)")
        for name in names:
            self.tabs.open_path(name)

    def _close_current(self) -> None:
        if self.tabs.count():
            self.tabs.close_tab(self.tabs.currentIndex())

    def show_about(self) -> None:
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>Offline engineering computation environment.<br>"
            "Interface shell (milestone G1): computation panels are not connected yet.")
