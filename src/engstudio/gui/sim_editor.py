"""Block-diagram model editor (Phase 7, S13-S16): library, canvas, wiring, parameter and
settings dialogs, Run/Stop with Scope windows, open/save ``.esmodel``.

The ``sim.model.Model`` is the single source of truth: every edit makes a new model, pushes the
old one on the undo stack and redraws the canvas. Simulations run on a worker thread through
``app.sim_service``; Scopes open as figure windows when the run ends.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from engstudio.app.sim_service import (
    BlockInfo,
    catalog,
    check_block,
    format_param,
    parse_param,
    ports_of,
    run_model,
    scope_figures,
)
from engstudio.core.errors import EngStudioError
from engstudio.gui.figure_window import FigureWindow
from engstudio.sim import serialization
from engstudio.sim.model import SOLVERS, Block, Line, Model

__all__ = ["SimEditor"]

MIME = "application/x-engstudio-block"
PORT_R = 5.0
_GRID = 10.0


def _snap(v: float) -> float:
    return round(v / _GRID) * _GRID


def default_subsystem() -> Model:
    inner = Model("subsystem")
    for b in (Block("In1", "Inport", position=(20, 40)),
              Block("Gain1", "Gain", position=(120, 40)),
              Block("Out1", "Outport", position=(240, 40))):
        inner = inner.add_block(b)
    return inner.connect("In1", 1, "Gain1", 1).connect("Gain1", 1, "Out1", 1)


# --------------------------------------------------------------------------- canvas items
class PortItem(QGraphicsEllipseItem):
    def __init__(self, block_id: str, kind: str, index: int, parent: QGraphicsItem) -> None:
        super().__init__(-PORT_R, -PORT_R, 2 * PORT_R, 2 * PORT_R, parent)
        self.block_id, self.kind, self.index = block_id, kind, index
        self.setBrush(QBrush(QColor("#1f6fb4") if kind == "out" else QColor("#ffffff")))
        self.setPen(QPen(QColor("#1f6fb4"), 1.5))
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip(f"{'output' if kind == 'out' else 'input'} {index}")


def face_text(block: Block) -> str:
    """What the block shows on its face (as Simulink: 1/s, the gain value, the signs ...)."""
    t, p = block.type, block.param
    if t == "Gain":
        return format_param(p("K", 1.0))
    if t == "Constant":
        return format_param(p("Value", 1.0))
    if t == "Integrator":
        return "1/s"
    if t == "Sum":
        return str(p("Signs", "++")).replace("|", "")
    if t == "Product":
        return str(p("Operations", "**")).replace("*", "×").replace("/", "÷")
    if t == "TransferFcn":
        return f"{format_param(p('Num', [1.0]))}\n{format_param(p('Den', [1.0, 1.0]))}"
    if t == "DiscreteTransferFcn":
        return f"{format_param(p('Num', [1.0]))}\n{format_param(p('Den', [1.0, -0.5]))} (z)"
    if t == "UnitDelay":
        return "1/z"
    if t == "MathFunction":
        return str(p("Function", "exp"))
    if t == "Fcn":
        return f"f(u) = {p('Expression', 'u')}"
    if t == "PIDController":
        return "PID"
    if t == "Subsystem":
        return "Subsystem"
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)  # ToWorkspace -> To Workspace


class BlockItem(QGraphicsRectItem):
    def __init__(self, block: Block, n_in: int, n_out: int, summary: str) -> None:
        f = QFont()
        f.setPointSize(8)
        text = face_text(block)
        probe = QGraphicsSimpleTextItem(text)
        probe.setFont(f)
        w = max(block.size[0], probe.boundingRect().width() + 2 * PORT_R + 14)
        h = max(block.size[1], 20 * max(n_in, n_out, 1), probe.boundingRect().height() + 10)
        super().__init__(0, 0, w, h)
        self.block = block
        self.setPos(*block.position)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setBrush(QBrush(QColor("#eef4fb")))
        self.setPen(QPen(QColor("#355c88"), 1.5))
        self.setToolTip(f"{block.type}\n{summary}" if summary else block.type)
        label = QGraphicsSimpleTextItem(text, self)
        label.setFont(f)
        label.setPos((w - label.boundingRect().width()) / 2,
                     (h - label.boundingRect().height()) / 2)
        name = QGraphicsSimpleTextItem(block.name, self)
        name.setFont(f)
        name.setBrush(QBrush(QColor("#555555")))
        name.setPos((w - name.boundingRect().width()) / 2, h + 2)
        self.inputs = [self._port(block.id, "in", i, 0, h * (i - 0.5) / n_in)
                       for i in range(1, n_in + 1)]
        self.outputs = [self._port(block.id, "out", i, w, h * (i - 0.5) / n_out)
                        for i in range(1, n_out + 1)]

    def _port(self, bid: str, kind: str, i: int, x: float, y: float) -> PortItem:
        p = PortItem(bid, kind, i, self)
        p.setPos(x, y)
        return p

    def port_pos(self, kind: str, index: int) -> QPointF:
        items = self.inputs if kind == "in" else self.outputs
        return items[index - 1].scenePos() if 0 < index <= len(items) else self.scenePos()


class LineItem(QGraphicsPathItem):
    def __init__(self, line: Line, start: QPointF, end: QPointF) -> None:
        super().__init__()
        self.line_ref = line
        mid = (start.x() + end.x()) / 2 if end.x() > start.x() + 20 else start.x() + 15
        path = QPainterPath(start)
        if end.x() > start.x() + 20:
            path.lineTo(mid, start.y())
            path.lineTo(mid, end.y())
        else:  # feedback: go out, down/up, back left, in
            low = max(start.y(), end.y()) + 40
            path.lineTo(start.x() + 15, start.y())
            path.lineTo(start.x() + 15, low)
            path.lineTo(end.x() - 15, low)
            path.lineTo(end.x() - 15, end.y())
        path.lineTo(end)
        self.setPath(path)
        self.setPen(QPen(QColor("#202020"), 1.4))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-1)


class ModelScene(QGraphicsScene):
    def __init__(self, editor: SimEditor) -> None:
        super().__init__()
        self.editor = editor
        self._drag_from: PortItem | None = None
        self._rubber: QGraphicsPathItem | None = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.scenePos(), self.views()[0].transform()) if self.views() else None
        if isinstance(item, PortItem) and item.kind == "out":
            self._drag_from = item
            self._rubber = self.addPath(QPainterPath(item.scenePos()),
                                        QPen(QColor("#1f6fb4"), 1, Qt.PenStyle.DashLine))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None and self._rubber is not None:
            path = QPainterPath(self._drag_from.scenePos())
            path.lineTo(event.scenePos())
            self._rubber.setPath(path)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None:
            src = self._drag_from
            self._drag_from = None
            if self._rubber is not None:
                self.removeItem(self._rubber)
                self._rubber = None
            target = next((i for i in self.items(event.scenePos()) if isinstance(i, PortItem)
                           and i.kind == "in"), None)
            if target is not None:
                self.editor.connect(src.block_id, src.index, target.block_id, target.index)
            return
        super().mouseReleaseEvent(event)
        self.editor.sync_positions()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.scenePos(), self.views()[0].transform()) if self.views() else None
        while item is not None and not isinstance(item, BlockItem):
            item = item.parentItem()
        if isinstance(item, BlockItem):
            self.editor.open_block(item.block.id)
            return
        super().mouseDoubleClickEvent(event)


class ModelView(QGraphicsView):
    def __init__(self, scene: ModelScene, editor: SimEditor) -> None:
        super().__init__(scene)
        self.editor = editor
        self.setAcceptDrops(True)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        btype = bytes(event.mimeData().data(MIME)).decode("utf-8")
        pos = self.mapToScene(event.position().toPoint())
        self.editor.add_block(btype, (pos.x(), pos.y()))
        event.acceptProposedAction()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.editor.delete_selected()
            return
        super().keyPressEvent(event)


class LibraryTree(QTreeWidget):
    def __init__(self, editor: SimEditor) -> None:
        super().__init__()
        self.editor = editor
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        groups: dict[str, QTreeWidgetItem] = {}
        for info in catalog():

            group = groups.get(info.category)
            if group is None:
                group = groups[info.category] = QTreeWidgetItem([info.category])
                self.addTopLevelItem(group)
            item = QTreeWidgetItem([info.name])
            item.setData(0, Qt.ItemDataRole.UserRole, info.name)
            item.setToolTip(0, info.doc)
            group.addChild(item)
        self.itemDoubleClicked.connect(self._add)

    def _add(self, item: QTreeWidgetItem) -> None:
        btype = item.data(0, Qt.ItemDataRole.UserRole)
        if btype:
            self.editor.add_block(btype)

    def mimeData(self, items) -> QMimeData:  # noqa: N802
        data = QMimeData()
        btype = items[0].data(0, Qt.ItemDataRole.UserRole) if items else None
        if btype:
            data.setData(MIME, str(btype).encode("utf-8"))
        return data


# -------------------------------------------------------------------------------- dialogs
class ParamDialog(QDialog):
    def __init__(self, block: Block, info: BlockInfo | None, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Block parameters: {block.name} ({block.type})")
        self.block = block
        self.result_block: Block | None = None
        form = QFormLayout(self)
        if info is not None and info.doc:
            doc = QLabel(info.doc)
            doc.setWordWrap(True)
            form.addRow(doc)
        self.name_edit = QLineEdit(block.name)
        form.addRow("Name", self.name_edit)
        self.fields: dict[str, tuple[str, QWidget]] = {}
        for p in (info.params if info else ()):
            current = block.param(p.name)
            text = format_param(current) if current is not None else p.default_text
            if p.kind == "choice":
                w: QWidget = QComboBox()
                w.addItems(list(p.choices))
                w.setCurrentText(text)
            else:
                w = QLineEdit(text)
            w.setToolTip(p.doc)
            form.addRow(p.name, w)
            self.fields[p.name] = (p.kind, w)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, object]:
        out = {}
        for name, (kind, w) in self.fields.items():
            text = w.currentText() if isinstance(w, QComboBox) else w.text()
            try:
                out[name] = parse_param(kind, text)
            except EngStudioError as exc:
                raise EngStudioError(f"{name}: {exc}") from None
        return out

    def try_accept(self) -> None:
        try:
            block = self.block.with_params(**self.values())
            block = replace(block, name=self.name_edit.text().strip() or block.id)
            check_block(block)
        except EngStudioError as exc:
            QMessageBox.warning(self, "Invalid parameter", str(exc))
            return
        self.result_block = block
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, model: Model, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Simulation settings")
        s = model.settings
        form = QFormLayout(self)
        self.edits = {
            "start_time": QLineEdit(f"{s.start_time:g}"),
            "stop_time": QLineEdit(f"{s.stop_time:g}"),
            "rel_tol": QLineEdit(f"{s.rel_tol:g}"), "abs_tol": QLineEdit(f"{s.abs_tol:g}"),
            "max_step": QLineEdit(format_param(s.max_step) if s.max_step != float("inf")
                                  else "auto"),
            "fixed_step": QLineEdit(f"{s.fixed_step:g}"),
        }
        self.solver = QComboBox()
        self.solver.addItems(list(SOLVERS))
        self.solver.setCurrentText(s.solver)
        labels = {"start_time": "Start time (s)", "stop_time": "Stop time (s)",
                  "rel_tol": "Relative tolerance", "abs_tol": "Absolute tolerance",
                  "max_step": "Max step (auto = (stop-start)/50)",
                  "fixed_step": "Fixed step (rk4/euler)"}
        form.addRow("Solver", self.solver)
        for key, edit in self.edits.items():
            form.addRow(labels[key], edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def changes(self) -> dict[str, object]:
        out: dict[str, object] = {"solver": self.solver.currentText()}
        for key, edit in self.edits.items():
            text = edit.text().strip().lower()
            out[key] = float("inf") if key == "max_step" and text in ("auto", "") else \
                parse_param("number", text)
        return out


# ----------------------------------------------------------------------------- run thread
class _RunThread(QThread):
    progressed = Signal(float)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, model: Model) -> None:
        super().__init__()
        self.model = model
        self.stop_requested = False

    def run(self) -> None:  # noqa: D401 (Qt override)
        try:
            res = run_model(self.model, progress=self.progressed.emit,
                            should_stop=lambda: self.stop_requested)
        except EngStudioError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # never let a bug kill the editor
            self.failed.emit(f"Internal error: {type(exc).__name__}: {exc}")
            return
        self.succeeded.emit(res)


# --------------------------------------------------------------------------------- editor
class SimEditor(QMainWindow):
    model_changed = Signal(object)  # the new Model (used by subsystem editors)

    def __init__(self, model: Model | None = None, path: Path | None = None,
                 theme: str = "light", parent: QWidget | None = None,
                 is_subsystem: bool = False) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.model = model or Model("untitled")
        self.path = path
        self.theme = theme
        self.is_subsystem = is_subsystem
        self.modified = False
        self.ask_to_save = True  # False: discard unsaved changes silently (tests, embedding)
        self._undo: list[Model] = []
        self._redo: list[Model] = []
        self._infos = {b.name: b for b in catalog()}
        self._items: dict[str, BlockItem] = {}
        self._children: list[QWidget] = []
        self.figures: list[QWidget] = []
        self.last_result = None
        self._thread: _RunThread | None = None
        self.scene = ModelScene(self)
        self.view = ModelView(self.scene, self)
        self.setCentralWidget(self.view)
        dock = QDockWidget("Library", self)
        self.library = LibraryTree(self)
        dock.setWidget(self.library)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(160)
        self.progress.setRange(0, 100)
        self.statusBar().addPermanentWidget(self.progress)
        self._build_actions()
        self.resize(1000, 650)
        self.redraw()

    # -- actions -----------------------------------------------------------------
    def _action(self, text: str, slot, shortcut: str | None = None) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda _checked=False: slot())
        return a

    def _build_actions(self) -> None:
        self.act_new = self._action("&New", self.new_model, "Ctrl+N")
        self.act_open = self._action("&Open...", self.open_dialog, "Ctrl+O")
        self.act_save = self._action("&Save", self.save, "Ctrl+S")
        self.act_save_as = self._action("Save &As...", self.save_as, "Ctrl+Shift+S")
        self.act_undo = self._action("&Undo", self.undo, "Ctrl+Z")
        self.act_redo = self._action("&Redo", self.redo, "Ctrl+Y")
        self.act_delete = self._action("&Delete", self.delete_selected)
        self.act_run = self._action("&Run", self.run_async, "Ctrl+R")
        self.act_stop = self._action("S&top", self.stop)
        self.act_stop.setEnabled(False)
        self.act_settings = self._action("Se&ttings...", self.settings_dialog, "Ctrl+E")
        tb = self.addToolBar("Simulation")
        actions = ([self.act_undo, self.act_redo, self.act_run, self.act_stop,
                    self.act_settings] if self.is_subsystem else
                   [self.act_new, self.act_open, self.act_save, self.act_undo, self.act_redo,
                    self.act_run, self.act_stop, self.act_settings])
        tb.addActions(actions)
        if not self.is_subsystem:
            m = self.menuBar().addMenu("&File")
            m.addActions([self.act_new, self.act_open, self.act_save, self.act_save_as])
        e = self.menuBar().addMenu("&Edit")
        e.addActions([self.act_undo, self.act_redo, self.act_delete])
        s = self.menuBar().addMenu("&Simulation")
        s.addActions([self.act_run, self.act_stop, self.act_settings])

    # -- model edits ----------------------------------------------------------------------
    def _apply(self, new: Model) -> None:
        self._undo.append(self.model)
        self._redo.clear()
        self.model = new
        self.modified = True
        self.redraw()
        self.model_changed.emit(new)

    def undo(self) -> None:
        if self._undo:
            self._redo.append(self.model)
            self.model = self._undo.pop()
            self.modified = True
            self.redraw()
            self.model_changed.emit(self.model)

    def redo(self) -> None:
        if self._redo:
            self._undo.append(self.model)
            self.model = self._redo.pop()
            self.modified = True
            self.redraw()
            self.model_changed.emit(self.model)

    def add_block(self, btype: str, pos: tuple[float, float] | None = None) -> str:
        bid = self.model.new_id(btype)
        if pos is None:
            center = self.view.mapToScene(self.view.viewport().rect().center())
            pos = (center.x() + 15 * (len(self.model.blocks) % 5), center.y())
        sub = default_subsystem() if btype == "Subsystem" else None
        size = (80.0, 50.0) if btype == "Subsystem" else (70.0, 40.0)
        block = Block(bid, btype, position=(_snap(pos[0]), _snap(pos[1])), size=size,
                      subsystem=sub)
        self._apply(self.model.add_block(block))
        return bid

    def connect(self, src: str, src_port: int, dst: str, dst_port: int) -> bool:
        if src == dst:
            return False
        model = self.model.disconnect(dst, dst_port)  # a new wire replaces the old one
        try:
            self._apply(model.connect(src, src_port, dst, dst_port))
        except EngStudioError as exc:
            self.statusBar().showMessage(str(exc), 5000)
            return False
        return True

    def delete(self, block_ids: list[str], lines: list[Line] = ()) -> None:
        model = self.model
        for bid in block_ids:
            model = model.remove_block(bid)
        for ln in lines:
            model = model.disconnect(ln.dst, ln.dst_port)
        if model is not self.model:
            self._apply(model)

    def delete_selected(self) -> None:
        blocks = [i.block.id for i in self.scene.selectedItems() if isinstance(i, BlockItem)]
        lines = [i.line_ref for i in self.scene.selectedItems() if isinstance(i, LineItem)]
        self.delete(blocks, lines)

    def set_block(self, block: Block) -> None:
        self._apply(self.model.update_block(block))

    def sync_positions(self) -> None:
        moved = self.model
        for bid, item in self._items.items():
            pos = (_snap(item.pos().x()), _snap(item.pos().y()))
            if pos != moved.block(bid).position:
                moved = moved.move_block(bid, pos)
        if moved is not self.model:
            self._apply(moved)

    # -- drawing -----------------------------------------------------------------------
    def redraw(self) -> None:
        selected = {i.block.id for i in self.scene.selectedItems() if isinstance(i, BlockItem)}
        self.scene.clear()
        self._items = {}
        for b in self.model.blocks:
            n_in, n_out = ports_of(b)
            summary = ", ".join(f"{k} = {format_param(v)}" for k, v in b.params)
            item = BlockItem(b, n_in, n_out, summary)
            self.scene.addItem(item)
            item.setSelected(b.id in selected)
            self._items[b.id] = item
        for ln in self.model.lines:
            src, dst = self._items.get(ln.src), self._items.get(ln.dst)
            if src and dst:
                self.scene.addItem(LineItem(ln, src.port_pos("out", ln.src_port),
                                            dst.port_pos("in", ln.dst_port)))
        rect = self.scene.itemsBoundingRect().adjusted(-200, -200, 200, 200)
        self.scene.setSceneRect(rect.united(QRectF(0, 0, 800, 500)))
        self._update_title()

    def _update_title(self) -> None:
        name = self.path.name if self.path else self.model.name
        self.setWindowTitle(f"{'*' if self.modified else ''}{name} - Simulation model")

    # -- block dialogs ---------------------------------------------------------------------
    def open_block(self, block_id: str) -> None:
        block = self.model.block(block_id)
        if block.type == "Subsystem":
            self.open_subsystem(block_id)
            return
        dlg = ParamDialog(block, self._infos.get(block.type), self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_block is not None:
            self.set_block(dlg.result_block)

    def open_subsystem(self, block_id: str) -> SimEditor:
        block = self.model.block(block_id)
        child = SimEditor(block.subsystem, theme=self.theme, parent=self, is_subsystem=True)
        child.setWindowTitle(f"{block.name} (subsystem of {self.model.name})")

        def update(inner: Model) -> None:
            self.set_block(replace(self.model.block(block_id), subsystem=inner))

        child.model_changed.connect(update)
        self._children.append(child)
        child.show()
        return child

    def settings_dialog(self) -> None:
        dlg = SettingsDialog(self.model, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self._apply(self.model.with_settings(**dlg.changes()))
            except EngStudioError as exc:
                QMessageBox.warning(self, "Invalid settings", str(exc))

    # -- files ------------------------------------------------------------------------------
    def new_model(self) -> None:
        if not self._confirm_discard():
            return
        self.model, self.path, self.modified = Model("untitled"), None, False
        self._undo.clear()
        self._redo.clear()
        self.redraw()

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Open model", str(Path.cwd()),
                                              "Simulation models (*.esmodel)")
        if name:
            self.open_path(name)

    def open_path(self, path: str | Path) -> bool:
        try:
            model = serialization.load(path)
        except EngStudioError as exc:
            QMessageBox.warning(self, "Open model failed", str(exc))
            return False
        self.model, self.path, self.modified = model, Path(path), False
        self._undo.clear()
        self._redo.clear()
        self.redraw()
        return True

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        return self.save_to(self.path)

    def save_as(self) -> bool:
        name, _ = QFileDialog.getSaveFileName(self, "Save model", str(Path.cwd() / "model.esmodel"),
                                              "Simulation models (*.esmodel)")
        return bool(name) and self.save_to(name)

    def save_to(self, path: str | Path) -> bool:
        try:
            saved = serialization.save(self.model, path)
        except EngStudioError as exc:
            QMessageBox.warning(self, "Save model failed", str(exc))
            return False
        self.path, self.modified = saved, False
        self._update_title()
        self.statusBar().showMessage(f"Saved {saved}", 4000)
        return True

    def _confirm_discard(self) -> bool:
        if not self.modified or self.is_subsystem or not self.ask_to_save:
            return True
        answer = QMessageBox.question(
            self, "Unsaved model", "Save changes to the model first?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop_requested = True
            self._thread.wait(5000)
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # -- running ----------------------------------------------------------------------------
    def run_async(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self._thread = _RunThread(self.model)
        self._thread.progressed.connect(lambda f: self.progress.setValue(int(100 * f)))
        self._thread.succeeded.connect(self._finished)
        self._thread.failed.connect(self._failed)
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.statusBar().showMessage("Running...")
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop_requested = True

    def run_blocking(self):
        """Run in the calling thread (tests, scripts); returns the SimResult."""
        res = run_model(self.model)
        self._finished(res)
        return res

    def _done(self) -> None:
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)

    def _failed(self, message: str) -> None:
        self._done()
        self.progress.setValue(0)
        self.statusBar().showMessage("Simulation failed", 5000)
        bad = next((bid for bid in self._items if bid in message), None)
        if bad is not None:
            self.scene.clearSelection()
            self._items[bad].setSelected(True)
        QMessageBox.warning(self, "Simulation", message)

    def _finished(self, res) -> None:
        self._done()
        self.last_result = res
        self.progress.setValue(100)
        displays = "; ".join(f"{k}: {' '.join(f'{v:.6g}' for v in val)}"
                             for k, val in res.displays.items())
        self.statusBar().showMessage(f"Done: {len(res.tout)} points, {res.steps} steps"
                                     + (f" | {displays}" if displays else ""), 10000)
        for spec in scope_figures(res):
            win = FigureWindow(spec.number, self.theme, self)
            win.set_figure(spec)
            win.show()
            self.figures.append(win)
