"""Theme data tests (no Qt needed)."""

from __future__ import annotations

import re

import pytest

from engstudio.gui.theme import DARK, LIGHT, build_stylesheet, contrast_ratio, get_palette


def test_contrast_ratio_known_values():
    # WCAG reference values: black/white = 21:1, identical colours = 1:1
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)
    assert contrast_ratio("#808080", "#808080") == pytest.approx(1.0)


@pytest.mark.parametrize("pal", [LIGHT, DARK])
def test_palette_readability(pal):
    for fg, bg in [(pal.text, pal.base), (pal.text, pal.window), (pal.text, pal.toolbar),
                   (pal.text_dim, pal.base), (pal.text_dim, pal.window),
                   (pal.text_dim, pal.toolbar), (pal.accent_text, pal.accent),
                   (pal.text, pal.selection), (pal.text_dim, pal.button),
                   (pal.text, pal.hover)]:
        assert contrast_ratio(fg, bg) >= 4.5, (pal.name, fg, bg)


@pytest.mark.parametrize("pal", [LIGHT, DARK])
def test_stylesheet_fully_substituted(pal):
    qss = build_stylesheet(pal)
    assert "${" not in qss and "$" not in qss
    assert pal.window in qss and pal.accent in qss
    assert qss.count("{") == qss.count("}")
    colors = set(re.findall(r"#[0-9a-fA-F]{6}\b", qss))
    assert colors <= {getattr(pal, f) for f in pal.__dataclass_fields__ if f != "name"}


def test_get_palette():
    assert get_palette("light") is LIGHT and get_palette("dark") is DARK
    with pytest.raises(ValueError):
        get_palette("solarized")


def test_palettes_are_valid_hex():
    for pal in (LIGHT, DARK):
        for f in pal.__dataclass_fields__:
            if f != "name":
                assert re.fullmatch(r"#[0-9a-f]{6}", getattr(pal, f)), (pal.name, f)
