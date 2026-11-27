"""Tokenizer and colours for syntax highlighting (pure logic, no Qt)."""

from __future__ import annotations

from engstudio.gui.highlight_rules import KINDS, SYNTAX_COLORS, tokenize_line
from engstudio.gui.theme import THEMES, contrast_ratio

KW = frozenset({"if", "else", "end", "for", "while", "function"})


def pieces(line: str, in_block: bool = False) -> list[tuple[str, str]]:
    tokens, _ = tokenize_line(line, in_block, KW)
    return [(t.kind, line[t.start:t.start + t.length]) for t in tokens]


def test_number_and_semicolon():
    assert pieces("x = 5;") == [("number", "5")]


def test_for_loop():
    assert pieces("for i = 1:10") == [("keyword", "for"), ("number", "1"), ("number", "10")]


def test_comments():
    assert pieces("% only a comment") == [("comment", "% only a comment")]
    assert pieces("x = 1 % trailing") == [("number", "1"), ("comment", "% trailing")]


def test_strings():
    assert pieces("disp('hello')") == [("string", "'hello'")]
    assert pieces("s = 'it''s';") == [("string", "'it''s'")]
    assert pieces('s = "a ""b"" c";') == [("string", '"a ""b"" c"')]
    assert pieces("z = ['a' 'b'];") == [("string", "'a'"), ("string", "'b'")]
    assert pieces("e = '';") == [("string", "''")]


def test_percent_inside_string_is_not_a_comment():
    assert pieces("disp('50% done')") == [("string", "'50% done'")]


def test_unterminated_string_runs_to_end_of_line():
    assert pieces("x = 'abc") == [("string", "'abc")]


def test_transpose_is_not_a_string():
    assert pieces("y = A';") == []
    assert pieces("y = A'*B';") == []
    assert pieces("y = [1 2 3]';") == [("number", "1"), ("number", "2"), ("number", "3")]
    assert pieces("y = x.';") == []
    assert pieces("y = (a+b)'';") == []


def test_number_formats():
    for text in ("1e-3", "2.5", ".5", "3i", "1.5e+10j", "42"):
        assert pieces(f"x = {text};") == [("number", text)], text


def test_digits_inside_identifiers_are_not_numbers():
    assert pieces("x1 = y2") == []
    assert pieces("a2b = 1") == [("number", "1")]


def test_elementwise_power_does_not_swallow_the_dot():
    assert pieces("2.^x") == [("number", "2")]
    assert pieces("3.*x") == [("number", "3")]


def test_keywords_only_as_whole_words():
    assert pieces("endpoint = 1") == [("number", "1")]
    assert pieces("iffy = 2") == [("number", "2")]
    assert pieces("end_val = 3") == [("number", "3")]
    assert pieces("if x") == [("keyword", "if")]
    assert pieces("s.end = 1") == [("number", "1")]  # struct field, not the keyword


def test_continuation_marker_starts_a_comment():
    assert pieces("x = 1 + ... more") == [("number", "1"), ("comment", "... more")]


def test_block_comment_state_machine():
    tokens, state = tokenize_line("%{", False, KW)
    assert tokens and state is True
    tokens, state = tokenize_line("if x 'text' 5", True, KW)
    assert [t.kind for t in tokens] == ["comment"] and tokens[0].length == 13 and state is True
    tokens, state = tokenize_line("%}", True, KW)
    assert [t.kind for t in tokens] == ["comment"] and state is False
    assert pieces("x = 1", in_block=False) == [("number", "1")]
    tokens, state = tokenize_line("  %{  ", False, KW)
    assert state is True and tokens


def test_percent_brace_with_text_is_an_ordinary_comment():
    tokens, state = tokenize_line("%{ not alone", False, KW)
    assert [t.kind for t in tokens] == ["comment"] and state is False
    tokens, state = tokenize_line("%} not a closer", True, KW)
    assert state is True  # still inside the block


def test_empty_line_keeps_state():
    assert tokenize_line("", False, KW) == ([], False)
    assert tokenize_line("", True, KW) == ([], True)


def test_tokens_are_sorted_in_range_and_never_overlap():
    lines = [
        "for k = 1:n  % loop", "x = A'*B' + 'str' + \"dq\" + 3.5e-2i;", "if a'==b, end",
        "s = 'a''b'; t = 5; ... more", "function y = f(x) % comment", "z = [1 2 3]'; w = z.';",
        "", "   ", "%{", "'", '"', "...", "1.", ".", "a.b.c = 'x';",
    ]
    for line in lines:
        tokens, _ = tokenize_line(line, False, KW)
        end = 0
        for t in tokens:
            assert t.kind in KINDS and t.length > 0, (line, t)
            assert t.start >= end and t.start + t.length <= len(line), (line, t)
            end = t.start + t.length


def test_colours_defined_for_every_theme_and_kind():
    assert set(SYNTAX_COLORS) == set(THEMES)
    for colors in SYNTAX_COLORS.values():
        assert set(colors) == set(KINDS)


def test_colours_have_readable_contrast_against_editor_background():
    for theme, colors in SYNTAX_COLORS.items():
        for kind, colour in colors.items():
            ratio = contrast_ratio(colour, THEMES[theme].base)
            assert ratio >= 4.5, f"{theme}/{kind} {colour}: contrast {ratio:.2f}"
