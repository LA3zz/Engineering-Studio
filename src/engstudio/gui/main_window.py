"""Main window: menus, toolstrip, dockable panels, themes, persisted layout."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStyle,
)

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import (
    ExecutionFinished,
    FigureClosed,
    FigureUpdate,
    FolderChanged,
    OpenModel,
)
from engstudio.core.errors import EngStudioError
from engstudio.gui.command_window import CommandWindow
from engstudio.gui.diagnostics_panel import DiagnosticsPanel
from engstudio.gui.docs_panel import DocsPanel
from engstudio.gui.editor_tabs import ScriptTabs
from engstudio.gui.figure_window import FigureWindow
from engstudio.gui.folder_panel import FolderPanel
from engstudio.gui.kernel_bridge import KernelBridge
from engstudio.gui.panels import PanelContext, PanelSpec, default_panels
from engstudio.gui.settings import UiSettings
from engstudio.gui.theme import THEMES, apply_palette, apply_theme, get_palette
from engstudio.gui.theme_custom import CustomThemes
from engstudio.gui.theme_dialog import ThemeDialog
from engstudio.gui.toolbox_panel import ToolboxPanel
from engstudio.plotting.model import FigureSpec

APP_NAME = "Engineering Studio"


def about_text() -> str:
    """Rich text for Help > About: version, contents, runtime and open-source credits."""
    import platform

    import PySide6

    from engstudio.version import __version__

    return (
        f"<h3>{APP_NAME} {__version__}</h3>"
        "<p>An offline, MATLAB-style environment for engineering students: Command Window, "
        "script editor (.m files), workspace, numerical engine, symbolic math, ODE solvers, "
        "2-D/3-D plotting and control systems.</p>"
        "<p><b>Status:</b> scripting, math engine, plotting, control systems and block-diagram "
        "simulation complete; Mechanical Engineering toolbox included; more toolboxes "
        "planned.</p>"
        f"<p>Python {platform.python_version()}, Qt (PySide6) {PySide6.__version__}</p>"
        "<p>Built with open-source software: NumPy, SciPy, SymPy, Matplotlib, PyQtGraph, "
        "python-control, Qt for Python (PySide6, LGPL). Not affiliated with MathWorks; "
        "MATLAB is a trademark of The MathWorks, Inc.</p>"
        "<p>Help: the Documentation panel (View &gt; Panels). Updates: Help &gt; Check for "
        "Updates. Source: github.com/LA3zz/Engineering-Studio</p>"
    )
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
        self.sim_editors: list = []  # open block-diagram editors (Simulation menu)
        self.custom_themes = CustomThemes.from_data(self.settings.get("custom_themes"))
        self._custom_actions: dict[str, QAction] = {}
        self._theme_group: QActionGroup | None = None
        self._themes_menu = None
        self._custom_sep = None

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
        known = isinstance(saved, str) and (saved in THEMES or saved in self.custom_themes)
        self.set_theme(saved if known else "light", save=False)
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
            self.folder_panel.open_model_requested.connect(self.open_model)
            self.folder_panel.folder_changed.connect(self.sync_working_folder)
        tools = self.docks["toolboxes"].widget()
        self.toolbox_panel = tools if isinstance(tools, ToolboxPanel) else None
        if self.toolbox_panel is not None:
            self.toolbox_panel.insert_requested.connect(self.insert_in_command)
        if self.bridge is not None:
            self.bridge.event.connect(self._on_kernel_event)
            self.bridge.running_changed.connect(self._on_running_changed)
        diagnostics = self.docks["diagnostics"].widget()
        self.diagnostics_panel = (
            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None
        )
        if self.diagnostics_panel is not None:
            self.diagnostics_panel.location_activated.connect(self._open_location)
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
        self.act_new_model = self._action("&New Model", self.new_model,
                                          tip="Open the block-diagram editor with a new model")
        self.act_open_model = self._action("&Open Model...", self.open_model_dialog,
                                           tip="Open a .esmodel simulation model")
        self.act_updates = self._action("Check for &Updates...", self.check_updates,
                                        tip="Ask GitHub whether a newer version exists")
        self.act_customize = self._action("&Customize...", self.customize_theme,
                                          tip="Edit colours and save custom themes")
        self.act_run = self._action("&Run Script", self.run_script, "F5",
                                    P.SP_MediaPlay, tip="Run the current script")
        self.act_run_selection = self._action(
            "Run &Selection or Line", self.run_selection, "F9",
            tip="Run the selected text, or the current line")
        self.act_stop = self._action("S&top", self.stop_execution, "Shift+F5",
                                     P.SP_MediaStop, tip="Stop the running code")
        self.act_stop.setEnabled(False)
        group = self._theme_group = QActionGroup(self)
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
        themes = self._themes_menu = v.addMenu("&Theme")
        themes.addActions(list(self._theme_actions.values()))
        self._custom_sep = themes.addSeparator()
        themes.addAction(self.act_toggle_theme)
        themes.addAction(self.act_customize)
        self._rebuild_custom_actions()
        v.addAction(self.act_fullscreen)

        run = mb.addMenu("&Run")
        run.addActions([self.act_run, self.act_run_selection, self.act_stop])

        sim = mb.addMenu("&Simulation")
        sim.addActions([self.act_new_model, self.act_open_model])

        help_menu = mb.addMenu("&Help")
        help_menu.addAction(self.act_updates)
        help_menu.addSeparator()
        help_menu.addAction(self.act_about)

    def _create_toolbar(self) -> None:
        tb = self.addToolBar("Home")
        tb.setObjectName("toolbar_home")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.addActions([self.act_new, self.act_open, self.act_save])
        tb.addSeparator()
        tb.addActions([self.act_run, self.act_stop])
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
        elif isinstance(event, FigureClosed):
            self.close_figure(event.number)
        elif isinstance(event, OpenModel):
            self.open_model(event.path)
        elif isinstance(event, FolderChanged):
            if self.folder_panel is not None:
                self.folder_panel.set_folder(event.path)
        elif isinstance(event, ExecutionFinished):
            text = {"ok": "Done", "error": "Finished with errors", "cancelled": "Stopped"}
            self.statusBar().showMessage(text.get(event.status, "Done"), 4000)

    # -- running code -------------------------------------------------------------
    def run_script(self) -> None:
        """Run the text of the current script tab (unsaved edits included)."""
        editor = self.tabs.current_editor()
        if editor is None:
            self.statusBar().showMessage("No script to run", 3000)
            return
        self._run_text(editor.toPlainText(), self._file_id(editor), editor.display_name)

    def run_selection(self) -> None:
        """Run the selected text, or the current line when nothing is selected.

        The code is padded with blank lines (and spaces) so that line and column numbers in
        diagnostics match the editor.
        """
        editor = self.tabs.current_editor()
        if editor is None:
            self.statusBar().showMessage("No script to run", 3000)
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            start = min(cursor.anchor(), cursor.position())
            block = editor.document().findBlock(start)
            text = cursor.selection().toPlainText()
            prefix = "\n" * block.blockNumber() + " " * (start - block.position())
        else:
            block = cursor.block()
            text = block.text()
            prefix = "\n" * block.blockNumber()
        if not text.strip():
            self.statusBar().showMessage("Nothing to run", 3000)
            return
        self._run_text(prefix + text, self._file_id(editor), f"{editor.display_name} (selection)")

    def stop_execution(self) -> None:
        if self.bridge is not None:
            self.bridge.cancel_running()
            self.statusBar().showMessage("Stopping...", 3000)

    @staticmethod
    def _file_id(editor) -> str:
        return str(editor.path) if editor.path else editor.untitled_name

    def _run_text(self, code: str, file_id: str, label: str) -> None:
        if self.bridge is None:
            self.statusBar().showMessage("No kernel connected", 3000)
            return
        if self.command_window is not None:
            self.docks["command"].show()
            self.command_window.echo(f">> run {label}")
        self.statusBar().showMessage(f"Running {label}...")
        try:
            self.bridge.execute(code, file_id)
        except EngStudioError as exc:
            self.statusBar().showMessage(f"Cannot run: {exc}", 5000)

    def _on_running_changed(self, running: bool) -> None:
        self.act_stop.setEnabled(running)
        self.act_run.setEnabled(not running)
        self.act_run_selection.setEnabled(not running)

    def _find_editor(self, file_id: str):
        for i in range(self.tabs.count()):
            editor = self.tabs.editor(i)
            if editor is None:
                continue
            if editor.path is not None and str(editor.path) == file_id:
                return editor
            if editor.path is None and editor.untitled_name == file_id:
                return editor
        return None

    def _open_location(self, file: object, line: int, col: int) -> None:
        """Show ``line``/``col`` of a script (opens the file when it is not open yet)."""
        if file is None:
            return  # the error came from a Command Window line: there is nothing to open
        file_id = str(file)
        editor = self._find_editor(file_id)
        if editor is None and Path(file_id).is_file():
            self.tabs.open_path(file_id)
            editor = self._find_editor(str(Path(file_id).resolve()))
        if editor is None:
            return
        self.tabs.setCurrentWidget(editor)
        block = editor.document().findBlockByNumber(max(line - 1, 0))
        if not block.isValid():  # a line past the end: go to the last line
            block = editor.document().lastBlock()
        column = min(max(col - 1, 0), max(block.length() - 1, 0))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + column)
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        editor.setFocus()

    def show_figure(self, spec: FigureSpec) -> FigureWindow:
        """Open the window for ``spec.number`` or update it if it already exists."""
        window = self.figures.get(spec.number)
        is_new = window is None
        if window is None:
            window = FigureWindow(spec.number, self.base_theme(), self)
            window.closed.connect(self._figure_closed)
            self.figures[spec.number] = window
            if spec.size is not None:
                window.resize(*spec.size)
        window.set_figure(spec)
        if is_new or not window.isVisible():  # animation frames must not steal the focus
            window.show()
            window.raise_()
        return window

    def close_figure(self, number: int) -> None:
        """Close the window of figure ``number`` if it is open."""
        window = self.figures.pop(number, None)
        if window is not None:
            window.closed.disconnect(self._figure_closed)  # the kernel already forgot it
            window.close()

    def _figure_closed(self, number: int) -> None:
        """The user closed a figure window: forget it here and in the kernel."""
        self.figures.pop(number, None)
        if self.bridge is not None:
            self.bridge.figure_closed(number)

    def clear_command(self) -> None:
        if self.command_window is not None:
            self.command_window.clear_output()

    # -- actions ---------------------------------------------------------------
    def base_theme(self) -> str:
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

    def new_model(self):
        """Simulation > New Model: an empty block-diagram editor."""
        from engstudio.gui.sim_editor import SimEditor

        editor = SimEditor(theme=self.base_theme(), parent=self)
        self.sim_editors.append(editor)
        editor.show()
        return editor

    def sync_working_folder(self, path: str) -> None:
        """The Current Folder is the working folder (as in MATLAB): relative file names in
        scripts (readmatrix, saveas, sim, ...) resolve against it. The kernel runs in this
        process, so one chdir serves both."""
        try:
            os.chdir(path)
        except OSError:
            pass

    def open_model(self, path: str):
        """Open a .esmodel in the editor (Simulation menu, Current Folder, open_system)."""
        from engstudio.gui.sim_editor import SimEditor

        editor = SimEditor(theme=self.base_theme(), parent=self)
        if not editor.open_path(path):
            editor.deleteLater()
            return None
        self.sim_editors.append(editor)
        editor.show()
        editor.raise_()
        return editor

    def open_model_dialog(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Open model", str(Path.cwd()),
                                              "Simulation models (*.esmodel)")
        if name:
            self.open_model(name)

    def check_updates(self) -> None:
        """Help > Check for Updates: one request to GitHub, only when clicked."""
        from engstudio.gui.updates import UpdateChecker
        from engstudio.version import __version__

        self._update_checker = UpdateChecker(__version__, self)
        self._update_checker.check()

    def show_about(self) -> None:
        QMessageBox.about(self, f"About {APP_NAME}", about_text())
