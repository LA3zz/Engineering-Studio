"""Fast calls of anonymous functions (``@(t, y) [y(2); -wn^2*y(1)]``).

Solvers such as ``ode45``, ``fzero`` and ``integral`` call the same anonymous function
thousands of times. ``compile_anon`` turns the body once into nested Python closures that call
the *same* operation functions as the interpreter (``symops.binary_op``,
``indexing.index_value``, ``symops.build_matrix``, the builtins themselves), so results are
identical; only the tree-walking overhead goes (measured: about 12 % faster for an ode45
oscillator; the remaining time is in the operations and SciPy itself).

Only simple bodies are compiled: numbers, parameters, captured variables, unary/binary
operators, transposes, ranges ``a:b``, indexing of a variable without ``end``, calls of
built-in functions and ``[...]`` matrices. Anything else (cell indexing, ``end``, strings,
``&&``/``||``, nested anonymous functions, user functions, handles stored in variables, ...)
returns ``None`` and the interpreter evaluates as before. At run time a compiled call that
meets anything unexpected raises, and the caller then re-runs the call through the
interpreter, which reports errors exactly as it always did.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from engstudio.lang import ast as A
from engstudio.lang import indexing as ix
from engstudio.lang import ops, symops
from engstudio.lang.values import FunctionHandle

__all__ = ["Fallback", "compile_anon"]

Env = dict[str, object]
Compiled = Callable[[Env], object]


class Fallback(Exception):
    """The compiled path cannot handle this call; use the interpreter instead."""


class _NotCompilable(Exception):
    pass


def compile_anon(interp, params: tuple[str, ...], captured: frozenset[str],
                 body: A.Node) -> Compiled | None:
    """A function ``env -> value`` for the body, or ``None`` if it is not simple enough."""
    known = set(params) | set(captured)
    try:
        return _compile(interp, body, known)
    except _NotCompilable:
        return None


def _compile(interp, node: A.Node, known: set[str]) -> Compiled:
    if isinstance(node, A.Number):
        value = float(node.value)
        return lambda env: np.array([[value]], dtype=np.float64)
    if isinstance(node, A.Imag):
        cvalue = complex(node.value)
        return lambda env: np.array([[cvalue]], dtype=np.complex128)
    if isinstance(node, A.Ident):
        return _ident(interp, node, known)
    if isinstance(node, A.Unary):
        operand = _compile(interp, node.operand, known)
        op = node.op
        return lambda env: symops.unary_op(op, operand(env))
    if isinstance(node, A.Postfix):
        operand = _compile(interp, node.operand, known)
        conj = node.op == "'"
        return lambda env: symops.transpose(operand(env), conj)
    if isinstance(node, A.Binary):
        if node.op in ("&&", "||"):
            raise _NotCompilable
        left, right = _compile(interp, node.left, known), _compile(interp, node.right, known)
        return _binary(interp, node.op, left, right)
    if isinstance(node, A.Range):
        start, stop = _compile(interp, node.start, known), _compile(interp, node.stop, known)
        if node.step is None:
            return lambda env: ops.colon_range(start(env), None, stop(env))
        step = _compile(interp, node.step, known)
        return lambda env: ops.colon_range(start(env), step(env), stop(env))
    if isinstance(node, A.Index):
        return _index(interp, node, known)
    if isinstance(node, A.Matrix):
        rows = [[_compile(interp, e, known) for e in row] for row in node.rows]
        return lambda env: symops.build_matrix([[e(env) for e in row] for row in rows])
    raise _NotCompilable


def _binary(interp, op: str, left: Compiled, right: Compiled) -> Compiled:
    def run(env: Env) -> object:
        diags: list = []
        out = symops.binary_op(op, left(env), right(env), diags)
        for d in diags:
            interp.host.diagnostic(d)
        return out

    return run


def _ident(interp, node: A.Ident, known: set[str]) -> Compiled:
    name = node.name
    if name in known:
        def var(env: Env) -> object:
            value = env[name]
            if isinstance(value, FunctionHandle):
                raise Fallback  # calling or returning handles stays in the interpreter
            return value

        return var
    return _call(interp, name, [], node)


def _call(interp, name: str, args: list[Compiled], node: A.Node) -> Compiled:
    def run(env: Env) -> object:
        if name in interp.user_functions or name not in interp.functions:
            raise Fallback  # user functions (or a missing name) keep the interpreter's rules
        out = interp._call(name, [a(env) for a in args], 1, node)
        if len(out) != 1:
            raise Fallback
        return out[0]

    return run


def _index(interp, node: A.Index, known: set[str]) -> Compiled:
    target = node.target
    if not isinstance(target, A.Ident):
        raise _NotCompilable
    for arg in node.args:
        if any(isinstance(n, (A.End, A.CellIndex, A.String)) for n in A.walk(arg)):
            raise _NotCompilable
    if target.name not in known:  # a function call such as sin(x) or deg2rad(a)
        if any(isinstance(a, A.Colon) for a in node.args):
            raise _NotCompilable
        return _call(interp, target.name, [_compile(interp, a, known) for a in node.args], node)
    name = target.name
    args = [(lambda env: ix.COLON) if isinstance(a, A.Colon) else _compile(interp, a, known)
            for a in node.args]

    def run(env: Env) -> object:
        base = env[name]
        if isinstance(base, FunctionHandle):
            raise Fallback  # a handle called through a variable
        return ix.index_value(base, [a(env) for a in args])

    return run
