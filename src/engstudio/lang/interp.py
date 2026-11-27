"""Tree-walking evaluator: ``Workspace``, ``Interpreter`` and ``EvalError`` (T3.4c).

Scope: expressions, assignment (including nested targets such as ``s.a(2) = 1`` and
``c{3}.x = 1``), calls of registered functions and function handles, anonymous functions with
captured variables, ``end`` inside indexes, ``&&``/``||`` short-circuiting, ``ans``, display
callbacks, control flow (``if``, ``for``, ``while``, ``switch``, ``try``/``catch``, ``break``,
``continue``, ``return``) and user-defined functions (own scope, several outputs, ``nargin``,
``nargout``, ``varargin``, ``varargout``, recursion, ``EvalError.stack`` frames).

Functions defined anywhere in a parsed program are registered before it runs, as MATLAB does
for functions in script files. Name resolution: variable, then user function, then registered
function. ``for`` iterates over the columns of its value (cells give 1-by-1 cells); ``try``
binds a struct with ``message`` and ``identifier`` to the catch variable. ``cancel()`` may be
called from another thread: the next statement or loop iteration raises ``Cancelled``, which
``try``/``catch`` never swallows. ``run`` raises the Python recursion limit while it executes
(and restores it) so ``max_depth`` levels of MATLAB recursion fit.

Function convention: ``functions[name](args, nargout) -> sequence of values`` where ``args`` is
a list of values and ``nargout`` the number of outputs requested (0 for a statement, 1 inside an
expression). Return fewer values for functions without output; extra values are dropped.
Plain Python numbers/arrays/strings in the result are converted with ``to_value``.

The interpreter never prints: ``Host.display(name, value)`` is called for unsuppressed
statements and ``Host.diagnostic(diag)`` for warnings. Errors raised while evaluating a node
become ``EvalError`` carrying that node's ``SourceLoc`` (the original error is ``__cause__``).
"""

from __future__ import annotations

import contextlib
import re
import sys
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence

import numpy as np

from engstudio.core.diagnostics import Diagnostic, SourceLoc
from engstudio.core.errors import EngStudioError, ValidationError
from engstudio.lang import ast as A
from engstudio.lang import indexing as ix
from engstudio.lang import ops, symops
from engstudio.lang.indexing import COLON
from engstudio.lang.parser import parse
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
    empty_double,
    is_true,
    is_value,
    size_of,
    to_value,
)

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
Env = MutableMapping[str, object]
Function = Callable[[list, int], object]


class EvalError(EngStudioError):
    """Runtime error with the source location of the failing node."""

    code = "E_EVAL"

    def __init__(self, message: str, location: SourceLoc | None = None) -> None:
        super().__init__(message)
        self.location = location
        #: calls the error passed through, innermost first: ``(function name, call location)``
        self.stack: list[tuple[str, SourceLoc | None]] = []

    def to_diagnostic(self, location: SourceLoc | None = None):  # type: ignore[override]
        return super().to_diagnostic(location or self.location)


class Cancelled(EngStudioError):
    """Execution was stopped with ``Interpreter.cancel()``; never caught by ``try``/``catch``."""

    code = "E_CANCELLED"


class _Signal(Exception):
    def __init__(self, loc: SourceLoc | None) -> None:
        super().__init__()
        self.loc = loc


class _Break(_Signal):
    pass


class _Continue(_Signal):
    pass


class _Return(_Signal):
    pass


@contextlib.contextmanager
def _recursion_limit(wanted: int) -> Iterator[None]:
    old = sys.getrecursionlimit()
    if wanted > old:
        sys.setrecursionlimit(wanted)
    try:
        yield
    finally:
        if wanted > old:
            sys.setrecursionlimit(old)


class Host:
    """Output callbacks; subclass and override (the defaults discard everything)."""

    def display(self, name: str, value: object) -> None:
        """An unsuppressed statement produced ``name = value``."""

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        """A warning (for example an ill-conditioned matrix) was raised."""

    def write(self, text: str) -> None:
        """Text printed by ``disp``/``fprintf`` (already newline-terminated by the caller)."""


class Workspace(MutableMapping):
    """Named values of the base workspace (insertion ordered, names validated)."""

    def __init__(self) -> None:
        self._vars: dict[str, object] = {}

    def __getitem__(self, name: str) -> object:
        return self._vars[name]

    def __setitem__(self, name: str, value: object) -> None:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise ValidationError(f"invalid variable name {name!r}")
        if not is_value(value):
            raise ValidationError(f"{name!r}: not an interpreter value ({type(value).__name__})")
        self._vars[name] = value

    def __delitem__(self, name: str) -> None:
        del self._vars[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._vars)

    def __len__(self) -> int:
        return len(self._vars)

    def names(self) -> list[str]:
        return list(self._vars)

    def clear(self, *names: str) -> None:  # type: ignore[override]
        """Remove the given variables (all when none are given); unknown names are ignored."""
        if not names:
            self._vars.clear()
        for name in names:
            self._vars.pop(name, None)

    def summary(self) -> list[tuple[str, str, tuple[int, int]]]:
        """``(name, class, size)`` for every variable."""
        return [(n, class_of(v), size_of(v)) for n, v in self._vars.items()]


def _scalar(x: float | bool) -> np.ndarray:
    return np.array([[x]], dtype=np.bool_ if isinstance(x, bool) else np.float64)


class Interpreter:
    def __init__(
        self,
        workspace: Workspace | None = None,
        functions: Mapping[str, Function] | None = None,
        host: Host | None = None,
        max_depth: int = 256,
    ) -> None:
        self.workspace = workspace if workspace is not None else Workspace()
        self.functions: dict[str, Function] = dict(functions or {})
        self.host = host if host is not None else Host()
        self.max_depth = max_depth
        self.user_functions: dict[str, A.FunctionDef] = {}
        self.script_functions: set[str] = set()  # local functions of the running program
        self._cancel = False
        self._end: list[tuple[object, int, int] | None] = []
        self._depth = 0

    # ------------------------------------------------------------ entry points
    def execute(self, source: str, file: str | None = None, reset_cancel: bool = True) -> None:
        """Parse and run ``source`` (``LexError``/``ParseError``/``EvalError`` on failure)."""
        self.run(parse(source, file), reset_cancel=reset_cancel)

    def cancel(self) -> None:
        """Ask the running program to stop (safe to call from another thread)."""
        self._cancel = True

    def clear_cancel(self) -> None:
        """Forget a pending ``cancel()`` (used by a runner that manages cancellation itself)."""
        self._cancel = False

    def check_cancel(self) -> None:
        """Raise ``Cancelled`` if a cancel is pending (for long-running builtins like pause)."""
        self._check_cancel()

    def run(self, program: A.Program, reset_cancel: bool = True) -> None:
        """Run a parsed program. ``reset_cancel=False`` keeps a cancel requested before the
        start, so the program stops at its first statement (no race with a runner thread)."""
        if reset_cancel:
            self._cancel = False
        self.script_functions = set()
        for stmt in program.body:
            if isinstance(stmt, A.FunctionDef):
                self.user_functions[stmt.name] = stmt
                self.script_functions.add(stmt.name)
        with _recursion_limit(self.max_depth * 40 + 1000):
            try:
                self._exec_block(program.body, self.workspace)
            except _Return:
                pass  # `return` at script level ends the script
            except _Signal as sig:
                word = "break" if isinstance(sig, _Break) else "continue"
                raise EvalError(f"'{word}' is only valid inside a loop.", sig.loc) from None
            except RecursionError:
                raise EvalError("Maximum recursion depth of the host was exceeded.") from None

    def call(self, f: object, args: Sequence[object], nargout: int = 1) -> list[object]:
        """Call a function handle or function name from Python code (builtins such as
        ``arrayfun`` or ``fzero``); returns the list of outputs."""
        handle = FunctionHandle(name=f) if isinstance(f, str) else f
        if not isinstance(handle, FunctionHandle):
            raise ValidationError(f"cannot call a {type(f).__name__} value")
        return self._call_handle(handle, list(args), nargout, A.Ident("<call>"))

    # --------------------------------------------------------------- statements
    def _check_cancel(self) -> None:
        if self._cancel:
            raise Cancelled("Execution cancelled by user.")

    def _exec_block(self, stmts: Sequence[A.Node], env: Env) -> None:
        for stmt in stmts:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, stmt: A.Node, env: Env) -> None:
        self._check_cancel()
        if isinstance(stmt, A.ExprStmt):
            self._expr_stmt(stmt, env)
        elif isinstance(stmt, A.Assign):
            self._assign(stmt, env)
        elif isinstance(stmt, A.If):
            self._if(stmt, env)
        elif isinstance(stmt, A.For):
            self._for(stmt, env)
        elif isinstance(stmt, A.While):
            self._while(stmt, env)
        elif isinstance(stmt, A.Switch):
            self._switch(stmt, env)
        elif isinstance(stmt, A.TryCatch):
            self._try(stmt, env)
        elif isinstance(stmt, A.Break):
            raise _Break(stmt.loc)
        elif isinstance(stmt, A.Continue):
            raise _Continue(stmt.loc)
        elif isinstance(stmt, A.Return):
            raise _Return(stmt.loc)
        elif isinstance(stmt, A.FunctionDef):
            self.user_functions[stmt.name] = stmt
        else:
            raise EvalError(f"{type(stmt).__name__} is not supported yet", stmt.loc)

    def _cond(self, node: A.Node, env: Env) -> bool:
        return self._guard(node, is_true, self.one(node, env))  # type: ignore[return-value]

    def _if(self, stmt: A.If, env: Env) -> None:
        for clause in stmt.clauses:
            if self._cond(clause.cond, env):
                self._exec_block(clause.body, env)
                return
        if stmt.else_body is not None:
            self._exec_block(stmt.else_body, env)

    def _while(self, stmt: A.While, env: Env) -> None:
        while self._cond(stmt.cond, env):
            self._check_cancel()
            try:
                self._exec_block(stmt.body, env)
            except _Break:
                break
            except _Continue:
                continue

    def _for(self, stmt: A.For, env: Env) -> None:
        subject = self.one(stmt.iterable, env)
        name = stmt.var.name
        if not isinstance(subject, (np.ndarray, CharArray, CellArray)):
            columns: Sequence[object] = [subject]
        else:
            cols = size_of(subject)[1]
            if cols == 0:
                env[name] = ix.index_value(subject, [COLON, np.zeros((1, 0))])
                return
            columns = _Columns(subject, cols)
        for column in columns:
            self._check_cancel()
            env[name] = column
            try:
                self._exec_block(stmt.body, env)
            except _Break:
                break
            except _Continue:
                continue

    def _switch(self, stmt: A.Switch, env: Env) -> None:
        subject = self.one(stmt.subject, env)
        bad_array = isinstance(subject, np.ndarray) and subject.size != 1
        bad_char = isinstance(subject, CharArray) and subject.shape[0] > 1
        if bad_array or bad_char or not isinstance(subject, (np.ndarray, CharArray)):
            raise EvalError(
                "SWITCH expression must be a scalar or character vector.", stmt.subject.loc
            )
        for case in stmt.cases:
            if _case_matches(subject, self.one(case.value, env)):
                self._exec_block(case.body, env)
                return
        if stmt.otherwise is not None:
            self._exec_block(stmt.otherwise, env)

    def _try(self, stmt: A.TryCatch, env: Env) -> None:
        try:
            self._exec_block(stmt.body, env)
        except Cancelled:
            raise
        except EngStudioError as exc:
            if stmt.catch_var:
                cause = exc.__cause__
                ident = getattr(cause, "identifier", getattr(exc, "identifier", None))
                if ident is None:
                    ident = getattr(exc, "code", "") or ""
                env[stmt.catch_var] = StructValue({"message": str(exc), "identifier": ident})
            self._exec_block(stmt.catch_body, env)

    def _expr_stmt(self, stmt: A.ExprStmt, env: Env) -> None:
        expr = stmt.expr
        if isinstance(expr, A.Ident) and expr.name in env:
            if stmt.printed:
                self.host.display(expr.name, env[expr.name])
            return
        for value in self.values(expr, env, nargout=0):
            env["ans"] = value
            if stmt.printed:
                self.host.display("ans", value)

    def _assign(self, stmt: A.Assign, env: Env) -> None:
        count = len(stmt.targets)
        vals = self.values(stmt.value, env, nargout=count)
        if count == 1:
            if not vals:
                if isinstance(stmt.value, A.CellIndex):
                    raise EvalError(
                        "Expected one output from a curly brace or dot indexing expression, "
                        "but there were 0 results.",
                        stmt.loc,
                    )
                raise EvalError("The right-hand side produced no value.", stmt.loc)
        elif len(vals) < count:
            raise EvalError("Too many output arguments.", stmt.loc)
        roots: list[str] = []
        for target, value in zip(stmt.targets, vals, strict=False):
            if isinstance(target, A.Tilde):
                continue
            self._store(target, value, env)
            roots.append(_root_name(target))
        if stmt.printed:
            for name in roots:
                self.host.display(name, env[name])

    # --------------------------------------------------------------- assignment
    def _current(self, node: A.Node, env: Env) -> object | None:
        """Existing value addressed by ``node`` or None when it does not exist yet."""
        if isinstance(node, A.Ident):
            return env.get(node.name)
        parent = self._current(node.target, env)  # type: ignore[attr-defined]
        if parent is None:
            return None
        try:
            if isinstance(node, A.Field):
                has_field = isinstance(parent, StructValue) and parent.has(node.name)
                return parent.get(node.name) if has_field else None  # type: ignore[union-attr]
            args = self._index_args(node.args, parent, env)  # type: ignore[attr-defined]
            if isinstance(node, A.CellIndex):
                items = ix.cell_contents(parent, args)
                return items[0] if len(items) == 1 else None
            return ix.index_value(parent, args)
        except EngStudioError:
            return None

    def _store(self, node: A.Node, value: object, env: Env) -> None:
        if isinstance(node, A.Ident):
            env[node.name] = value
            return
        parent = self._current(node.target, env)  # type: ignore[attr-defined]
        if isinstance(node, A.Field):
            new = self._guard(node, ix.set_field, parent, node.name, value)
        else:
            base = parent if parent is not None else empty_double()
            args = self._index_args(node.args, base, env)  # type: ignore[attr-defined]
            fn = ix.assign_cell_content if isinstance(node, A.CellIndex) else ix.assign_index
            new = self._guard(node, fn, parent, args, value)
        self._store(node.target, new, env)  # type: ignore[attr-defined]

    # -------------------------------------------------------------- expressions
    def one(self, node: A.Node, env: Env) -> object:
        """Evaluate ``node`` to exactly one value."""
        vals = self.values(node, env, nargout=1)
        if not vals and not isinstance(node, A.CellIndex):
            raise EvalError("The expression produced no value.", node.loc)
        if len(vals) != 1:
            raise EvalError(
                "Expected one output from a curly brace or dot indexing expression, "
                f"but there were {len(vals)} results.",
                node.loc,
            )
        return vals[0]

    def values(self, node: A.Node, env: Env, nargout: int = 1) -> list[object]:
        """Evaluate ``node``; calls and ``c{...}`` can yield zero or several values."""
        if isinstance(node, A.Number):
            return [_scalar(node.value)]
        if isinstance(node, A.Imag):
            return [np.array([[node.value]], dtype=np.complex128)]
        if isinstance(node, A.String):
            return [CharArray.from_str(node.value)]
        if isinstance(node, A.Ident):
            return self._ident(node, env, nargout)
        if isinstance(node, A.End):
            return [self._end_value(node)]
        if isinstance(node, A.Unary):
            return [self._guard(node, symops.unary_op, node.op, self.one(node.operand, env))]
        if isinstance(node, A.Postfix):
            operand = self.one(node.operand, env)
            return [self._guard(node, symops.transpose, operand, node.op == "'")]
        if isinstance(node, A.Binary):
            return [self._binary(node, env)]
        if isinstance(node, A.Range):
            start = self.one(node.start, env)
            step = None if node.step is None else self.one(node.step, env)
            return [self._guard(node, ops.colon_range, start, step, self.one(node.stop, env))]
        if isinstance(node, A.Index):
            return self._index(node, env, nargout)
        if isinstance(node, A.CellIndex):
            base = self.one(node.target, env)
            return list(self._guard(node, ix.cell_contents, base,
                                    self._index_args(node.args, base, env)))
        if isinstance(node, A.Field):
            return [self._guard(node, ix.get_field, self.one(node.target, env), node.name)]
        if isinstance(node, A.Matrix):
            rows = [self._flat(row, env) for row in node.rows]
            return [self._guard(node, symops.build_matrix, rows)]
        if isinstance(node, A.CellLiteral):
            rows = [self._flat(row, env) for row in node.rows]
            return [self._guard(node, ops.build_cell, rows)]
        if isinstance(node, A.FuncHandle):
            return [FunctionHandle(name=node.name)]
        if isinstance(node, A.AnonFunc):
            return [self._anon(node, env)]
        raise EvalError(f"cannot evaluate {type(node).__name__}", node.loc)

    def _flat(self, nodes: Sequence[A.Node], env: Env) -> list[object]:
        """Evaluate several nodes, expanding comma-separated lists (``c{:}``)."""
        out: list[object] = []
        for n in nodes:
            out.extend(self.values(n, env, nargout=1))
        return out

    def _ident(self, node: A.Ident, env: Env, nargout: int) -> list[object]:
        if node.name in env:
            return [env[node.name]]
        if self._has_function(node.name):
            return self._call(node.name, [], nargout, node)
        raise EvalError(f"Undefined function or variable '{node.name}'.", node.loc)

    def _binary(self, node: A.Binary, env: Env) -> object:
        if node.op in ("&&", "||"):
            left = self._guard(node, ops.to_logical_scalar, self.one(node.left, env), node.op)
            if (node.op == "||") == left:
                return _scalar(left)
            right = self._guard(node, ops.to_logical_scalar, self.one(node.right, env), node.op)
            return _scalar(right)
        left_value = self.one(node.left, env)
        right_value = self.one(node.right, env)
        diags: list[Diagnostic] = []
        result = self._guard(node, symops.binary_op, node.op, left_value, right_value, diags)
        for d in diags:
            self.host.diagnostic(d)
        return result

    def _end_value(self, node: A.End) -> object:
        top = self._end[-1] if self._end else None
        if top is None:
            raise EvalError("'end' is only valid inside an index expression.", node.loc)
        base, position, nargs = top
        return _scalar(float(ix.end_value(base, position, nargs)))

    # ------------------------------------------------------------ index and call
    def _index(self, node: A.Index, env: Env, nargout: int) -> list[object]:
        target = node.target
        if isinstance(target, A.Ident) and target.name not in env:
            if self._has_function(target.name):
                args = self._call_args(node.args, env)
                return self._call(target.name, args, nargout, node)
            raise EvalError(f"Undefined function or variable '{target.name}'.", target.loc)
        base = self.one(target, env)
        if isinstance(base, FunctionHandle):
            return self._call_handle(base, self._call_args(node.args, env), nargout, node)
        args = self._index_args(node.args, base, env)
        return [self._guard(node, ix.index_value, base, args)]

    def _call_args(self, nodes: Sequence[A.Node], env: Env) -> list[object]:
        self._end.append(None)
        try:
            out: list[object] = []
            for n in nodes:
                if isinstance(n, A.Colon):
                    out.append(CharArray.from_str(":"))
                else:
                    out.extend(self.values(n, env, nargout=1))
            return out
        finally:
            self._end.pop()

    def _index_args(self, nodes: Sequence[A.Node], base: object, env: Env) -> list[object]:
        out: list[object] = []
        for pos, n in enumerate(nodes):
            if isinstance(n, A.Colon):
                out.append(COLON)
                continue
            self._end.append((base, pos, len(nodes)))
            try:
                out.extend(self.values(n, env, nargout=1))
            finally:
                self._end.pop()
        return out

    def _enter(self, node: A.Node) -> None:
        if self._depth >= self.max_depth:
            raise EvalError(f"Maximum recursion limit of {self.max_depth} reached.", node.loc)
        self._depth += 1

    def _has_function(self, name: str) -> bool:
        return name in self.user_functions or name in self.functions

    def _call_user(
        self, fn: A.FunctionDef, args: list, nargout: int, node: A.Node
    ) -> list[object]:
        varargs = bool(fn.params) and fn.params[-1] == "varargin"
        fixed = fn.params[:-1] if varargs else fn.params
        if len(args) > len(fixed) and not varargs:
            raise EvalError("Too many input arguments.", node.loc)
        local: dict[str, object] = dict(zip(fixed, args, strict=False))
        if varargs:
            extra = args[len(fixed):]
            local["varargin"] = ops.build_cell([extra]) if extra else CellArray.empty(0, 0)
        local["nargin"] = _scalar(float(len(args)))
        local["nargout"] = _scalar(float(nargout))
        self._enter(node)
        try:
            try:
                self._exec_block(fn.body, local)
            except _Return:
                pass
            except _Signal as sig:
                word = "break" if isinstance(sig, _Break) else "continue"
                raise EvalError(f"'{word}' is only valid inside a loop.", sig.loc) from None
        except EvalError as exc:
            exc.stack.append((fn.name, node.loc))
            raise
        finally:
            self._depth -= 1
        return self._outputs(fn, local, nargout, node)

    def _outputs(
        self, fn: A.FunctionDef, local: dict[str, object], nargout: int, node: A.Node
    ) -> list[object]:
        vals: list[object | None] = []
        for out in fn.outputs:
            if out == "varargout":
                extra = local.get("varargout")
                if isinstance(extra, CellArray):
                    vals.extend(extra.data.ravel(order="F"))
                break
            vals.append(local.get(out))
        result: list[object] = []
        for i in range(max(nargout, 1)):
            if i >= len(vals):
                if nargout == 0:
                    break
                raise EvalError("Too many output arguments.", node.loc)
            if vals[i] is None:
                if nargout == 0:
                    break
                raise EvalError(
                    f"Output argument '{fn.outputs[i]}' (and maybe others) not assigned "
                    f"during call to '{fn.name}'.",
                    node.loc,
                )
            result.append(vals[i])
        return result

    def _call(self, name: str, args: list, nargout: int, node: A.Node) -> list[object]:
        if name in self.user_functions:
            return self._call_user(self.user_functions[name], args, nargout, node)
        self._enter(node)
        try:
            raw = self._guard(node, self.functions[name], args, nargout)
            if not isinstance(raw, (list, tuple)):
                raw = [raw]
            outs = [self._guard(node, to_value, item) for item in raw]
        finally:
            self._depth -= 1
        return outs[: max(nargout, 1)]

    def _call_handle(
        self, handle: FunctionHandle, args: list, nargout: int, node: A.Node
    ) -> list[object]:
        if not handle.is_anonymous:
            if not self._has_function(handle.name):  # type: ignore[arg-type]
                raise EvalError(f"Undefined function '{handle.name}'.", node.loc)
            return self._call(handle.name, args, nargout, node)  # type: ignore[arg-type]
        if len(args) > len(handle.params):
            raise EvalError("Too many input arguments.", node.loc)
        local: dict[str, object] = dict(handle.captured)
        local.update(zip(handle.params, args, strict=False))
        self._enter(node)
        self._end.append(None)
        try:
            outs = self.values(handle.body, local, nargout)  # type: ignore[arg-type]
        finally:
            self._end.pop()
            self._depth -= 1
        return outs[: max(nargout, 1)]

    def _anon(self, node: A.AnonFunc, env: Env) -> FunctionHandle:
        names = {n.name for n in A.walk(node.body) if isinstance(n, A.Ident)}
        captured = {n: env[n] for n in names - set(node.params) if n in env}
        return FunctionHandle(params=node.params, body=node.body, captured=captured)

    # ------------------------------------------------------------------ helpers
    def _guard(self, node: A.Node, fn: Callable, *args: object) -> object:
        try:
            return fn(*args)
        except (EvalError, Cancelled):  # a Stop inside a builtin stays a Stop
            raise
        except EngStudioError as exc:
            raise EvalError(str(exc), node.loc) from exc


def _root_name(node: A.Node) -> str:
    while not isinstance(node, A.Ident):
        node = node.target  # type: ignore[attr-defined]
    return node.name


class _Columns:
    """Lazy sequence of the columns of a value (what ``for`` iterates over)."""

    def __init__(self, value: object, count: int) -> None:
        self._value = value
        self._count = count

    def __iter__(self) -> Iterator[object]:
        for k in range(self._count):
            yield ix.index_value(self._value, [COLON, _scalar(float(k + 1))])


def _case_matches(subject: object, case: object) -> bool:
    if isinstance(case, CellArray):
        return any(_case_matches(subject, item) for item in case.data.ravel(order="F"))
    if isinstance(subject, CharArray):
        return isinstance(case, CharArray) and case.shape[0] <= 1 and (
            case.to_str() == subject.to_str())
    if isinstance(subject, np.ndarray):
        return isinstance(case, np.ndarray) and case.size == 1 and bool(
            subject.item() == case.item())
    return False
