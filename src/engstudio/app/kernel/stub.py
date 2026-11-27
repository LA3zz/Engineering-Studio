"""Stub kernel for GUI development. NOT an interpreter.

Supported, one statement per line (``%`` starts a comment, trailing ``;`` hides the echo):
    name = <numeric literal>     stores a 1x1 double exactly as typed
    name                         shows an existing variable (error if undefined)
    clear                        removes all variables
    clear name [name ...]        removes the named variables (unknown names are ignored)
    demo_plot [N]                emits a sample figure (number N, default 1)
Everything else yields an ``E_STUB`` error. It computes nothing; it only lets the Command
Window and Workspace browser be built and tested before the real kernel exists.
"""

from __future__ import annotations

import re

import numpy as np

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import (
    Diagnostics,
    ExecutionFinished,
    FigureUpdate,
    Stdout,
    ToolboxFunction,
    ToolboxInfo,
    ToolboxList,
    VariableInfo,
    WorkspaceSummary,
)
from engstudio.core.diagnostics import SourceLoc, error
from engstudio.core.errors import EngStudioError
from engstudio.lang.lexer import KEYWORDS
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_NUMBER = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
_ASSIGN = re.compile(rf"^({_NAME})\s*=\s*({_NUMBER})$")
_CLEAR = re.compile(rf"^clear(?:\s+({_NAME}(?:\s+{_NAME})*))?$")
_NAME_ONLY = re.compile(rf"^{_NAME}$")
_DEMO = re.compile(r"^demo_plot(?:\s+(\d+))?$")

_HELP = (
    "stub kernel: only 'name = <number>', 'clear' and 'clear name' are supported "
    "(the interpreter is not connected yet)"
)


# Sample catalogue for GUI development only: names come from the architecture plan and are
# NOT implemented functions.
SAMPLE_TOOLBOXES: tuple[ToolboxInfo, ...] = (
    ToolboxInfo("control", "Control Systems (sample)", (
        ToolboxFunction("bode", "Bode plot of a transfer function", "bode(sys)"),
        ToolboxFunction("step", "Step response of a system", "step(sys)"),
        ToolboxFunction("tf", "Create a transfer function", "tf(num, den)"),
    )),
    ToolboxInfo("mathematics", "Mathematics (sample)", (
        ToolboxFunction("det", "Determinant of a square matrix", "det(A)"),
        ToolboxFunction("eig", "Eigenvalues and eigenvectors", "eig(A)"),
        ToolboxFunction("inv", "Matrix inverse", "inv(A)"),
        ToolboxFunction("trapz", "Trapezoidal numerical integration", "trapz(x, y)"),
    )),
)


def demo_figure(number: int = 1) -> FigureSpec:
    """Small figure for developing the Figure window (sample data, not a result)."""
    x = np.linspace(0.0, 2.0 * np.pi, 50)
    lines = AxesSpec(
        series=(
            SeriesSpec("line", x, np.sin(x), label="sin(x)"),
            SeriesSpec("line", x, np.cos(x), label="cos(x)", line_style="--"),
        ),
        title="Lines", xlabel="x (rad)", ylabel="value", grid=True, legend=True,
    )
    bars = AxesSpec(
        series=(
            SeriesSpec("bar", [1, 2, 3, 4], [3, 5, 2, 4], label="counts"),
            SeriesSpec("scatter", [1, 2, 3, 4], [3, 5, 2, 4], marker="s", color="#d62728"),
        ),
        title="Bars and points", xlabel="item", ylabel="count",
    )
    return FigureSpec(
        number=number, title="demo_plot (sample data from the stub kernel)",
        axes=(lines, bars), rows=1, cols=2,
    )


def format_double(v: float) -> str:
    """Short display format: integers plain, otherwise 4 decimals (or exponent form)."""
    if v == int(v) and abs(v) < 1e9:
        return str(int(v))
    if 1e-3 <= abs(v) < 1e5:
        return f"{v:.4f}"
    return f"{v:.4e}"


class StubKernelClient(KernelClient):
    def __init__(self) -> None:
        super().__init__()
        self._vars: dict[str, float] = {}
        self._next_id = 1
        self._closed = False

    def cancel(self, request_id: int) -> None:
        return None  # execution is synchronous: nothing can be running

    def shutdown(self) -> None:
        self._closed = True

    def list_toolboxes(self) -> int:
        if self._closed:
            raise EngStudioError("kernel client is shut down")
        rid = self._next_id
        self._next_id += 1
        self._emit(ToolboxList(rid, SAMPLE_TOOLBOXES))
        return rid

    def execute(self, code: str, file: str | None = None) -> int:
        if self._closed:
            raise EngStudioError("kernel client is shut down")
        rid = self._next_id
        self._next_id += 1
        status = "ok"
        for lineno, raw in enumerate(code.splitlines(), start=1):
            line = raw.split("%", 1)[0].strip()
            if not line:
                continue
            hide = line.endswith(";")
            line = line.rstrip(";").strip()
            problem = self._run_line(rid, line, hide)
            if problem:
                loc = SourceLoc(file, lineno, 1)
                self._emit(Diagnostics(rid, (error("E_STUB", problem, loc),)))
                status = "error"
                break
        self._emit(WorkspaceSummary(rid, self._summary()))
        self._emit(ExecutionFinished(rid, status))
        return rid

    # -- internals -----------------------------------------------------------
    def _run_line(self, rid: int, line: str, hide: bool) -> str | None:
        """Execute one statement; returns an error message or None."""
        m = _ASSIGN.match(line)
        if m:
            name = m.group(1)
            if name in KEYWORDS:
                return f"'{name}' is a reserved keyword and cannot be a variable name"
            value = float(m.group(2))
            self._vars[name] = value
            if not hide:
                self._emit(Stdout(rid, f"{name} =\n\n     {format_double(value)}\n\n"))
            return None
        m = _CLEAR.match(line)
        if m:
            if m.group(1) is None:
                self._vars.clear()
            else:
                for name in m.group(1).split():
                    self._vars.pop(name, None)
            return None
        m = _DEMO.match(line)
        if m:
            number = int(m.group(1)) if m.group(1) else 1
            if number < 1:
                return "figure number must be 1 or greater"
            self._emit(FigureUpdate(rid, demo_figure(number)))
            return None
        if _NAME_ONLY.match(line) and line not in KEYWORDS:
            if line in self._vars:
                if not hide:
                    shown = format_double(self._vars[line])
                    self._emit(Stdout(rid, f"{line} =\n\n     {shown}\n\n"))
                return None
            return f"Unrecognized function or variable '{line}'."
        return _HELP

    def _summary(self) -> tuple[VariableInfo, ...]:
        return tuple(
            VariableInfo(n, "double", (1, 1), format_double(v))
            for n, v in sorted(self._vars.items())
        )
