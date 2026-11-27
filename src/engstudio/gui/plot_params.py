"""Rendering decisions for figures that need no Qt or PyQtGraph: colours, marker/pen
mapping, log-axis ranges, bar width. Kept pure so they can be tested exhaustively."""

from __future__ import annotations

import math
from collections.abc import Iterable

from engstudio.gui.theme import get_palette

__all__ = ["PEN_STYLES", "SERIES_COLORS", "SYMBOLS", "bar_width", "plot_colors",
           "series_color", "symbol_for", "symbol_size", "tick_values", "view_range"]

# Default colour cycle per theme; every colour has contrast >= 3:1 against the plot
# background (tests/gui/test_plot_params.py).
SERIES_COLORS: dict[str, tuple[str, ...]] = {
    "light": ("#1f6fb4", "#d62728", "#2a8a2a", "#8d5bb8", "#c85a00", "#0b8a8f", "#b5338a"),
    "dark": ("#4da3ff", "#ff8a80", "#7bd88f", "#c792ea", "#ffb74d", "#4dd0e1", "#f06292"),
}
PEN_STYLES = {"-": "solid", "--": "dash", ":": "dot", "-.": "dashdot"}
# PyQtGraph: 't' points down, 't1' up, 't2' right, 't3' left.
SYMBOLS = {"o": "o", "s": "s", "^": "t1", "v": "t", ">": "t2", "<": "t3", "x": "x", "+": "+",
           "*": "star", ".": "o", "d": "d", "p": "p", "h": "h"}


def plot_colors(theme: str) -> tuple[str, str]:
    """(background, foreground) for plots. Raises ValueError for an unknown theme."""
    p = get_palette(theme)
    return p.base, p.text


def series_color(theme: str, index: int, explicit: str | None) -> str:
    """The series' own colour, else the theme's cycle colour for ``index``."""
    if explicit is not None:
        return explicit
    cycle = SERIES_COLORS[theme]
    return cycle[index % len(cycle)]


def symbol_for(marker: str | None, kind: str) -> str | None:
    """PyQtGraph symbol for a marker; scatter series default to circles, lines to none."""
    if marker is None:
        return "o" if kind == "scatter" else None
    return SYMBOLS[marker]


def symbol_size(marker: str | None, size: float) -> float:
    return max(2.0, size * 0.5) if marker == "." else size  # "." is a small dot


def view_range(lim: tuple[float, float] | None, scale: str) -> tuple[float, float] | None:
    """Axis limits in view coordinates (PyQtGraph log axes work in log10 units)."""
    if lim is None:
        return None
    lo, hi = lim
    if scale == "log":
        return (math.log10(lo), math.log10(hi))
    return (lo, hi)


def tick_values(pairs: list[tuple[float, str]], scale: str) -> list[tuple[float, str]]:
    """Custom ticks in view coordinates; on a log axis non-positive ticks are dropped."""
    if scale != "log":
        return list(pairs)
    return [(math.log10(v), label) for v, label in pairs if v > 0]


def bar_width(x: Iterable[float]) -> float:
    """80% of the smallest gap between distinct finite x positions (0.8 if fewer than two)."""
    xs = sorted({float(v) for v in x if math.isfinite(v)})
    if len(xs) < 2:
        return 0.8
    return 0.8 * min(b - a for a, b in zip(xs, xs[1:], strict=False))
