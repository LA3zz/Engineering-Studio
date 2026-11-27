"""Tests for engstudio.lang.ast (T3.2): construction, validation, immutability, traversal."""

from dataclasses import FrozenInstanceError

import pytest

from engstudio.core.diagnostics import SourceLoc
from engstudio.core.errors import ValidationError
from engstudio.lang import ast as A


def num(x):
    return A.Number(float(x))


def test_structural_equality_ignores_loc():
    a = A.Ident("x", loc=SourceLoc(None, 1, 1))
    b = A.Ident("x", loc=SourceLoc("f.m", 9, 9))
    assert a == b
    assert a.loc != b.loc
    assert A.Ident("x") != A.Ident("y")


def test_loc_is_keyword_only():
    with pytest.raises(TypeError):
        A.Ident("x", SourceLoc(None, 1, 1))  # type: ignore[misc]


def test_nodes_are_frozen_and_hashable():
    n = A.Binary("+", num(1), num(2))
    with pytest.raises(FrozenInstanceError):
        n.op = "-"  # type: ignore[misc]
    assert hash(n) == hash(A.Binary("+", num(1), num(2)))
    assert not hasattr(n, "__dict__")


@pytest.mark.parametrize("op", sorted(A.BINARY_OPS))
def test_binary_valid_ops(op):
    assert A.Binary(op, num(1), num(2)).op == op


@pytest.mark.parametrize("op", ["=", "!", "**", "'", ""])
def test_binary_invalid_ops(op):
    with pytest.raises(ValidationError):
        A.Binary(op, num(1), num(2))


def test_unary_and_postfix_ops():
    for op in ("-", "+", "~"):
        A.Unary(op, num(1))
    for op in ("'", ".'"):
        A.Postfix(op, num(1))
    with pytest.raises(ValidationError):
        A.Unary("*", num(1))
    with pytest.raises(ValidationError):
        A.Postfix("^", num(1))


def test_empty_names_rejected():
    for make in (lambda: A.Ident(""), lambda: A.Field(A.Ident("s"), ""),
                 lambda: A.FuncHandle(""), lambda: A.FunctionDef("", (), (), ())):
        with pytest.raises(ValidationError):
            make()


def test_duplicate_params_rejected():
    with pytest.raises(ValidationError):
        A.AnonFunc(("x", "x"), num(1))
    with pytest.raises(ValidationError):
        A.FunctionDef("f", ("a", "a"), (), ())
    with pytest.raises(ValidationError):
        A.FunctionDef("f", (), ("y", "y"), ())


def test_assign_targets():
    x = A.Ident("x")
    A.Assign((x,), num(1))
    A.Assign((A.Index(x, (num(1),)),), num(1))
    A.Assign((A.Field(A.Index(x, (num(2),)), "f"),), num(1))
    A.Assign((A.CellIndex(x, (num(1),)),), num(1))
    A.Assign((A.Tilde(), A.Ident("i")), A.Index(A.Ident("max"), (x,)))


def test_assign_invalid_targets():
    with pytest.raises(ValidationError):
        A.Assign((), num(1))
    with pytest.raises(ValidationError):
        A.Assign((num(1),), num(2))
    with pytest.raises(ValidationError):
        A.Assign((A.Binary("+", A.Ident("a"), A.Ident("b")),), num(2))
    with pytest.raises(ValidationError):
        A.Assign((A.Index(num(1), ()),), num(2))
    with pytest.raises(ValidationError):
        A.Assign((A.Tilde(),), num(1))
    with pytest.raises(ValidationError):
        A.Assign((A.Index(A.Tilde(), ()),), num(1))


def test_if_requires_clause():
    with pytest.raises(ValidationError):
        A.If(())
    node = A.If((A.IfClause(num(1), ()),))
    assert node.else_body is None


def test_defaults():
    assert A.ExprStmt(num(1)).printed is True
    assert A.Assign((A.Ident("a"),), num(1)).printed is True
    assert A.String("s").double_quoted is False
    assert A.Index(A.Ident("f")).args == ()
    assert A.Matrix().rows == ()
    assert A.Program().body == ()


def test_children_flattens_tuples_and_skips_none():
    m = A.Matrix(((num(1), num(2)), (num(3), num(4))))
    assert [c.value for c in A.children(m)] == [1.0, 2.0, 3.0, 4.0]
    r = A.Range(num(1), None, num(5))
    assert list(A.children(r)) == [num(1), num(5)]
    assert list(A.children(num(1))) == []
    assert list(A.children(A.Colon())) == []


def test_walk_preorder_on_program():
    # for k = 1:3, s = s + k^2; end
    loop = A.For(
        A.Ident("k"),
        A.Range(num(1), None, num(3)),
        (A.Assign((A.Ident("s"),),
                  A.Binary("+", A.Ident("s"), A.Binary("^", A.Ident("k"), num(2))),
                  printed=False),),
    )
    prog = A.Program((loop,))
    kinds = [type(n).__name__ for n in A.walk(prog)]
    assert kinds == ["Program", "For", "Ident", "Range", "Number", "Number", "Assign",
                     "Ident", "Binary", "Ident", "Binary", "Ident", "Number"]


def test_walk_reaches_control_flow_bodies():
    stmt = A.If(
        (A.IfClause(A.Ident("a"), (A.Break(),)), A.IfClause(A.Ident("b"), (A.Continue(),))),
        (A.Return(),),
    )
    names = {type(n).__name__ for n in A.walk(stmt)}
    assert {"If", "IfClause", "Break", "Continue", "Return"} <= names
    sw = A.Switch(A.Ident("m"), (A.Case(A.String("a"), (A.Break(),)),), (A.Return(),))
    assert {"Case", "Break", "Return"} <= {type(n).__name__ for n in A.walk(sw)}
    tc = A.TryCatch((A.Break(),), "err", (A.Continue(),))
    assert [type(n).__name__ for n in A.walk(tc)] == ["TryCatch", "Break", "Continue"]


def test_function_def_children_are_body_only():
    fd = A.FunctionDef("f", ("x",), ("y",), (A.Assign((A.Ident("y"),), A.Ident("x")),))
    assert [type(n).__name__ for n in A.walk(fd)] == ["FunctionDef", "Assign", "Ident", "Ident"]


def test_loc_preserved_and_not_a_child():
    loc = SourceLoc("a.m", 3, 5)
    n = A.Unary("-", num(1), loc=loc)
    assert n.loc == loc
    assert list(A.children(n)) == [num(1)]


def test_no_gui_or_engine_imports():
    import ast as pyast
    import inspect

    tree = pyast.parse(inspect.getsource(A))
    mods = {
        (n.module if isinstance(n, pyast.ImportFrom) else a.name)
        for n in pyast.walk(tree)
        if isinstance(n, (pyast.Import, pyast.ImportFrom))
        for a in (n.names if isinstance(n, pyast.Import) else [None])
    }
    assert all(m.split(".")[0] in {"__future__", "collections", "dataclasses", "engstudio"}
               for m in mods)
    assert not any(m.startswith(("engstudio.gui", "engstudio.engine")) for m in mods)
