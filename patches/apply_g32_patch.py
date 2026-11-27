"""G3.2 patch (exact-match, idempotent). Run from the project root:
    python patches\\apply_g32_patch.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio")

PROTOCOL = [
    ("class Shutdown:\n    pass\n",
     "class Shutdown:\n    pass\n\n\n@dataclass(frozen=True)\nclass ListToolboxes:\n"
     "    request_id: int\n"),
    ("Event = Stdout | Diagnostics | WorkspaceSummary | ExecutionFinished\n",
     '@dataclass(frozen=True)\nclass ToolboxFunction:\n'
     '    """One function listed in a toolbox. Plain data (no callable)."""\n\n'
     '    name: str\n    summary: str  # one line\n'
     '    signature: str = ""  # e.g. "inv(A)"\n\n\n'
     '@dataclass(frozen=True)\nclass ToolboxInfo:\n'
     '    name: str  # identifier, e.g. "mathematics"\n    display_name: str\n'
     '    functions: tuple[ToolboxFunction, ...]\n\n\n'
     '@dataclass(frozen=True)\nclass ToolboxList:\n    request_id: int\n'
     '    toolboxes: tuple[ToolboxInfo, ...]\n\n\n'
     'Event = Stdout | Diagnostics | WorkspaceSummary | ExecutionFinished | ToolboxList\n'),
]
CLIENT = [
    ("from engstudio.app.kernel.protocol import Event\n",
     "from engstudio.app.kernel.protocol import Event\n"
     "from engstudio.core.errors import NotSupportedError\n"),
    ('        """Release resources; further ``execute`` calls raise ``EngStudioError``."""\n',
     '        """Release resources; further ``execute`` calls raise ``EngStudioError``."""\n\n'
     '    def list_toolboxes(self) -> int:\n'
     '        """Request the toolbox catalogue; answered by one ``ToolboxList`` event.\n\n'
     '        Not abstract: clients without a catalogue raise ``NotSupportedError``.\n'
     '        """\n'
     '        raise NotSupportedError("this kernel client does not provide a toolbox list")\n'),
]
STUB = [
    ("    Stdout,\n    VariableInfo,\n",
     "    Stdout,\n    ToolboxFunction,\n    ToolboxInfo,\n    ToolboxList,\n    VariableInfo,\n"),
    ("def format_double(v: float) -> str:\n",
     "# Sample catalogue for GUI development only: names come from the architecture plan and are\n"
     "# NOT implemented functions.\n"
     "SAMPLE_TOOLBOXES: tuple[ToolboxInfo, ...] = (\n"
     '    ToolboxInfo("control", "Control Systems (sample)", (\n'
     '        ToolboxFunction("bode", "Bode plot of a transfer function", "bode(sys)"),\n'
     '        ToolboxFunction("step", "Step response of a system", "step(sys)"),\n'
     '        ToolboxFunction("tf", "Create a transfer function", "tf(num, den)"),\n'
     "    )),\n"
     '    ToolboxInfo("mathematics", "Mathematics (sample)", (\n'
     '        ToolboxFunction("det", "Determinant of a square matrix", "det(A)"),\n'
     '        ToolboxFunction("eig", "Eigenvalues and eigenvectors", "eig(A)"),\n'
     '        ToolboxFunction("inv", "Matrix inverse", "inv(A)"),\n'
     '        ToolboxFunction("trapz", "Trapezoidal numerical integration", "trapz(x, y)"),\n'
     "    )),\n"
     ")\n\n\n"
     "def format_double(v: float) -> str:\n"),
    ("    def execute(self, code: str) -> int:\n        if self._closed:\n",
     "    def list_toolboxes(self) -> int:\n"
     "        if self._closed:\n"
     '            raise EngStudioError("kernel client is shut down")\n'
     "        rid = self._next_id\n"
     "        self._next_id += 1\n"
     "        self._emit(ToolboxList(rid, SAMPLE_TOOLBOXES))\n"
     "        return rid\n\n"
     "    def execute(self, code: str) -> int:\n        if self._closed:\n"),
]
BRIDGE = [
    ("    def execute(self, code: str) -> int:\n        return self._client.execute(code)\n",
     "    def execute(self, code: str) -> int:\n        return self._client.execute(code)\n\n"
     "    def list_toolboxes(self) -> int:\n        return self._client.list_toolboxes()\n"),
]
PANELS = [
    ("from engstudio.gui.settings import UiSettings\n",
     "from engstudio.gui.settings import UiSettings\n"
     "from engstudio.gui.toolbox_panel import ToolboxPanel\n"),
    ('_placeholder("Toolboxes", "G3"),', "_toolboxes,"),
    ("def _folder(ctx: PanelContext) -> QWidget:\n    return FolderPanel(ctx.settings)\n",
     "def _folder(ctx: PanelContext) -> QWidget:\n    return FolderPanel(ctx.settings)\n\n\n"
     "def _toolboxes(ctx: PanelContext) -> QWidget:\n    return ToolboxPanel(ctx.bridge)\n"),
]
MAIN = [
    ("from engstudio.gui.theme import THEMES, apply_theme, get_palette\n",
     "from engstudio.gui.theme import THEMES, apply_theme, get_palette\n"
     "from engstudio.gui.toolbox_panel import ToolboxPanel\n"),
    ("            self.folder_panel.open_file_requested.connect(self.tabs.open_path)\n",
     "            self.folder_panel.open_file_requested.connect(self.tabs.open_path)\n"
     '        tools = self.docks["toolboxes"].widget()\n'
     "        self.toolbox_panel = tools if isinstance(tools, ToolboxPanel) else None\n"
     "        if self.toolbox_panel is not None:\n"
     "            self.toolbox_panel.insert_requested.connect(self.insert_in_command)\n"),
    ("    def clear_command(self) -> None:\n",
     "    def insert_in_command(self, text: str) -> None:\n"
     "        \"\"\"Insert ``text`` at the cursor of the Command Window input and focus it.\"\"\"\n"
     "        if self.command_window is None:\n"
     "            return\n"
     '        self.docks["command"].show()\n'
     '        self.docks["command"].raise_()\n'
     "        self.command_window.input.insert(text)\n"
     "        self.command_window.focus_input()\n\n"
     "    def clear_command(self) -> None:\n"),
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


for rel, edits in [
    ("app/kernel/protocol.py", PROTOCOL), ("app/kernel/client.py", CLIENT),
    ("app/kernel/stub.py", STUB), ("gui/kernel_bridge.py", BRIDGE),
    ("gui/panels.py", PANELS), ("gui/main_window.py", MAIN),
]:
    patch(ROOT / rel, edits)
