"""Lexer tests (T3.1). Expected token streams follow documented MATLAB lexical rules
(numeric literal forms, transpose vs. string, whitespace-separated matrix elements)."""

from __future__ import annotations

import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang.lexer import LexError, tokenize

_NAMES = {"NUMBER": "N", "IMAG": "Z", "IDENT": "id", "STRING": "S", "DQSTRING": "D",
          "TRANSPOSE": "T", "NEWLINE": "NL"}


def sig(src: str) -> str:
    """Compact rendering: N number, Z imaginary, id, S/D strings, T transpose, * = synthetic."""
    out = []
    for t in tokenize(src):
        if t.kind == "EOF":
            continue
        if t.kind == "KEYWORD":
            out.append("kw:" + t.text)
        elif t.kind in _NAMES:
            out.append(_NAMES[t.kind])
        else:
            out.append(t.kind + ("*" if t.synthetic else ""))
    return " ".join(out)


def vals(src: str):
    return [t.value for t in tokenize(src) if t.kind in ("NUMBER", "IMAG", "STRING", "DQSTRING")]


def test_ends_with_eof_and_empty_source():
    assert [t.kind for t in tokenize("")] == ["EOF"]
    assert tokenize("x")[-1].kind == "EOF"


def test_number_forms():
    assert vals("3 1.5 .5 1. 1e-3 2E+4 1.5e2 0") == [3.0, 1.5, 0.5, 1.0, 1e-3, 2e4, 150.0, 0.0]


def test_imaginary_literals():
    assert vals("3i 2.5j 1e2i .5i") == [3j, 2.5j, 100j, 0.5j]


def test_number_followed_by_dot_operator():
    assert sig("1.*2") == "N .* N"
    assert sig("1./2") == "N ./ N"
    assert sig("2.^3") == "N .^ N"
    assert sig("1.'") == "N T"
    assert vals("1.*2") == [1.0, 2.0]


@pytest.mark.parametrize("src", ["3x", "2e", "1.5abc", "4ii"])
def test_invalid_numbers(src):
    with pytest.raises(LexError):
        tokenize(src)


def test_identifiers_and_keywords():
    assert sig("if x1 _y end") == "kw:if id id kw:end"
    assert sig("endx ifs") == "id id"
    assert sig("function y = f(x)") == "kw:function id = id ( id )"


def test_all_keywords_recognised():
    for kw in ["if", "elseif", "else", "end", "for", "while", "break", "continue", "return",
               "function", "switch", "case", "otherwise", "try", "catch"]:
        assert sig(kw) == f"kw:{kw}"


def test_operators():
    assert sig("a == b ~= c <= d >= e < f > g") == "id == id ~= id <= id >= id < id > id"
    assert sig("a && b || c & d | e") == "id && id || id & id | id"
    assert sig(r"a.*b./c.\d.^e") == r"id .* id ./ id .\ id .^ id"
    assert sig(r"a+b-c*d/e\f^g") == r"id + id - id * id / id \ id ^ id"
    assert sig("~a") == "~ id"
    assert sig("@sin") == "@ id"
    assert sig("1:2:3") == "N : N : N"
    assert sig("s.a") == "id . id"


def test_transpose_vs_string():
    assert sig("a'") == "id T"
    assert sig("a''") == "id T T"
    assert sig("a.'") == "id T"
    assert sig("(a)'") == "( id ) T"
    assert sig("x(end)'") == "id ( kw:end ) T"
    assert sig("a '") == "id T"  # outside brackets whitespace is allowed before transpose
    assert sig("x = 'hi'") == "id = S"
    assert sig("disp('hi')") == "id ( S )"
    assert sig("x = 3; 'hi'") == "id = N ; S"
    assert sig("1'") == "N T"
    assert sig("[1 2]'") == "[ N ,* N ] T"


def test_string_escapes():
    assert vals("'it''s'") == ["it's"]
    assert vals("''''") == ["'"]
    assert vals('"say ""hi"""') == ['say "hi"']
    assert vals("'a%b'") == ["a%b"]
    assert vals("''") == [""]


def test_unterminated_string_location():
    with pytest.raises(LexError) as ei:
        tokenize("x = 1\ny = 'abc", file="t.m")
    loc = ei.value.location
    assert (loc.file, loc.line, loc.col) == ("t.m", 2, 5)
    d = ei.value.to_diagnostic()
    assert d.code == "E_LEX" and d.location == loc


def test_matrix_whitespace_separation():
    assert sig("[1 2 3]") == "[ N ,* N ,* N ]"
    assert sig("[1 -2]") == "[ N ,* - N ]"
    assert sig("[1 - 2]") == "[ N - N ]"
    assert sig("[1 -  2]") == "[ N - N ]"
    assert sig("[a - b]") == "[ id - id ]"
    assert sig("[a -b]") == "[ id ,* - id ]"
    assert sig("[1 +2]") == "[ N ,* + N ]"
    assert sig("[1, 2; 3, 4]") == "[ N , N ; N , N ]"
    assert sig("[1 , 2]") == "[ N , N ]"
    assert sig("[]") == "[ ]"
    assert sig("[ 1 2 ]") == "[ N ,* N ]"


def test_matrix_transpose_and_strings():
    assert sig("[a' b']") == "[ id T ,* id T ]"
    assert sig("[a 'x']") == "[ id ,* S ]"
    assert sig("[a' 'x']") == "[ id T ,* S ]"
    assert sig('[1 "a"]') == "[ N ,* D ]"
    assert sig("['a' 'b']") == "[ S ,* S ]"


def test_matrix_parentheses_suppress_separation():
    assert sig("[f(1, 2) 3]") == "[ id ( N , N ) ,* N ]"
    assert sig("[f(1 -2)]") == "[ id ( N - N ) ]"
    assert sig("[x(1) (2)]") == "[ id ( N ) ,* ( N ) ]"
    assert sig("[a (1)]") == "[ id ,* ( N ) ]"
    assert sig("[x(end) 1]") == "[ id ( kw:end ) ,* N ]"


def test_matrix_row_newlines():
    assert sig("[1 2\n3 4]") == "[ N ,* N ;* N ,* N ]"
    assert sig("[1 2;\n3 4]") == "[ N ,* N ; N ,* N ]"
    assert sig("[\n1 2\n]") == "[ N ,* N ;* ]"
    assert sig("[1 ...\n 2]") == "[ N ,* N ]"
    assert sig("x = [1 2\n3 4]\ny") == "id = [ N ,* N ;* N ,* N ] NL id"


def test_cell_literals():
    assert sig("{1 'a'}") == "{ N ,* S }"
    assert sig("c{2}") == "id { N }"
    assert sig("c{end}'") == "id { kw:end } T"


def test_matrix_unary_not_and_handles():
    assert sig("[a ~b]") == "[ id ,* ~ id ]"
    assert sig("[a ~= b]") == "[ id ~= id ]"
    assert sig("{@sin @cos}") == "{ @ id ,* @ id }"
    assert sig("[1 .5]") == "[ N ,* N ]"


def test_comments():
    assert sig("x = 1 % comment") == "id = N"
    assert sig("% only comment") == ""
    assert sig("x = 1 % a 'b\ny = 2") == "id = N NL id = N"
    assert sig("%{\nblock 'unterminated\n%}\nx") == "NL id"
    assert sig("%{\n%{\nnested\n%}\nstill\n%}\nx") == "NL id"
    assert sig("  %{  \nfoo\n  %}  \nx") == "NL id"
    # '%{' not alone on its line is an ordinary line comment
    assert sig("x %{ y\nz") == "id NL id"


def test_unterminated_block_comment():
    with pytest.raises(LexError) as ei:
        tokenize("a\n%{\nnever closed")
    assert ei.value.location.line == 2


def test_continuation():
    toks = tokenize("x = 1 + ...\n    2")
    assert [t.kind for t in toks] == ["IDENT", "=", "NUMBER", "+", "NUMBER", "EOF"]
    assert (toks[4].loc.line, toks[4].loc.col) == (2, 5)
    assert sig("x = 1 + ... comment text\n2") == "id = N + N"


def test_newlines_and_crlf():
    assert sig("a\nb") == "id NL id"
    assert sig("a\r\nb\rc") == "id NL id NL id"
    assert sig("a;\n\nb") == "id ; NL NL id"
    assert sig("a, b") == "id , id"


def test_locations_and_file():
    toks = tokenize("x = 1\n  yy = 22", file="a.m")
    by_text = {t.text: t for t in toks if t.text}
    assert (by_text["x"].loc.line, by_text["x"].loc.col, by_text["x"].loc.file) == (1, 1, "a.m")
    assert (by_text["yy"].loc.line, by_text["yy"].loc.col) == (2, 3)
    assert (by_text["22"].loc.line, by_text["22"].loc.col) == (2, 8)
    assert str(by_text["yy"].loc) == "a.m:2:3"
    assert all(t.loc.line is not None and t.loc.col is not None for t in toks)


def test_space_before_flag():
    toks = tokenize("a +b")
    assert [t.space_before for t in toks[:3]] == [False, True, False]


@pytest.mark.parametrize("src", ["(1", "[1 2", "{1", "1)", "1]", "(1]", "[1)", "}"])
def test_bracket_errors(src):
    with pytest.raises(LexError):
        tokenize(src)


def test_unclosed_bracket_points_at_opener():
    with pytest.raises(LexError) as ei:
        tokenize("x = [1 2\n3 4")
    assert (ei.value.location.line, ei.value.location.col) == (1, 5)


def test_newline_in_parentheses_is_error():
    with pytest.raises(LexError):
        tokenize("f(1,\n2)")
    assert sig("f(1, ...\n2)") == "id ( N , N )"


@pytest.mark.parametrize("src", ["$", "x = 3 ? 4", "é", "a ` b"])
def test_unexpected_characters(src):
    with pytest.raises(LexError):
        tokenize(src)


def test_lexerror_is_engstudio_error():
    assert issubclass(LexError, EngStudioError)


def test_realistic_script():
    src = (
        "% demo\n"
        "A = [1 2; 3 4];\n"
        "b = A' * [1; -1];\n"
        "for k = 1:3\n"
        "  x(k) = k^2 + 2i;\n"
        "end\n"
        "disp('done')\n"
    )
    toks = tokenize(src)
    assert toks[-1].kind == "EOF"
    assert not any(t.synthetic and t.kind == ";" for t in toks)  # no stray row breaks
    assert sig("A = [1 2; 3 4];") == "id = [ N ,* N ; N ,* N ] ;"
    assert sig("b = A' * [1; -1];") == "id = id T * [ N ; - N ] ;"
