"""P5.1 patch: figure state in the kernel. Exact-match and idempotent. Run from the project root."""

from pathlib import Path

SRC = Path("src/engstudio")


def sub(rel: str, old: str, new: str) -> None:
    path = SRC / rel
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    if new in text:
        print(f"already applied: {rel}: {new.strip()[:50]!r}")
        return
    if text.count(old) != 1:
        raise SystemExit(f"{rel}: anchor not found exactly once: {old.strip()[:60]!r}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace(old, new, 1))
    print(f"patched: {rel}")


# -- plotting.model: FigureSpec.name (window title text, not drawn inside the figure)
sub("plotting/model.py",
    "    rows: int = 1\n    cols: int = 1\n\n    def __post_init__",
    "    rows: int = 1\n    cols: int = 1\n    name: str = \"\"\n\n    def __post_init__")
sub("plotting/model.py",
    "        _text(\"title\", self.title)\n        axes = tuple(self.axes)",
    "        _text(\"title\", self.title)\n        _text(\"name\", self.name)\n"
    "        axes = tuple(self.axes)")

# -- gui.figure_window: window title uses the figure name
sub("gui/figure_window.py",
    "        self.setWindowTitle(\n"
    "            f\"Figure {self.number}: {spec.title}\" if spec.title "
    "else f\"Figure {self.number}\")",
    "        label = spec.name or spec.title\n"
    "        self.setWindowTitle(f\"Figure {self.number}: {label}\" if label\n"
    "                            else f\"Figure {self.number}\")")

# -- kernel protocol: FigureClosed
sub("app/kernel/protocol.py",
    "Event = (\n",
    "@dataclass(frozen=True)\n"
    "class FigureClosed:\n"
    "    \"\"\"The script closed figure ``number`` (the GUI closes its window).\"\"\"\n\n"
    "    request_id: int\n"
    "    number: int\n\n\n"
    "Event = (\n")
sub("app/kernel/protocol.py", "    | FigureUpdate\n)", "    | FigureUpdate | FigureClosed\n)")

# -- in-process kernel
K = "app/kernel/inprocess.py"
sub(K, "    ExecutionFinished,\n    Stdout,",
    "    ExecutionFinished,\n    FigureClosed,\n    FigureUpdate,\n    Stdout,")
sub(K, "from engstudio.lang.builtins_funcs import install_funcs\n",
    "from engstudio.lang.builtins_funcs import install_funcs\n"
    "from engstudio.lang.builtins_plot import install_plot\n")
sub(K, "(clear|clearvars|clc|format|more|close|syms)",
    "(clear|clearvars|clc|format|more|close|syms|hold|figure|clf|cla|drawnow)")
sub(K, "def _rewrite_command(line: str) -> str:\n    m = _COMMAND.match(line)\n"
       "    if not m:\n        return line\n",
    "def _separators(line: str) -> list[int]:\n"
    "    \"\"\"Indices of ``;`` and ``,`` outside brackets, strings and comments.\"\"\"\n"
    "    found: list[int] = []\n"
    "    depth, quote, prev, i = 0, \"\", \"\", 0\n"
    "    while i < len(line):\n"
    "        c = line[i]\n"
    "        if quote:\n"
    "            if c == quote:\n"
    "                if line[i + 1:i + 2] == quote:\n"
    "                    i += 1\n"
    "                else:\n"
    "                    quote, prev = \"\", c\n"
    "        elif c == \"%\":\n"
    "            break\n"
    "        elif c == '\"' or (c == \"'\" and not (prev.isalnum() or prev in \"_)]}'.\")):\n"
    "            quote = c\n"
    "        elif c in \"([{\":\n"
    "            depth += 1\n"
    "            prev = c\n"
    "        elif c in \")]}\":\n"
    "            depth = max(0, depth - 1)\n"
    "            prev = c\n"
    "        elif c in \";,\" and depth == 0:\n"
    "            found.append(i)\n"
    "            prev = c\n"
    "        elif not c.isspace():\n"
    "            prev = c\n"
    "        i += 1\n"
    "    return found\n\n\n"
    "def _rewrite_command(line: str) -> str:\n    m = _COMMAND.match(line)\n"
    "    if not m:\n"
    "        for k in _separators(line):  # ``bar(x); hold on``: a command after a separator\n"
    "            if _COMMAND.match(line[k + 1:]):\n"
    "                return line[:k + 1] + _rewrite_command(line[k + 1:])\n"
    "        return line\n")
sub(K, "        install_sym(self._interp)\n",
    "        install_sym(self._interp)\n"
    "        self._figures = install_plot(\n"
    "            self._interp, self._publish_figure, self._retire_figure)\n")
sub(K, "\"exist\", \"close\")),\n}", "\"exist\")),\n}")
sub(K, "    \"workspace\": (\"Workspace\",",
    "    \"plotting\": (\"Plotting\", (\n"
    "        \"figure\", \"gcf\", \"gca\", \"clf\", \"cla\", \"close\", \"hold\", \"ishold\",\n"
    "        \"plot\", \"drawnow\")),\n"
    "    \"workspace\": (\"Workspace\",")
sub(K, "                \"close\": noop, \"who\": who,", "                \"who\": who,")
sub(K, "    def _variables(self) -> tuple[VariableInfo, ...]:",
    "    def _publish_figure(self, spec) -> None:\n"
    "        self._deliver(FigureUpdate(self._host.request_id, spec))\n\n"
    "    def _retire_figure(self, number: int) -> None:\n"
    "        self._deliver(FigureClosed(self._host.request_id, number))\n\n"
    "    def _variables(self) -> tuple[VariableInfo, ...]:")

# -- main window
W = "gui/main_window.py"
sub(W, "import ExecutionFinished, FigureUpdate\n",
    "import ExecutionFinished, FigureClosed, FigureUpdate\n")
sub(W, "            self.show_figure(event.figure)\n"
       "        elif isinstance(event, ExecutionFinished):",
    "            self.show_figure(event.figure)\n"
    "        elif isinstance(event, FigureClosed):\n"
    "            self.close_figure(event.number)\n"
    "        elif isinstance(event, ExecutionFinished):")
sub(W, "    def _figure_closed(self, number: int) -> None:",
    "    def close_figure(self, number: int) -> None:\n"
    "        \"\"\"Close the window of figure ``number`` if it is open.\"\"\"\n"
    "        window = self.figures.pop(number, None)\n"
    "        if window is not None:\n"
    "            window.close()\n\n"
    "    def _figure_closed(self, number: int) -> None:")
print("done")
