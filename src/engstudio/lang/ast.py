"""AST node dataclasses for the Engineering Studio v1 MATLAB-like subset (T3.2).

Pure data: no parsing, no evaluation. All nodes are frozen, slotted dataclasses; sequences
are tuples, so trees are immutable and hashable. ``loc`` (keyword-only, optional) is the
1-based source position and is excluded from equality, so trees compare structurally.

Operator spellings equal the lexer token text. Precedence is the parser's job; the tree
is already resolved. ``Index`` is used for both ``a(i)`` indexing and ``f(x)`` calls: the
interpreter decides at run time (variable wins over function, as in MATLAB).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, fields

from engstudio.core.diagnostics import SourceLoc
from engstudio.core.errors import ValidationError

UNARY_OPS = frozenset({"-", "+", "~"})
POSTFIX_OPS = frozenset({"'", ".'"})
BINARY_OPS = frozenset(
    {"+", "-", "*", "/", "\\", "^", ".*", "./", ".\\", ".^",
     "==", "~=", "<", "<=", ">", ">=", "&", "|", "&&", "||"}
)


def _check(cond: bool, message: str) -> None:
    if not cond:
        raise ValidationError(message)


@dataclass(frozen=True, slots=True)
class Node:
    """Base class. ``loc`` is keyword-only and ignored by ``==``."""

    loc: SourceLoc | None = field(default=None, kw_only=True, compare=False, repr=False)


# ---------------------------------------------------------------- expressions
@dataclass(frozen=True, slots=True)
class Number(Node):
    value: float


@dataclass(frozen=True, slots=True)
class Imag(Node):
    """Imaginary literal such as ``2i``; ``value`` is the complex number ``0+2j``."""

    value: complex


@dataclass(frozen=True, slots=True)
class String(Node):
    value: str
    double_quoted: bool = False


@dataclass(frozen=True, slots=True)
class Ident(Node):
    name: str

    def __post_init__(self) -> None:
        _check(bool(self.name), "Ident name must not be empty")


@dataclass(frozen=True, slots=True)
class Colon(Node):
    """Bare ``:`` inside an index (select all)."""


@dataclass(frozen=True, slots=True)
class End(Node):
    """``end`` inside an index (last element along that dimension)."""


@dataclass(frozen=True, slots=True)
class Unary(Node):
    op: str
    operand: Node

    def __post_init__(self) -> None:
        _check(self.op in UNARY_OPS, f"invalid unary operator {self.op!r}")


@dataclass(frozen=True, slots=True)
class Postfix(Node):
    """Transpose: ``'`` (conjugate) or ``.'`` (plain)."""

    op: str
    operand: Node

    def __post_init__(self) -> None:
        _check(self.op in POSTFIX_OPS, f"invalid postfix operator {self.op!r}")


@dataclass(frozen=True, slots=True)
class Binary(Node):
    op: str
    left: Node
    right: Node

    def __post_init__(self) -> None:
        _check(self.op in BINARY_OPS, f"invalid binary operator {self.op!r}")


@dataclass(frozen=True, slots=True)
class Range(Node):
    """``start:stop`` or ``start:step:stop`` (``step`` is None for the two-part form)."""

    start: Node
    step: Node | None
    stop: Node


@dataclass(frozen=True, slots=True)
class Index(Node):
    """``target(args)``: array index or function call."""

    target: Node
    args: tuple[Node, ...] = ()


@dataclass(frozen=True, slots=True)
class CellIndex(Node):
    """``target{args}``: cell content indexing."""

    target: Node
    args: tuple[Node, ...] = ()


@dataclass(frozen=True, slots=True)
class Field(Node):
    """``target.name`` (struct field access)."""

    target: Node
    name: str

    def __post_init__(self) -> None:
        _check(bool(self.name), "Field name must not be empty")


@dataclass(frozen=True, slots=True)
class Matrix(Node):
    """``[a, b; c, d]``: ``rows`` is a tuple of rows, each a tuple of elements."""

    rows: tuple[tuple[Node, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class CellLiteral(Node):
    """``{a, b; c, d}``."""

    rows: tuple[tuple[Node, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class FuncHandle(Node):
    """``@name``."""

    name: str

    def __post_init__(self) -> None:
        _check(bool(self.name), "FuncHandle name must not be empty")


@dataclass(frozen=True, slots=True)
class AnonFunc(Node):
    """``@(params) body``."""

    params: tuple[str, ...]
    body: Node

    def __post_init__(self) -> None:
        _check(len(set(self.params)) == len(self.params), "duplicate parameter name")


@dataclass(frozen=True, slots=True)
class Tilde(Node):
    """Ignored output placeholder in ``[~, i] = max(x)``; valid only as an Assign target."""


# ----------------------------------------------------------------- statements
@dataclass(frozen=True, slots=True)
class ExprStmt(Node):
    expr: Node
    printed: bool = True  # False when terminated by ';'


@dataclass(frozen=True, slots=True)
class Assign(Node):
    """``a = e``, ``a(i).f = e`` or ``[a, ~, b] = e``.

    Each target is an Ident, Index, CellIndex, Field chain, or Tilde.
    """

    targets: tuple[Node, ...]
    value: Node
    printed: bool = True

    def __post_init__(self) -> None:
        _check(len(self.targets) >= 1, "Assign needs at least one target")
        for t in self.targets:
            _check(_is_lvalue(t), f"invalid assignment target {type(t).__name__}")
        if len(self.targets) == 1:
            _check(not isinstance(self.targets[0], Tilde), "'~' needs a multi-output assignment")


def _is_lvalue(node: Node) -> bool:
    if isinstance(node, Tilde):
        return True
    while isinstance(node, (Index, CellIndex, Field)):
        node = node.target
    return isinstance(node, Ident)


@dataclass(frozen=True, slots=True)
class IfClause(Node):
    cond: Node
    body: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class If(Node):
    """``if``/``elseif`` clauses in order, then optional ``else`` body."""

    clauses: tuple[IfClause, ...]
    else_body: tuple[Node, ...] | None = None

    def __post_init__(self) -> None:
        _check(len(self.clauses) >= 1, "If needs at least one clause")


@dataclass(frozen=True, slots=True)
class For(Node):
    var: Ident
    iterable: Node
    body: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class While(Node):
    cond: Node
    body: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Case(Node):
    """``case expr``; a cell literal means "any of"."""

    value: Node
    body: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Switch(Node):
    subject: Node
    cases: tuple[Case, ...]
    otherwise: tuple[Node, ...] | None = None


@dataclass(frozen=True, slots=True)
class Break(Node):
    pass


@dataclass(frozen=True, slots=True)
class Continue(Node):
    pass


@dataclass(frozen=True, slots=True)
class Return(Node):
    pass


@dataclass(frozen=True, slots=True)
class TryCatch(Node):
    body: tuple[Node, ...]
    catch_var: str | None
    catch_body: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class FunctionDef(Node):
    """``function [o1, o2] = name(p1, p2) ... end``."""

    name: str
    params: tuple[str, ...]
    outputs: tuple[str, ...]
    body: tuple[Node, ...]

    def __post_init__(self) -> None:
        _check(bool(self.name), "FunctionDef name must not be empty")
        _check(len(set(self.params)) == len(self.params), "duplicate parameter name")
        _check(len(set(self.outputs)) == len(self.outputs), "duplicate output name")


@dataclass(frozen=True, slots=True)
class Program(Node):
    """A parsed script or file: top-level statements (including FunctionDef)."""

    body: tuple[Node, ...] = ()


# ------------------------------------------------------------------ utilities
def children(node: Node) -> Iterator[Node]:
    """Yield the direct child nodes of ``node`` in field order (tuples are flattened)."""

    def _flat(v: object) -> Iterator[Node]:
        if isinstance(v, Node):
            yield v
        elif isinstance(v, tuple):
            for item in v:
                yield from _flat(item)

    for f in fields(node):
        if f.name != "loc":
            yield from _flat(getattr(node, f.name))


def walk(node: Node) -> Iterator[Node]:
    """Pre-order traversal including ``node`` itself."""
    yield node
    for c in children(node):
        yield from walk(c)
