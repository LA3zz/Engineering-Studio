"""Real kernel client that runs the interpreter in a worker thread of the GUI process (K1).

Same contract as every ``KernelClient``: for each ``execute`` the handlers receive ``Stdout`` and
``Diagnostics`` events as they happen, then one ``WorkspaceSummary`` and finally one
``ExecutionFinished`` (``ok``/``error``/``cancelled``). With ``threaded=True`` (default) requests
are queued and run one at a time on a daemon thread, so ``cancel`` can interrupt a running loop
and the window stays responsive; events are then delivered from the worker thread (the Qt
``KernelBridge`` marshals them to the GUI thread). ``threaded=False`` runs each request inside
``execute`` (deterministic, used by tests).

Command syntax: ``clear``, ``clearvars``, ``clc``, ``format`` and ``more`` may be written as
commands (``clear x y``); ``to_function_syntax`` rewrites such lines into calls before parsing.
The worker never dies: a Python bug inside a builtin becomes an ``E_INTERNAL`` diagnostic.
"""

from __future__ import annotations

import fnmatch
import logging
import queue
import re
import threading

import numpy as np

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import (
    Diagnostics,
    ExecStatus,
    ExecutionFinished,
    FigureClosed,
    FigureUpdate,
    OpenModel,
    Stdout,
    ToolboxFunction,
    ToolboxInfo,
    ToolboxList,
    VariableInfo,
    WorkspaceSummary,
)
from engstudio.app.sim_bindings import sim_functions
from engstudio.app.toolbox_bindings import toolbox_builtins
from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_analysis import install_analysis
from engstudio.lang.builtins_control import install_control
from engstudio.lang.builtins_controlplot import install_control_plots
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_data import install_data
from engstudio.lang.builtins_decomp import install_decomp
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.builtins_funcs import install_funcs
from engstudio.lang.builtins_plot import install_plot
from engstudio.lang.builtins_poly import install_poly
from engstudio.lang.builtins_sym import display_text, install_sym, preview_text
from engstudio.lang.interp import Cancelled, EvalError, Host, Interpreter
from engstudio.lang.values import CharArray, class_of, size_of

__all__ = ["InProcessKernelClient", "to_function_syntax"]

_log = logging.getLogger("engstudio.kernel")

FIGURE_INTERVAL = 1 / 30  # seconds between updates of one figure (animation throttle)

_COMMAND = re.compile(
    r"^(\s*)(clear|clearvars|clc|format|more|close|syms|hold|figure|clf|cla|drawnow|grid|axis|"
    r"legend|box|shading|colorbar|colormap)"
    r"((?:[ \t]+[A-Za-z_][\w.*]*)*)[ \t]*(?:([;,])[ \t]*(.*)|(%.*))?$"
)

_CATEGORIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "constants": ("Constants", (
        "pi", "e", "Inf", "inf", "NaN", "nan", "eps", "i", "j", "true", "false", "realmax",
        "realmin")),
    "matrices": ("Matrices and arrays", (
        "zeros", "ones", "eye", "linspace", "logspace", "repmat", "reshape", "diag", "triu",
        "tril", "meshgrid", "horzcat", "vertcat", "size", "numel", "length", "ndims", "fliplr",
        "flipud")),
    "elementary": ("Elementary math", (
        "abs", "sqrt", "exp", "log", "log2", "log10", "sin", "cos", "tan", "asin", "acos",
        "atan", "sinh", "cosh", "tanh", "floor", "ceil", "round", "fix", "sign", "mod", "rem",
        "atan2", "hypot", "real", "imag", "conj", "angle", "deg2rad", "rad2deg")),
    "data": ("Data analysis", (
        "sum", "prod", "mean", "min", "max", "cumsum", "cumprod", "any", "all", "sort", "find",
        "diff")),
    "linalg": ("Linear algebra", ("inv", "det", "trace", "rank", "cond", "rcond", "norm", "dot",
                                  "cross")),
    "decomp": ("Matrix decompositions", ("eig", "lu", "qr", "chol", "svd")),
    "types": ("Types and tests", (
        "class", "isa", "double", "logical", "char", "isequal", "isempty", "isscalar",
        "isvector", "isrow", "iscolumn", "ismatrix", "issquare", "isnumeric", "isreal",
        "iscomplex", "islogical", "ischar", "iscell", "isstruct", "is_function_handle", "isnan",
        "isinf", "isfinite")),
    "io": ("Input and output", ("disp", "fprintf", "sprintf", "num2str", "error", "warning")),
    "text": ("Strings", (
        "strcmp", "strcmpi", "strncmp", "strncmpi", "upper", "lower", "strtrim", "strrep",
        "strcat", "strsplit", "strjoin", "strfind", "contains", "startsWith", "endsWith",
        "str2double", "int2str", "mat2str", "blanks", "isspace", "isletter", "isdigit")),
    "structs": ("Structures and cells", (
        "struct", "fieldnames", "isfield", "rmfield", "numfields", "getfield", "setfield",
        "cell", "iscellstr", "cell2mat", "num2cell", "deal")),
    "functional": ("Functional programming", (
        "cellfun", "arrayfun", "feval", "func2str", "str2func")),
    "sets": ("Sets and counting", ("unique", "ismember", "nnz")),
    "operators": ("Operators as functions", (
        "plus", "minus", "times", "rdivide", "ldivide", "power", "mtimes", "mrdivide",
        "mldivide", "mpower", "eq", "ne", "lt", "le", "gt", "ge", "and", "or", "not", "uminus",
        "uplus", "transpose", "ctranspose", "colon")),
    "numerics": ("Numerical analysis", ("trapz", "cumtrapz", "interp1", "interp2")),
    "statistics": ("Statistics", ("std", "var", "median", "rms", "zscore", "quantile",
                                              "prctile", "ttest", "ttest2", "histcounts")),
    "signal": ("Signal processing", ("fft", "ifft")),
    "polynomials": ("Polynomials", ("poly", "roots", "polyval", "polyfit")),
    "solvers": ("Solvers and optimization", ("fzero", "fsolve", "fminsearch", "fminbnd",
                                                        "fminunc", "linprog")),
    "integration": ("Integration", ("integral", "integral2", "quad", "quadgk")),
    "odes": ("Differential equations", ("ode45", "ode23", "ode15s", "odeset")),
    "symbolic": ("Symbolic math", (
        "syms", "sym", "int", "limit", "taylor", "solve", "simplify", "expand", "factor",
        "subs", "laplace", "ilaplace", "latex", "symvar", "matlabFunction")),
    "control": ("Control systems", (
        "tf", "zpk", "ss", "pid", "pidstd", "feedback", "series", "parallel", "pole", "zero",
        "dcgain", "damp", "isstable", "stepinfo", "margin", "c2d", "tfdata", "zpkdata", "ssdata",
        "order", "isdt", "minreal", "step", "impulse", "initial", "lsim", "bode", "nyquist",
        "rlocus", "pzmap", "pidtune")),
    "simulation": ("Simulation", ("sim", "open_system")),
    "random": ("Random numbers", ("rand", "randn", "randi", "randperm", "rng")),
    "timing": ("Timing", ("tic", "toc")),
    "plotting": ("Plotting", (
        "figure", "gcf", "gca", "clf", "cla", "close", "hold", "ishold",
        "plot", "drawnow", "subplot", "axes", "title", "xlabel", "ylabel", "sgtitle", "grid",
        "box", "legend", "xlim", "ylim", "axis", "xticks", "yticks", "xticklabels",
        "yticklabels", "text", "set", "get", "bar", "stem", "stairs", "area", "scatter",
        "semilogx", "semilogy", "loglog", "histogram", "hist", "plot3", "scatter3", "surf",
        "mesh", "contour", "contourf", "zlabel", "zlim", "view", "colormap", "colorbar",
        "shading", "polarplot", "errorbar", "xline", "yline", "pause", "animatedline",
        "addpoints", "clearpoints", "saveas", "print", "exportgraphics")),
    "workspace": ("Workspace", ("clear", "clearvars", "clc", "format", "more", "who", "whos",
                                "exist")),
}


_MIDLINE_WORDS = frozenset(
    ("hold", "figure", "clf", "cla", "drawnow", "close", "grid", "axis", "legend", "box", "shading",
     "colorbar", "colormap"))


def _separators(line: str) -> list[int]:
    """Indices of ``;`` and ``,`` outside brackets, strings and comments."""
    found: list[int] = []
    depth, quote, prev, i = 0, "", "", 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == quote:
                if line[i + 1:i + 2] == quote:
                    i += 1
                else:
                    quote, prev = "", c
        elif c == "%":
            break
        elif c == '"' or (c == "'" and not (prev.isalnum() or prev in "_)]}'.")):
            quote = c
        elif c in "([{":
            depth += 1
            prev = c
        elif c in ")]}":
            depth = max(0, depth - 1)
            prev = c
        elif c in ";," and depth == 0:
            found.append(i)
            prev = c
        elif not c.isspace():
            prev = c
        i += 1
    return found


def _rewrite_command(line: str) -> str:
    m = _COMMAND.match(line)
    if not m:
        for k in _separators(line):  # ``bar(x); hold on``: a command after a separator
            tail = _COMMAND.match(line[k + 1:])
            if tail and tail.group(2) in _MIDLINE_WORDS:
                return line[:k + 1] + _rewrite_command(line[k + 1:])
        return line
    indent, word, args, term, rest, _comment = m.groups()
    call = ", ".join(f"'{a}'" for a in args.split())
    out = f"{indent}{word}({call}){term or ''}"
    rest = (rest or "").strip()
    if rest and not rest.startswith("%"):
        out += " " + _rewrite_command(rest)  # ``clc; clear all; x = 1``
    return out


def to_function_syntax(code: str) -> str:
    """Rewrite command-style statements (``clear x y``, ``syms x; f = x^2``) as calls.

    A command may be followed by more statements on the same line. Line numbers are preserved.
    """
    return "\n".join(_rewrite_command(line) for line in code.split("\n"))


class _KernelHost(Host):
    """Turns interpreter output into protocol events for the current request."""

    def __init__(self, deliver) -> None:
        self.request_id = 0
        self._deliver = deliver

    def display(self, name: str, value: object) -> None:
        self._deliver(Stdout(self.request_id, display_text(name, value)))

    def write(self, text: str) -> None:
        self._deliver(Stdout(self.request_id, text))

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        self._deliver(Diagnostics(self.request_id, (diagnostic,)))


def _error_diagnostic(exc: EngStudioError) -> Diagnostic:
    message = str(exc)
    stack = getattr(exc, "stack", None)
    if isinstance(exc, EvalError) and stack:
        frames = [f"  in {name} (line {loc.line})" if loc else f"  in {name}"
                  for name, loc in stack]
        message += "\n" + "\n".join(frames)
    return Diagnostic(
        severity="error", code=getattr(exc, "code", "E") or "E", message=message,
        location=getattr(exc, "location", None),
    )


class InProcessKernelClient(KernelClient):
    def __init__(self, threaded: bool = True) -> None:
        super().__init__()
        self._threaded = threaded
        self._deliver = self._safe_emit if threaded else self._emit
        self._host = _KernelHost(self._deliver)
        self._interp = Interpreter(host=self._host)
        install_core(self._interp)
        install_decomp(self._interp)
        install_extra(self._interp)
        install_poly(self._interp)
        install_data(self._interp)
        install_funcs(self._interp)
        install_analysis(self._interp)
        install_sym(self._interp)
        install_control(self._interp)
        self._figures = install_plot(
            self._interp, self._publish_figure, self._retire_figure,
            min_interval=FIGURE_INTERVAL)
        install_control_plots(self._interp, self._figures)
        self._interp.functions.update(self._workspace_commands())
        self._toolbox_categories = self._install_toolboxes()
        self._interp.functions.update(sim_functions(
            self._interp, self._figures,
            lambda path: self._deliver(OpenModel(self._host.request_id, path))))
        self._next_id = 1
        self._closed = False
        self._lock = threading.Lock()
        self._current: int | None = None
        self._pending: set[int] = set()  # queued, not yet started
        self._cancelled: set[int] = set()  # queued requests cancelled before they started
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        if threaded:
            self._thread = threading.Thread(
                target=self._worker, name="engstudio-kernel", daemon=True)
            self._thread.start()

    # ------------------------------------------------------------ KernelClient
    def execute(self, code: str, file: str | None = None) -> int:
        rid = self._new_id()
        if self._threaded:
            with self._lock:
                self._pending.add(rid)
            self._queue.put((rid, code, file))
        else:
            self._run(rid, code, file)
        return rid

    def cancel(self, request_id: int) -> None:
        with self._lock:
            if request_id == self._current:
                self._interp.cancel()
            elif request_id in self._pending:
                self._cancelled.add(request_id)

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread is not None:
            with self._lock:
                if self._current is not None:
                    self._interp.cancel()
            self._queue.put(None)
            self._thread.join(timeout=10)

    def figure_closed(self, number: int) -> None:
        # Runs between requests (worker queue), never in the middle of a running script.
        if self._closed:
            return
        if self._threaded:
            self._queue.put(lambda: self._forget_figure(number))
        else:
            self._forget_figure(number)

    def _forget_figure(self, number: int) -> None:
        if number in self._figures.numbers():
            self._figures.close(number)
            self._figures.publisher.forget(number)  # type: ignore[union-attr]

    def list_toolboxes(self) -> int:
        rid = self._new_id()
        available = set(self._interp.functions)
        boxes: list[ToolboxInfo] = []
        listed: set[str] = set()
        for key, (title, names) in {**_CATEGORIES, **self._toolbox_categories}.items():
            present = sorted(n for n in names if n in available)
            listed.update(present)
            if present:
                boxes.append(ToolboxInfo(key, title, tuple(
                    ToolboxFunction(n, "", f"{n}(...)") for n in present)))
        rest = sorted(available - listed)
        if rest:
            boxes.append(ToolboxInfo("other", "Other functions", tuple(
                ToolboxFunction(n, "", f"{n}(...)") for n in rest)))
        self._emit(ToolboxList(rid, tuple(boxes)))
        return rid

    # ----------------------------------------------------------------- internals
    def _new_id(self) -> int:
        if self._closed:
            raise EngStudioError("kernel client is shut down")
        with self._lock:
            rid = self._next_id
            self._next_id += 1
        return rid

    def _safe_emit(self, event) -> None:
        for handler in list(self._handlers):
            try:
                handler(event)
            except Exception:
                _log.exception("kernel event handler failed")

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                if callable(item):  # internal job such as figure_closed
                    item()
                    continue
                self._run(*item)
            except Exception:  # never let the worker die
                _log.exception("kernel request failed")

    def _run(self, rid: int, code: str, file: str | None = None) -> None:
        status: ExecStatus = "ok"
        with self._lock:
            self._pending.discard(rid)
            skip = rid in self._cancelled
            self._cancelled.discard(rid)
            if not skip:
                self._current = rid
                self._host.request_id = rid
                self._interp.clear_cancel()
        if skip:
            status = "cancelled"
        else:
            try:
                self._interp.execute(to_function_syntax(code), file, reset_cancel=False)
            except Cancelled:
                status = "cancelled"
            except EngStudioError as exc:
                self._deliver(Diagnostics(rid, (_error_diagnostic(exc),)))
                status = "error"
            except Exception as exc:
                _log.exception("internal interpreter error")
                self._deliver(Diagnostics(rid, (Diagnostic(
                    severity="error", code="E_INTERNAL",
                    message=f"Internal error: {type(exc).__name__}: {exc}"),)))
                status = "error"
            finally:
                with self._lock:
                    self._current = None
                self._flush_figures()
        self._deliver(WorkspaceSummary(rid, self._variables()))
        self._deliver(ExecutionFinished(rid, status))

    def _install_toolboxes(self) -> dict[str, tuple[str, tuple[str, ...]]]:
        """Engineering toolboxes (Phase 8). A toolbox never replaces an existing builtin, and a
        toolbox that fails to load never stops the kernel from starting."""
        try:
            builtins, categories = toolbox_builtins()
        except Exception:
            _log.exception("toolboxes failed to load")
            return {}
        for name, fn in builtins.items():
            if name in self._interp.functions:
                _log.warning("toolbox function %s hides nothing: name already taken", name)
                continue
            self._interp.functions[name] = fn
        return categories

    def _flush_figures(self) -> None:
        try:
            self._figures.publisher.flush()  # type: ignore[union-attr]
        except Exception:  # a figure that cannot be drawn must not hide the run's result
            _log.exception("figure flush failed")

    def _publish_figure(self, spec) -> None:
        self._deliver(FigureUpdate(self._host.request_id, spec))

    def _retire_figure(self, number: int) -> None:
        self._deliver(FigureClosed(self._host.request_id, number))

    def _variables(self) -> tuple[VariableInfo, ...]:
        ws = self._interp.workspace
        return tuple(
            VariableInfo(name, class_of(ws[name]), size_of(ws[name]), preview_text(ws[name]))
            for name in sorted(ws.names())
        )

    def _workspace_commands(self) -> dict:
        interp = self._interp
        host = self._host

        def names_of(args: list) -> list[str]:
            out = []
            for a in args:
                if not isinstance(a, CharArray):
                    raise EngStudioError("names must be character vectors")
                out.append(a.to_str())
            return out

        def clear(args: list, nargout: int) -> list:
            names = names_of(args)
            if not names or names in (["all"], ["variables"]):
                interp.workspace.clear()
                if names == ["all"]:  # the running script keeps its own local functions
                    for fname in list(interp.user_functions):
                        if fname not in interp.script_functions:
                            del interp.user_functions[fname]
                return []
            for pattern in names:
                matches = fnmatch.filter(interp.workspace.names(), pattern)
                interp.workspace.clear(*matches)
            return []

        def noop(args: list, nargout: int) -> list:
            return []

        def fmt(args: list, nargout: int) -> list:
            names = names_of(args)
            if names == ["short", "g"]:
                host.diagnostic(Diagnostic(
                    severity="info", code="I_FORMAT",
                    message="format short g is shown as format short (not implemented yet)"))
            elif names not in ([], ["short"]):
                host.diagnostic(Diagnostic(
                    severity="warning", code="W_FORMAT",
                    message="format long is not supported yet; output stays in short format"))
            return []

        def who(args: list, nargout: int) -> list:
            names = interp.workspace.names()
            if names:
                host.write("Your variables are:\n\n" + "  ".join(sorted(names)) + "\n\n")
            return []

        def whos(args: list, nargout: int) -> list:
            rows = interp.workspace.summary()
            if rows:
                lines = ["  Name".ljust(12) + "Size".ljust(12) + "Class"]
                for name, cls, (r, c) in sorted(rows):
                    lines.append(f"  {name}".ljust(12) + f"{r}x{c}".ljust(12) + cls)
                host.write("\n".join(lines) + "\n\n")
            return []

        def exist(args: list, nargout: int) -> list:
            (name,) = names_of(args[:1]) or [""]
            if name in interp.workspace:
                code = 1.0
            elif name in interp.user_functions:
                code = 2.0
            elif name in interp.functions:
                code = 5.0
            else:
                code = 0.0
            return [np.array([[code]])]

        return {"clear": clear, "clearvars": clear, "clc": noop, "more": noop, "format": fmt,
                "who": who, "whos": whos, "exist": exist}
