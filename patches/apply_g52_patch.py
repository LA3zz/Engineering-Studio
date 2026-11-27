"""G5.2 patch: demo_plot command in the stub kernel and figure windows in MainWindow
(exact-match, idempotent). Run from the project root: python patches\\apply_g52_patch.py

First checks that pyqtgraph is installed; if not it stops WITHOUT changing anything."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import pyqtgraph
except ImportError:
    sys.exit("pyqtgraph is NOT installed in this environment. Nothing was changed. "
             "Tell Claude; do not install it before agreeing on the version.")
print(f"pyqtgraph {pyqtgraph.__version__} found")
_lock = Path("requirements.lock.txt")
if _lock.exists() and "pyqtgraph" not in _lock.read_text(encoding="utf-8-sig").lower():
    print("WARNING: pyqtgraph is installed but not listed in requirements.lock.txt")

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio")

STUB = [
    ("import re\n\nfrom engstudio.app.kernel.client import KernelClient\n",
     "import re\n\nimport numpy as np\n\nfrom engstudio.app.kernel.client import KernelClient\n"),
    ("    ExecutionFinished,\n    Stdout,\n",
     "    ExecutionFinished,\n    FigureUpdate,\n    Stdout,\n"),
    ("from engstudio.lang.lexer import KEYWORDS\n",
     "from engstudio.lang.lexer import KEYWORDS\n"
     "from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec\n"),
    ('_NAME_ONLY = re.compile(rf"^{_NAME}$")\n',
     '_NAME_ONLY = re.compile(rf"^{_NAME}$")\n'
     '_DEMO = re.compile(r"^demo_plot(?:\\s+(\\d+))?$")\n'),
    ("    clear name [name ...]        removes the named variables (unknown names are ignored)\n",
     "    clear name [name ...]        removes the named variables (unknown names are ignored)\n"
     "    demo_plot [N]                emits a sample figure (number N, default 1)\n"),
    ("def format_double(v: float) -> str:\n",
     "def demo_figure(number: int = 1) -> FigureSpec:\n"
     '    """Small figure for developing the Figure window (sample data, not a result)."""\n'
     "    x = np.linspace(0.0, 2.0 * np.pi, 50)\n"
     "    lines = AxesSpec(\n"
     "        series=(\n"
     '            SeriesSpec("line", x, np.sin(x), label="sin(x)"),\n'
     '            SeriesSpec("line", x, np.cos(x), label="cos(x)", line_style="--"),\n'
     "        ),\n"
     '        title="Lines", xlabel="x (rad)", ylabel="value", grid=True, legend=True,\n'
     "    )\n"
     "    bars = AxesSpec(\n"
     "        series=(\n"
     '            SeriesSpec("bar", [1, 2, 3, 4], [3, 5, 2, 4], label="counts"),\n'
     '            SeriesSpec("scatter", [1, 2, 3, 4], [3, 5, 2, 4], marker="s", color="#d62728"),\n'
     "        ),\n"
     '        title="Bars and points", xlabel="item", ylabel="count",\n'
     "    )\n"
     "    return FigureSpec(\n"
     "        number=number, title=\"demo_plot (sample data from the stub kernel)\",\n"
     "        axes=(lines, bars), rows=1, cols=2,\n"
     "    )\n\n\n"
     "def format_double(v: float) -> str:\n"),
    ("        if _NAME_ONLY.match(line) and line not in KEYWORDS:\n",
     "        m = _DEMO.match(line)\n"
     "        if m:\n"
     "            number = int(m.group(1)) if m.group(1) else 1\n"
     "            if number < 1:\n"
     '                return "figure number must be 1 or greater"\n'
     "            self._emit(FigureUpdate(rid, demo_figure(number)))\n"
     "            return None\n"
     "        if _NAME_ONLY.match(line) and line not in KEYWORDS:\n"),
]
MAIN = [
    ("from engstudio.app.kernel.client import KernelClient\n",
     "from engstudio.app.kernel.client import KernelClient\n"
     "from engstudio.app.kernel.protocol import FigureUpdate\n"),
    ("from engstudio.gui.editor_tabs import ScriptTabs\n",
     "from engstudio.gui.editor_tabs import ScriptTabs\n"
     "from engstudio.gui.figure_window import FigureWindow\n"),
    ("from engstudio.gui.toolbox_panel import ToolboxPanel\n",
     "from engstudio.gui.toolbox_panel import ToolboxPanel\n"
     "from engstudio.plotting.model import FigureSpec\n"),
    ("        self.command_window = None\n",
     "        self.command_window = None\n"
     "        self.figures: dict[int, FigureWindow] = {}\n"),
    ("            self.toolbox_panel.insert_requested.connect(self.insert_in_command)\n",
     "            self.toolbox_panel.insert_requested.connect(self.insert_in_command)\n"
     "        if self.bridge is not None:\n"
     "            self.bridge.event.connect(self._on_kernel_event)\n"),
    ("        self.tabs.set_theme(name)\n",
     "        self.tabs.set_theme(name)\n"
     "        for window in self.figures.values():\n"
     "            window.set_theme(name)\n"),
    ("            self.bridge.shutdown()\n        event.accept()\n",
     "            self.bridge.shutdown()\n"
     "        for window in list(self.figures.values()):\n"
     "            window.close()\n"
     "        event.accept()\n"),
    ("    def clear_command(self) -> None:\n",
     "    def _on_kernel_event(self, event: object) -> None:\n"
     "        if isinstance(event, FigureUpdate):\n"
     "            self.show_figure(event.figure)\n\n"
     "    def show_figure(self, spec: FigureSpec) -> FigureWindow:\n"
     '        """Open the window for ``spec.number`` or update it if it already exists."""\n'
     "        window = self.figures.get(spec.number)\n"
     "        if window is None:\n"
     "            window = FigureWindow(spec.number, self.theme, self)\n"
     "            window.closed.connect(self._figure_closed)\n"
     "            self.figures[spec.number] = window\n"
     "        window.set_figure(spec)\n"
     "        window.show()\n"
     "        window.raise_()\n"
     "        return window\n\n"
     "    def _figure_closed(self, number: int) -> None:\n"
     "        self.figures.pop(number, None)\n\n"
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


patch(SRC / "app" / "kernel" / "stub.py", STUB)
patch(SRC / "gui" / "main_window.py", MAIN)
