"""needs_more: block completeness for Command Window input (K3)."""

import pytest

from engstudio.app.input_state import needs_more


@pytest.mark.parametrize("code", [
    "x = 1", "x = 1;", "", "   ", "% just a comment", "disp('wait...')", "x = 1 % more...",
    "for i=1:3, disp(i), end", "if x, y=1; end", "a(end)", "c{end} = 1", "x = [1 2 3](end);",
    "if a\n  b = 1;\nend", "while true\n  break\nend", "try\n x=1;\ncatch\n y=2;\nend",
    "switch k\n case 1\n  a=1;\nend", "function r = f(x)\n r = x;\nend",
    "x = (1 + ...\n 2)", "end", "x = 'unterminated", "x = 1 +", "A = [1 2\n3 4];",
])
def test_complete(code):
    assert not needs_more(code)


@pytest.mark.parametrize("code", [
    "for i=1:3", "if x", "if x\n  y = 1;", "if x\n y\nelse", "while k < 3\n k = k + 1;",
    "switch k\n case 1", "try\n x = 1;", "try\n x\ncatch e", "function r = f(x)\n r = x;",
    "if a\n for i=1:2\n  b\n end", "x = [1 2", "x = {1, ...", "f(1, 2", "y = 1 + ...",
    "%{\nblock comment", "x = [1 2\n3 4",
])
def test_incomplete(code):
    assert needs_more(code)


def test_nested_blocks_close_in_order():
    code = "for i=1:2\n if i == 1\n  a = 1;\n else\n  a = 2;\n end\nend"
    assert not needs_more(code)
    assert needs_more(code[: code.rindex("end")])


def test_extra_end_is_complete_so_the_parser_reports_it():
    assert not needs_more("if x\nend\nend")


def test_block_comment_closed():
    assert not needs_more("%{\nnote\n%}\nx = 1;")
