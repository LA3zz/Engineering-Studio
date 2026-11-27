"""Pure rendering decisions for figures (no Qt, no PyQtGraph)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.gui.plot_params import (
    PEN_STYLES,
    SERIES_COLORS,
    SYMBOLS,
    bar_width,
    plot_colors,
    series_color,
    symbol_for,
    symbol_size,
    view_range,
)
from engstudio.gui.theme import THEMES, contrast_ratio
from engstudio.plotting.model import LINE_STYLES, MARKERS


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def test_every_theme_has_a_colour_cycle_with_readable_contrast():
    assert set(SERIES_COLORS) == set(THEMES)
    for theme, cycle in SERIES_COLORS.items():
        assert len(set(cycle)) == len(cycle) >= 5
        for colour in cycle:
            ratio = contrast_ratio(colour, plot_colors(theme)[0])
            assert ratio >= 3.0, f"{theme} {colour}: contrast {ratio:.2f}"


def test_plot_colors_follow_the_palette_and_validate_theme():
    assert plot_colors("light") == (THEMES["light"].base, THEMES["light"].text)
    assert plot_colors("dark") == (THEMES["dark"].base, THEMES["dark"].text)
    with pytest.raises(ValueError):
        plot_colors("neon")


def test_series_color_explicit_wins_and_cycle_wraps():
    assert series_color("light", 0, "#123456") == "#123456"
    cycle = SERIES_COLORS["dark"]
    assert series_color("dark", 0, None) == cycle[0]
    assert series_color("dark", len(cycle), None) == cycle[0]
    assert series_color("dark", len(cycle) + 2, None) == cycle[2]


def test_marker_and_style_tables_cover_the_model():
    assert set(SYMBOLS) == set(MARKERS)
    assert set(PEN_STYLES) == set(LINE_STYLES)


def test_symbol_for():
    assert symbol_for(None, "line") is None
    assert symbol_for(None, "bar") is None
    assert symbol_for(None, "scatter") == "o"
    assert symbol_for("^", "line") == "t1"
    assert symbol_for("*", "scatter") == "star"
    assert symbol_for(".", "line") == "o"


def test_symbol_size():
    assert symbol_size("o", 6.0) == 6.0
    assert symbol_size(".", 6.0) == 3.0
    assert symbol_size(".", 2.0) == 2.0  # never below 2
    assert symbol_size(None, 8.0) == 8.0


def test_view_range():
    assert view_range(None, "linear") is None
    assert view_range(None, "log") is None
    assert view_range((-5.0, 5.0), "linear") == (-5.0, 5.0)
    lo, hi = view_range((1.0, 100.0), "log")
    assert close(lo, 0.0) and close(hi, 2.0)
    lo, hi = view_range((0.1, 10.0), "log")
    assert close(lo, -1.0) and close(hi, 1.0)


def test_bar_width():
    assert close(bar_width([1, 2, 3]), 0.8)
    assert close(bar_width([0, 0.5, 2]), 0.4)
    assert close(bar_width([3, 1, 2]), 0.8)  # order does not matter
    assert close(bar_width([1, 1, 2]), 0.8)  # duplicates ignored
    assert close(bar_width([1, float("nan"), 2]), 0.8)  # NaN ignored
    assert close(bar_width(np.array([0.0, 10.0, 20.0])), 8.0)


def test_bar_width_degenerate_cases():
    assert bar_width([]) == 0.8
    assert bar_width([5]) == 0.8
    assert bar_width([float("nan")]) == 0.8
