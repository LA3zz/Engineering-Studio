"""Tests for engstudio.lang.parser (T3.3): expected trees are built by hand from lang.ast."""

import pytest

from engstudio.lang import ast as A
from engstudio.lang.lexer import LexError
from engstudio.lang.parser import ParseError, parse


def n(x):
    return A.Number(float(x))


def v(name):
    return A.Ident(name)


def bi(op, a, b):
    return A.Binary(op, a, b)


def expr(src):
    prog = parse(src)
    assert len(prog.body) == 1, prog
    stmt = prog.body[0]
    assert isinstance(stmt, A.ExprStmt), stmt
    return stmt.expr


def assign(src):
    stmt = parse(src).body[0]
    assert isinstance(stmt, A.Assign), stmt
    return stmt


def fails(src, fragment=""):
    with pytest.raises(ParseError) as info:
        parse(src)
    assert fragment in str(info.value)
    return info.value


# ------------------------------------------------------------------ literals
def test_empty_and_comment_only_programs():
    assert parse("") == A.Program(())
    assert parse("% nothing\n\n%{\nblock\n%}\n") == A.Program(())


def test_literals():
    assert expr("1.5") == n(1.5)
    assert expr("2i") == A.Imag(2j)
    assert expr("'it''s'") == A.String("it's", False)
    assert expr('"a b"') == A.String("a b", True)
    assert expr("x") == v("x")


# ---------------------------------------------------------------- precedence
def test_arithmetic_precedence_and_associativity():
    assert expr("1+2*3") == bi("+", n(1), bi("*", n(2), n(3)))
    assert expr("a-b-c") == bi("-", bi("-", v("a"), v("b")), v("c"))
    assert expr("a/b*c") == bi("*", bi("/", v("a"), v("b")), v("c"))
    assert expr("a\\b") == bi("\\", v("a"), v("b"))
    assert expr("(1+2)*3") == bi("*", bi("+", n(1), n(2)), n(3))


def test_unary_and_power():
    assert expr("-2^2") == A.Unary("-", bi("^", n(2), n(2)))
    assert expr("2^3^2") == bi("^", bi("^", n(2), n(3)), n(2))
    assert expr("2^-1") == bi("^", n(2), A.Unary("-", n(1)))
    assert expr("a*-b") == bi("*", v("a"), A.Unary("-", v("b")))
    assert expr("~a==b") == bi("==", A.Unary("~", v("a")), v("b"))
    assert expr("--x") == A.Unary("-", A.Unary("-", v("x")))


def test_transpose_binds_tighter_than_power():
    assert expr("a.^b'") == bi(".^", v("a"), A.Postfix("'", v("b")))
    assert expr("a'*b") == bi("*", A.Postfix("'", v("a")), v("b"))
    assert expr("a.'") == A.Postfix(".'", v("a"))
    assert expr("x''") == A.Postfix("'", A.Postfix("'", v("x")))
    assert expr("-a'") == A.Unary("-", A.Postfix("'", v("a")))


def test_range_precedence():
    assert expr("1:10") == A.Range(n(1), None, n(10))
    assert expr("1:2:10") == A.Range(n(1), n(2), n(10))
    assert expr("1+1:3") == A.Range(bi("+", n(1), n(1)), None, n(3))
    assert expr("a<1:3") == bi("<", v("a"), A.Range(n(1), None, n(3)))


def test_logical_precedence():
    assert expr("a || b && c") == bi("||", v("a"), bi("&&", v("b"), v("c")))
    assert expr("a | b & c") == bi("|", v("a"), bi("&", v("b"), v("c")))
    assert expr("a && b | c") == bi("&&", v("a"), bi("|", v("b"), v("c")))
    assert expr("a < b == c") == bi("==", bi("<", v("a"), v("b")), v("c"))
    assert expr("a ~= b") == bi("~=", v("a"), v("b"))


# ------------------------------------------------------------------- indexing
def test_index_and_call():
    assert expr("f(1,2)") == A.Index(v("f"), (n(1), n(2)))
    assert expr("f()") == A.Index(v("f"), ())
    assert expr("f(x)(2)") == A.Index(A.Index(v("f"), (v("x"),)), (n(2),))


def test_colon_and_end_in_index():
    assert expr("x(:,1)") == A.Index(v("x"), (A.Colon(), n(1)))
    assert expr("x(:)") == A.Index(v("x"), (A.Colon(),))
    assert expr("x(end)") == A.Index(v("x"), (A.End(),))
    assert expr("x(end-1:end)") == A.Index(
        v("x"), (A.Range(bi("-", A.End(), n(1)), None, A.End()),))
    assert expr("c{:}") == A.CellIndex(v("c"), (A.Colon(),))


def test_cell_index_and_fields():
    assert expr("c{2}") == A.CellIndex(v("c"), (n(2),))
    assert expr("s.a.b(3)") == A.Index(A.Field(A.Field(v("s"), "a"), "b"), (n(3),))
    assert expr("s(2).name") == A.Field(A.Index(v("s"), (n(2),)), "name")


# ----------------------------------------------------------- matrices / cells
def test_matrix_literals():
    assert expr("[1 2 3]") == A.Matrix(((n(1), n(2), n(3)),))
    assert expr("[1,2;3,4]") == A.Matrix(((n(1), n(2)), (n(3), n(4))))
    assert expr("[]") == A.Matrix(())
    assert expr("[1 2\n3 4]") == A.Matrix(((n(1), n(2)), (n(3), n(4))))
    assert expr("[1 2;]") == A.Matrix(((n(1), n(2)),))


def test_matrix_whitespace_rules():
    assert expr("[1 -2]") == A.Matrix(((n(1), A.Unary("-", n(2))),))
    assert expr("[1 - 2]") == A.Matrix(((bi("-", n(1), n(2)),),))
    assert expr("[a' b']") == A.Matrix(((A.Postfix("'", v("a")), A.Postfix("'", v("b"))),))
    assert expr("[x(1) y(2)]") == A.Matrix(((A.Index(v("x"), (n(1),)), A.Index(v("y"), (n(2),))),))
    assert expr("[a(1, 2)]") == A.Matrix(((A.Index(v("a"), (n(1), n(2))),),))


def test_cell_literals():
    assert expr("{1, 'a'; 2, 'b'}") == A.CellLiteral(
        ((n(1), A.String("a")), (n(2), A.String("b"))))
    assert expr("{}") == A.CellLiteral(())


def test_function_handles():
    assert expr("@sin") == A.FuncHandle("sin")
    assert expr("@(x) x.^2") == A.AnonFunc(("x",), bi(".^", v("x"), n(2)))
    assert expr("@(x,y) x+y") == A.AnonFunc(("x", "y"), bi("+", v("x"), v("y")))
    assert expr("@() 1") == A.AnonFunc((), n(1))
    assert expr("@(x) x(end)") == A.AnonFunc(("x",), A.Index(v("x"), (A.End(),)))


def test_anonymous_functions_inside_cell_literal():
    node = expr("{@(x) x+1, @(x) x*2}")
    assert node == A.CellLiteral(((
        A.AnonFunc(("x",), bi("+", v("x"), n(1))),
        A.AnonFunc(("x",), bi("*", v("x"), n(2))),
    ),))


# ------------------------------------------------------------- simple statements
def test_assignment_printed_flag():
    assert assign("x = 5") == A.Assign((v("x"),), n(5), True)
    assert assign("x = 5;") == A.Assign((v("x"),), n(5), False)
    assert assign("x = 5,") == A.Assign((v("x"),), n(5), True)


def test_assignment_targets():
    assert assign("x(2) = 1").targets == (A.Index(v("x"), (n(2),)),)
    assert assign("x(end+1) = 1").targets == (A.Index(v("x"), (bi("+", A.End(), n(1)),)),)
    assert assign("s.a = 2").targets == (A.Field(v("s"), "a"),)
    assert assign("c{1} = 3").targets == (A.CellIndex(v("c"), (n(1),)),)
    assert assign("s.a(2).b = 1").targets == (A.Field(A.Index(A.Field(v("s"), "a"), (n(2),)), "b"),)


def test_assignment_rhs_with_comparison():
    assert assign("t = a == b").value == bi("==", v("a"), v("b"))


def test_multi_assignment():
    s = assign("[q, r] = deal(1, 2)")
    assert s.targets == (v("q"), v("r"))
    assert s.value == A.Index(v("deal"), (n(1), n(2)))
    s = assign("[~, i] = max(x);")
    assert s.targets == (A.Tilde(), v("i")) and s.printed is False
    assert assign("[a b] = f()").targets == (v("a"), v("b"))
    assert assign("[s.x, v(2)] = f()").targets == (A.Field(v("s"), "x"), A.Index(v("v"), (n(2),)))


def test_matrix_statement_is_not_assignment():
    stmt = parse("[1 2 3]").body[0]
    assert isinstance(stmt, A.ExprStmt) and isinstance(stmt.expr, A.Matrix)
    stmt = parse("[a b] == [1 2]").body[0]
    assert isinstance(stmt, A.ExprStmt) and stmt.expr.op == "=="


def test_statement_separators():
    prog = parse("a, b\nc;d")
    assert [(s.expr, s.printed) for s in prog.body] == [
        (v("a"), True), (v("b"), True), (v("c"), False), (v("d"), True)]
    prog = parse("a = 1, b = 2;")
    assert [s.printed for s in prog.body] == [True, False]


def test_comments_and_continuation():
    prog = parse("x = 1 + ... comment\n 2; % trailing\n% whole line\ny = 3")
    assert len(prog.body) == 2
    assert prog.body[0].value == bi("+", n(1), n(2))


# --------------------------------------------------------------- control flow
def test_if_elseif_else():
    prog = parse("if a\n x=1;\nelseif b\n x=2;\nelse\n x=3;\nend")
    node = prog.body[0]
    assert isinstance(node, A.If) and len(node.clauses) == 2
    assert node.clauses[0].cond == v("a") and node.clauses[1].cond == v("b")
    assert node.else_body == (A.Assign((v("x"),), n(3), False),)


def test_if_without_else_and_one_liner():
    node = parse("if x, y = 1, end").body[0]
    assert node.else_body is None
    assert node.clauses[0].body == (A.Assign((v("y"),), n(1), True),)


def test_for_and_while():
    node = parse("for k = 1:3\n s = s + k;\nend").body[0]
    assert node.var == v("k") and node.iterable == A.Range(n(1), None, n(3))
    assert len(node.body) == 1
    node = parse("for i=1:3 disp(i); end").body[0]
    assert node.body == (A.ExprStmt(A.Index(v("disp"), (v("i"),)), False),)
    node = parse("while x < 5\n x = x + 1;\nend").body[0]
    assert isinstance(node, A.While) and node.cond == bi("<", v("x"), n(5))


def test_switch():
    src = "switch m\n case 'a'\n x=1;\n case {1,2}\n x=2;\n otherwise\n x=3;\nend"
    node = parse(src).body[0]
    assert node.subject == v("m") and len(node.cases) == 2
    assert node.cases[0].value == A.String("a")
    assert isinstance(node.cases[1].value, A.CellLiteral)
    assert node.otherwise == (A.Assign((v("x"),), n(3), False),)
    assert parse("switch x\ncase 1\nend").body[0].otherwise is None


def test_try_catch():
    node = parse("try\n error('x');\ncatch err\n disp(err);\nend").body[0]
    assert node.catch_var == "err" and len(node.body) == 1 and len(node.catch_body) == 1
    node = parse("try\n a;\ncatch\n b;\nend").body[0]
    assert node.catch_var is None
    node = parse("try\n a;\ncatch disp(1)\nend").body[0]
    assert node.catch_var is None and len(node.catch_body) == 1
    assert parse("try, a; end").body[0].catch_body == ()


def test_break_continue_return():
    node = parse("while 1\n break;\n continue\n return\nend").body[0]
    assert node.body == (A.Break(), A.Continue(), A.Return())


def test_nested_blocks():
    node = parse("for i=1:2\n for j=1:2\n if i==j, break, end\n end\nend").body[0]
    inner = node.body[0]
    assert isinstance(inner, A.For) and isinstance(inner.body[0], A.If)


# ------------------------------------------------------------------ functions
def test_function_forms():
    f = parse("function [a, b] = f(x, y)\n a = x; b = y;\nend").body[0]
    assert (f.name, f.params, f.outputs) == ("f", ("x", "y"), ("a", "b"))
    f = parse("function y = sq(x)\n y = x^2;\nend").body[0]
    assert (f.name, f.params, f.outputs) == ("sq", ("x",), ("y",))
    f = parse("function show(x)\n disp(x);\nend").body[0]
    assert f.outputs == () and f.params == ("x",)
    f = parse("function noargs\n disp(1);\nend").body[0]
    assert f.params == () and f.outputs == ()
    f = parse("function [a b] = g()\nend").body[0]
    assert f.outputs == ("a", "b") and f.body == ()


def test_functions_without_end_and_script_mix():
    prog = parse("function a = f()\n a = 1;\nfunction b = g()\n b = 2;")
    assert [s.name for s in prog.body] == ["f", "g"]
    assert len(prog.body[0].body) == 1
    prog = parse("x = f(2);\nfunction y = f(a)\n y = a;\nend\ndisp(x)")
    assert [type(s).__name__ for s in prog.body] == ["Assign", "FunctionDef", "ExprStmt"]


def test_function_with_nested_blocks_and_end():
    f = parse("function y = f(x)\n if x\n  y = 1;\n else\n  y = 2;\n end\nend").body[0]
    assert isinstance(f.body[0], A.If)


# --------------------------------------------------------------------- errors
def test_missing_end_reports_opener_line():
    err = fails("x = 1;\nif x\n y = 2;\n", "missing 'end' for 'if' opened at line 2")
    assert err.location is not None
    for src in ("for i=1:3\n a;", "while 1\n a;", "try\n a;", "switch x\n case 1\n a;"):
        fails(src, "missing 'end'")


def test_stray_block_words():
    for word in ("end", "else", "elseif x", "case 1", "otherwise", "catch"):
        fails(word, "unexpected")


def test_else_branch_ordering():
    fails("if a\n b;\nelse\n c;\nelseif d\n e;\nend", "unexpected 'elseif'")
    fails("switch x\ncase 1\notherwise\ncase 2\nend", "unexpected 'case'")


def test_invalid_assignment_targets():
    for src in ("1 = 2", "x' = 1", "a + b = 3", "f(1)' = 2", "[a, 1] = f()"):
        fails(src, "")
    fails("1 = 2", "invalid assignment target")
    fails("[~] = f()", "at least one output")
    fails("[~, ~] = f()", "at least one output")
    fails("[] = f()", "empty output list")


def test_command_syntax_is_rejected_with_hint():
    fails("hold on", "command syntax")
    fails("format long", "command syntax")
    assert parse("clc").body[0].expr == v("clc")


def test_malformed_expressions():
    fails("x = ", "unexpected end of input")
    fails("x = * 3", "unexpected '*'")
    fails("f(1,)", "unexpected ')'")
    fails("f(1 2)", "")  # lexer is not in a matrix here, so no synthetic comma
    fails("x = 1 2", "unexpected")
    fails("s.(n)", "dynamic field")
    fails("s.1", "")


def test_lexer_errors_pass_through():
    for src in ("x = (1 + 2", "x = [1 2 3", "x = 'abc"):
        with pytest.raises(LexError):
            parse(src)


def test_bad_headers_and_names():
    fails("for = 1:3\nend", "loop variable")
    fails("for k 1:3\nend", "'='")
    fails("function\nend", "function name")
    fails("function f(x, x)\nend", "duplicate parameter")
    fails("function [a, a] = f()\nend", "duplicate output")
    fails("function f(~)\nend", "'~'")
    fails("x = @(a, a) a", "duplicate parameter")
    fails("x = @", "function name")
    fails("switch x\n foo\nend", "expected 'case'")


def test_end_outside_index_is_an_error():
    fails("x = end", "unexpected")


# ------------------------------------------------------------------ locations
def test_node_locations():
    prog = parse("x = 1\n  y = a + b")
    first, second = prog.body
    assert (first.loc.line, first.loc.col) == (1, 1)
    assert (second.loc.line, second.loc.col) == (2, 3)
    assert (second.value.loc.line, second.value.loc.col) == (2, 9)  # operator '+'
    assert (second.value.left.loc.line, second.value.left.loc.col) == (2, 7)
    assert parse("f(1)").body[0].expr.loc.col == 1


def test_error_locations_and_file_name():
    err = fails("x = 1;\ny = * 3", "unexpected '*'")
    assert (err.location.line, err.location.col) == (2, 5)
    with pytest.raises(ParseError) as info:
        parse("end", file="a.m")
    assert info.value.location.file == "a.m"
    assert info.value.code == "E_PARSE"


# -------------------------------------------------------------- end to end
SCRIPT = """\
% simulate
function y = decay(t, k)
    y = exp(-k * t);
end

t = linspace(0, 1, 5);
A = [1 2; 3 4];
b = A \\ [1; 2];
total = 0;
for i = 1:numel(t)
    if t(i) > 0.5 && ~isempty(b)
        total = total + decay(t(i), 2);
    else
        continue
    end
end
f = @(x) x.^2 + 1;
names = {'a', 'b'};
try
    r = f(A(end, :));
catch e
    r = [];
end
"""


def test_realistic_script_parses_and_traverses():
    prog = parse(SCRIPT, "demo.m")
    kinds = [type(s).__name__ for s in prog.body]
    assert kinds == ["FunctionDef", "Assign", "Assign", "Assign", "Assign", "For",
                     "Assign", "Assign", "TryCatch"]
    names = {x.name for x in A.walk(prog) if isinstance(x, A.Ident)}
    assert {"t", "decay", "total", "b", "f"} <= names
    assert any(isinstance(x, A.End) for x in A.walk(prog))
    assert all(x.loc is not None for x in A.walk(prog))
