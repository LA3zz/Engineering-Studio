"""MATLAB TeX subset (plotting.text)."""

import pytest

from engstudio.plotting.text import (
    parse_tex,
    tex_to_html,
    tex_to_mathtext,
    tex_to_plain,
    tex_to_unicode,
)


@pytest.mark.parametrize("src, runs", [
    ("abc", [("abc", 0)]),
    ("\\theta_1", [("θ", 0), ("1", -1)]),
    ("m/s^2", [("m/s", 0), ("2", 1)]),
    ("x^{10}y", [("x", 0), ("10", 1), ("y", 0)]),
    ("d^2\\theta/dt^2", [("d", 0), ("2", 1), ("θ/dt", 0), ("2", 1)]),
    ("\\omega = 5", [("ω = 5", 0)]),
    ("a\\_b", [("a_b", 0)]),
    ("\\unknown x", [("\\unknown x", 0)]),
    ("\\theta_{\\alpha}", [("θ", 0), ("α", -1)]),
    ("90\\circ", [("90°", 0)]),
    ("x^", [("x^", 0)]),
])
def test_parse(src, runs):
    assert parse_tex(src) == runs


def test_html_escapes_and_tags():
    assert tex_to_html("a<b_1") == "a&lt;b<sub>1</sub>"
    assert tex_to_html("x^2", "none") == "x^2"


def test_mathtext():
    assert tex_to_mathtext("\\theta_1") == "θ$_{1}$"
    assert tex_to_mathtext("cost $5") == "cost \\$5"
    assert tex_to_mathtext("a_b", "none") == "a_b"


def test_unicode_and_plain():
    assert tex_to_unicode("\\theta_1") == "θ₁"
    assert tex_to_unicode("m/s^2") == "m/s²"
    assert tex_to_unicode("x_{max}") == "xₘₐₓ"
    assert tex_to_unicode("x_{bd}") == "x_{bd}"  # no Unicode subscript b/d: keep the markup
    assert tex_to_plain("\\theta_1") == "θ1"
