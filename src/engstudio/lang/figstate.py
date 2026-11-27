"""Kernel-side figure state and plot-argument handling (pure Python/NumPy, no GUI, no values).

``FigureManager`` holds the mutable state a MATLAB-style session needs (figures, current figure,
current axes, hold flag, handles) and turns it into immutable ``FigureSpec`` snapshots.
``build_series`` turns already-converted ``plot`` arguments (2-D float arrays and ``str``) into
``SeriesSpec`` objects. Handles: a figure's handle is its number (1..MAX_FIGURE); axes and
lines get unique numbers above MAX_FIGURE.

Differences from MATLAB: only the line properties Color, LineWidth, LineStyle, Marker,
MarkerSize and DisplayName are supported; the marker set is o + * . x s ^ ; ``figure`` picks
the lowest unused number (not verified against MATLAB); a single complex argument plots real
against imaginary part; a marker-only line specification such as 'o' draws markers without a
line, as in MATLAB.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from fractions import Fraction

import numpy as np

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.plotting.model import (
    LINE_STYLES,
    AxesSpec,
    FigureSpec,
    SeriesSpec,
    SurfaceSpec,
    TextSpec,
)

__all__ = ["FigureManager", "MAX_FIGURE", "MAX_GRID", "build_series", "parse_color",
           "parse_linespec"]

MAX_FIGURE = 100000
_LETTER_COLORS = {
    "r": "#ff0000", "g": "#00ff00", "b": "#0000ff", "c": "#00ffff",
    "m": "#ff00ff", "y": "#ffff00", "k": "#000000", "w": "#ffffff",
}
_NAME_COLORS = {
    "red": "r", "green": "g", "blue": "b", "cyan": "c", "magenta": "m", "yellow": "y",
    "black": "k", "white": "w",
}
_MARKERS = {"o": "o", "+": "+", "*": "*", ".": ".", "x": "x", "s": "s", "^": "^", "d": "d",
            "v": "v", "<": "<", ">": ">", "p": "p", "h": "h", "square": "s", "diamond": "d",
            "pentagram": "p", "hexagram": "h"}
_UNSUPPORTED_MARKERS = ""
_PROPS = ("color", "linewidth", "linestyle", "marker", "markersize", "displayname")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def parse_color(value: object, who: str = "plot") -> str:
    """'r', 'red', '#rrggbb' or an RGB triple in [0, 1] -> '#rrggbb'."""
    if isinstance(value, str):
        key = value.strip()
        if _HEX.match(key):
            return key.lower()
        key = _NAME_COLORS.get(key.lower(), key)
        if key in _LETTER_COLORS:
            return _LETTER_COLORS[key]
        raise ValidationError(f"{who}: unknown color {value!r}.")
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.size != 3 or not np.all((arr >= 0) & (arr <= 1)):  # NaN fails the comparison too
        raise ValidationError(f"{who}: a color must be an RGB triple with values in [0, 1].")
    r, g, b = (int(round(float(v) * 255)) for v in arr)
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_linespec(text: str, who: str = "plot") -> tuple[str | None, str | None, str | None]:
    """'r--o' -> (color, line style, marker); each part is None when not given."""
    color = style = marker = None
    i = 0
    while i < len(text):
        tok = text[i:i + 2] if text[i:i + 2] in ("--", "-.") else text[i]
        i += len(tok)
        if tok in ("--", "-.", "-", ":"):
            if style is not None:
                raise ValidationError(f"{who}: invalid line specification {text!r}.")
            style = tok
        elif tok in _LETTER_COLORS:
            if color is not None:
                raise ValidationError(f"{who}: invalid line specification {text!r}.")
            color = _LETTER_COLORS[tok]
        elif tok in _MARKERS and len(tok) == 1:
            if marker is not None:
                raise ValidationError(f"{who}: invalid line specification {text!r}.")
            marker = _MARKERS[tok]
        elif tok in _UNSUPPORTED_MARKERS:
            raise ValidationError(f"{who}: marker {tok!r} is not supported yet.")
        else:
            raise ValidationError(f"{who}: invalid line specification {text!r}.")
    return color, style, marker


def _is_linespec(text: str) -> bool:
    if not text or len(text) > 5:
        return False
    try:
        parse_linespec(text)
    except ValidationError:
        return False
    return True


def _is_vector(a: np.ndarray) -> bool:
    return a.shape[0] == 1 or a.shape[1] == 1


def _flat(a: np.ndarray) -> np.ndarray:
    return a.reshape(-1, order="F")


def _columns(x: np.ndarray | None, y: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """The (x, y) pairs MATLAB's plot(x, y) draws; matrices go by column."""
    empty = [(np.empty(0), np.empty(0))]
    if x is None:
        if y.size == 0:
            return empty
        if _is_vector(y):
            v = _flat(y)
            return [(np.arange(1.0, v.size + 1), v)]
        t = np.arange(1.0, y.shape[0] + 1)
        return [(t, y[:, j]) for j in range(y.shape[1])]
    if x.size == 0 and y.size == 0:
        return empty
    if _is_vector(x) and _is_vector(y):
        xv, yv = _flat(x), _flat(y)
        if xv.size != yv.size:
            raise DimensionError(
                f"plot: vectors must be the same length (x has {xv.size}, y has {yv.size}).")
        return [(xv, yv)]
    if _is_vector(x):
        xv = _flat(x)
        if xv.size == y.shape[0]:
            return [(xv, y[:, j]) for j in range(y.shape[1])]
        if xv.size == y.shape[1]:
            return [(xv, y[i, :]) for i in range(y.shape[0])]
        raise DimensionError(f"plot: x has {xv.size} points but y is {y.shape[0]}x{y.shape[1]}.")
    if _is_vector(y):
        yv = _flat(y)
        if yv.size == x.shape[0]:
            return [(x[:, j], yv) for j in range(x.shape[1])]
        raise DimensionError(f"plot: y has {yv.size} points but x is {x.shape[0]}x{x.shape[1]}.")
    if x.shape != y.shape:
        raise DimensionError(
            f"plot: x is {x.shape[0]}x{x.shape[1]} but y is {y.shape[0]}x{y.shape[1]}.")
    return [(x[:, j], y[:, j]) for j in range(y.shape[1])]


def _positive(name: str, value: object) -> float:
    arr = None if isinstance(value, str) else np.asarray(value, dtype=float)
    if arr is None or arr.size != 1 or not (np.isfinite(arr.item()) and arr.item() > 0):
        raise ValidationError(f"plot: {name} must be a positive number.")
    return float(arr.item())


def _name_value(rest: list) -> dict[str, object]:
    if len(rest) % 2:
        raise ValidationError("plot: name-value arguments must come in pairs.")
    out: dict[str, object] = {}
    for name, value in zip(rest[::2], rest[1::2], strict=True):
        if not isinstance(name, str) or name.lower() not in _PROPS:
            shown = name if isinstance(name, str) else "<number>"
            raise ValidationError(f"plot: unrecognized property {shown!r}.")
        key = name.lower()
        if key == "color":
            out[key] = parse_color(value)
        elif key in ("linewidth", "markersize"):
            out[key] = _positive(name, value)
        elif key == "linestyle":
            if not isinstance(value, str) or value not in (*LINE_STYLES, "none"):
                raise ValidationError("plot: LineStyle must be one of -, --, :, -., none.")
            out[key] = value
        elif key == "marker":
            if not isinstance(value, str) or (value != "none" and value not in _MARKERS):
                raise ValidationError(f"plot: Marker {value!r} is not supported.")
            out[key] = _MARKERS.get(value, value)
        else:  # displayname
            if not isinstance(value, str):
                raise ValidationError("plot: DisplayName must be text.")
            out[key] = value
    return out


def build_series(items: list) -> list[SeriesSpec]:
    """``plot`` arguments (2-D float arrays and ``str``) -> series, in drawing order."""
    if not items:
        raise ValidationError("plot: Not enough input arguments.")
    groups: list[tuple[np.ndarray | None, np.ndarray, str | None]] = []
    i, n = 0, len(items)
    while i < n and not isinstance(items[i], str):
        first = items[i]
        i += 1
        if i < n and not isinstance(items[i], str):
            x, y = first, items[i]
            i += 1
        else:
            x, y = None, first
        spec = None
        if (i < n and isinstance(items[i], str) and items[i].lower() not in _PROPS
                and _is_linespec(items[i])):
            spec = items[i]
            i += 1
        groups.append((x, y, spec))
    if not groups:
        raise ValidationError(f"plot: expected data before {items[0]!r}.")
    props = _name_value(items[i:])
    single = len(groups) == 1 and groups[0][0] is None
    out: list[SeriesSpec] = []
    for x, y, spec in groups:
        if y.dtype.kind == "c" and x is None and single:
            x, y = y.real, y.imag
        elif y.dtype.kind == "c" or (x is not None and x.dtype.kind == "c"):
            raise ValidationError("plot: complex data is only supported as a single argument.")
        color, style, marker = parse_linespec(spec) if spec else (None, None, None)
        for xs, ys in _columns(x, y):
            out.append(_series(xs, ys, color, style, marker, props))
    return out


def _series(xs, ys, color, style, marker, props) -> SeriesSpec:
    color = props.get("color", color)
    line_off = False
    if "linestyle" in props:
        line_off = props["linestyle"] == "none"
        if not line_off:
            style = props["linestyle"]
    elif style is None and marker is not None and "marker" not in props:
        line_off = True  # 'o' alone: markers only
    if "marker" in props:
        marker = None if props["marker"] == "none" else props["marker"]
    kwargs: dict[str, object] = {"label": props.get("displayname", ""), "color": color}
    if "linewidth" in props:
        kwargs["line_width"] = props["linewidth"]
    if "markersize" in props:
        kwargs["marker_size"] = props["markersize"]
    if line_off and marker is not None:
        return SeriesSpec("scatter", xs, ys, marker=marker, **kwargs)
    return SeriesSpec("line", xs, ys, line_style=style or "-", marker=marker, **kwargs)


# ----------------------------------------------------------------------------- state
MAX_GRID = 50  # subplot(m, n, ...) limit per side
_AXES_FIELDS = ("title", "xlabel", "ylabel", "xlim", "ylim", "xscale", "yscale", "grid",
                "legend", "xticks", "xticklabels", "yticks", "yticklabels", "equal_aspect",
                "interpreter", "projection", "zlabel", "zlim", "view", "colormap", "colorbar")


@dataclass
class _Axes:
    handle: int
    grid: tuple[int, int, int, int, int, int] = (1, 1, 0, 0, 1, 1)  # m, n, r0, c0, rs, cs
    hold: bool = False
    lines: list[list] = field(default_factory=list)  # [handle, SeriesSpec]
    texts: list[list] = field(default_factory=list)  # [handle, TextSpec]
    surfaces: list[list] = field(default_factory=list)  # [handle, SurfaceSpec]
    props: dict[str, object] = field(default_factory=dict)  # AxesSpec field overrides

    def rect(self) -> tuple[Fraction, Fraction, Fraction, Fraction]:
        m, n, r0, c0, rs, cs = self.grid
        return (Fraction(c0, n), Fraction(r0, m), Fraction(c0 + cs, n), Fraction(r0 + rs, m))


def _overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@dataclass
class _Figure:
    number: int
    name: str = ""
    title: str = ""  # sgtitle
    props: dict[str, object] = field(default_factory=dict)
    axes: list[_Axes] = field(default_factory=list)
    current: _Axes | None = None


class FigureManager:
    def __init__(self) -> None:
        self._figs: dict[int, _Figure] = {}
        self._recent: list[int] = []  # activation order, last = current figure
        self._next_handle = MAX_FIGURE + 1
        self.publisher: object | None = None  # set by builtins_plot.install_plot

    def _handle(self) -> int:
        self._next_handle += 1
        return self._next_handle - 1

    # -- figures ---------------------------------------------------------------
    def numbers(self) -> list[int]:
        return sorted(self._figs)

    def current_number(self) -> int | None:
        return self._recent[-1] if self._recent else None

    def props(self, number: int) -> dict[str, object]:
        return dict(self._figs[number].props)

    def figure(self, number: int | None = None, name: str | None = None,
               props: dict[str, object] | None = None) -> int:
        """Create figure ``number`` (lowest unused if None) or make it current."""
        if number is None:
            number = next(k for k in range(1, MAX_FIGURE + 2) if k not in self._figs)
        if not 1 <= number <= MAX_FIGURE:
            raise ValidationError(f"figure: number must be an integer 1..{MAX_FIGURE}.")
        fig = self._figs.get(number)
        if fig is None:
            fig = self._figs[number] = _Figure(number)
        if name is not None:
            fig.name = name
        if props:
            fig.props.update(props)
        if number in self._recent:
            self._recent.remove(number)
        self._recent.append(number)
        return number

    def update_figure(self, number: int, name: str | None, props: dict[str, object]) -> None:
        """set(fig, ...): change name/properties without making the figure current."""
        fig = self._figs[number]
        if name is not None:
            fig.name = name
        fig.props.update(props)

    def figure_name(self, number: int) -> str:
        return self._figs[number].name

    def gcf(self) -> int:
        cur = self.current_number()
        return cur if cur is not None else self.figure()

    def _fig(self) -> _Figure:
        return self._figs[self.gcf()]

    def _axes(self) -> _Axes:
        fig = self._fig()
        if fig.current is None:
            if not fig.axes:
                fig.axes.append(_Axes(self._handle()))
            fig.current = fig.axes[-1]
        return fig.current

    def gca(self) -> int:
        return self._axes().handle

    def set_title(self, text: str) -> int:
        """sgtitle: the figure's overall title."""
        fig = self._fig()
        fig.title = text
        return fig.number

    def figure_title(self, number: int) -> str:
        return self._figs[number].title

    def clf(self) -> int:
        fig = self._fig()
        fig.axes.clear()
        fig.current = None
        fig.title = ""
        return fig.number

    def cla(self) -> int:
        ax = self._axes()
        ax.lines.clear()
        ax.texts.clear()
        ax.surfaces.clear()
        ax.hold = False
        return self.gcf()

    def close(self, which: int | str | None = None) -> list[int]:
        """Close the current figure (None), figure ``which`` or ``'all'``; returns numbers."""
        if which == "all":
            gone = self.numbers()
        elif which is None:
            gone = [self._recent[-1]] if self._recent else []
        elif isinstance(which, int) and which in self._figs:
            gone = [which]
        elif isinstance(which, int):
            raise ValidationError(f"close: figure {which} does not exist.")
        else:
            raise ValidationError("close: expected a figure number or 'all'.")
        for k in gone:
            del self._figs[k]
            self._recent.remove(k)
        return gone

    # -- subplots --------------------------------------------------------------
    def subplot(self, m: int, n: int, positions: list[int]) -> int:
        """Make the axes at grid cells ``positions`` (1-based, row-major) of an m x n grid
        current, creating it (and deleting axes it overlaps) if needed."""
        if not (1 <= m <= MAX_GRID and 1 <= n <= MAX_GRID):
            raise ValidationError(f"subplot: grid size must be 1..{MAX_GRID} per side.")
        if not positions or any(not 1 <= p <= m * n for p in positions):
            raise ValidationError(f"subplot: position must be 1..{m * n} for a {m}x{n} grid.")
        rows = [(p - 1) // n for p in positions]
        cols = [(p - 1) % n for p in positions]
        r0, c0 = min(rows), min(cols)
        new = _Axes(0, (m, n, r0, c0, max(rows) - r0 + 1, max(cols) - c0 + 1))
        rect = new.rect()
        fig = self._fig()
        for ax in fig.axes:
            if ax.rect() == rect:
                fig.current = ax
                return ax.handle
        fig.axes[:] = [ax for ax in fig.axes if not _overlap(ax.rect(), rect)]
        new.handle = self._handle()
        fig.axes.append(new)
        fig.current = new
        return new.handle

    def select_axes(self, handle: int) -> int:
        """axes(h): make axes ``h`` (and its figure) current."""
        for fig in self._figs.values():
            for ax in fig.axes:
                if ax.handle == handle:
                    self.figure(fig.number)
                    fig.current = ax
                    return fig.number
        raise ValidationError("axes: invalid axes handle.")

    # -- axes state ------------------------------------------------------------
    def hold(self, mode: str | None = None) -> bool:
        ax = self._axes()
        if mode is None or mode == "toggle":
            ax.hold = not ax.hold
        elif mode in ("on", "off", "all"):
            ax.hold = mode != "off"
        else:
            raise ValidationError(f"hold: unknown option {mode!r}; use on, off or no argument.")
        return ax.hold

    def ishold(self) -> bool:
        return self._axes().hold

    def add_lines(self, series: list[SeriesSpec], props: dict | None = None,
                  surfaces: list[SurfaceSpec] | None = None) -> list[int]:
        """Add series (and gridded surfaces) to the current axes. Without hold, the axes is
        reset first (as MATLAB's high-level plot functions do); ``props`` are then applied
        (e.g. log scales, a 3-D projection). With hold on, a 3-D or polar projection already
        set stays (plot after surf + hold on draws into the 3-D axes)."""
        ax = self._axes()
        if not ax.hold:
            keep = {k: ax.props[k] for k in ("colormap",) if k in ax.props}
            ax.lines.clear()
            ax.texts.clear()
            ax.surfaces.clear()
            ax.props.clear()
            ax.props.update(keep)
        if props:
            if ax.hold and "projection" in props and ax.props.get("projection", "2d") != "2d":
                props = {k: v for k, v in props.items() if k != "projection"}
            ax.props.update(props)
        handles = []
        for s in series:
            handles.append(self._handle())
            ax.lines.append([handles[-1], s])
        for g in surfaces or ():
            handles.append(self._handle())
            ax.surfaces.append([handles[-1], g])
        return handles

    def add_overlay(self, series: list[SeriesSpec]) -> list[int]:
        """Add series to the current axes without clearing it, whatever the hold state."""
        ax = self._axes()
        handles = []
        for s in series:
            handles.append(self._handle())
            ax.lines.append([handles[-1], s])
        return handles

    def update_surfaces(self, fn, handle: int | None = None) -> bool:
        """Replace each surface ``s`` of the axes with ``fn(s)``; True if any changed."""
        changed = False
        for item in self._find_axes(handle).surfaces:
            new = fn(item[1])
            if new is not item[1]:
                item[1] = new
                changed = True
        return changed

    def axes_props(self, handle: int | None = None) -> dict[str, object]:
        return self._find_axes(handle).props

    def set_axes(self, handle: int | None = None, **props: object) -> None:
        ax = self._find_axes(handle)
        for key, value in props.items():
            if key not in _AXES_FIELDS:
                raise ValidationError(f"internal: unknown axes field {key!r}")
            if value is None:
                ax.props.pop(key, None)
            else:
                ax.props[key] = value

    def axes_series(self, handle: int | None = None) -> list[SeriesSpec]:
        return [s for _, s in self._find_axes(handle).lines]

    def relabel(self, labels: list[str | None], handle: int | None = None) -> None:
        """legend: set series labels in order (None leaves a label unchanged)."""
        ax = self._find_axes(handle)
        for item, label in zip(ax.lines, labels, strict=False):
            if label is not None:
                item[1] = replace(item[1], label=label)

    def add_text(self, text: TextSpec) -> int:
        ax = self._axes()
        h = self._handle()
        ax.texts.append([h, text])
        return h

    def is_axes(self, handle: int) -> bool:
        return any(ax.handle == handle for f in self._figs.values() for ax in f.axes)

    def is_figure(self, handle: int) -> bool:
        return handle in self._figs

    def line(self, handle: int) -> SeriesSpec | None:
        for f in self._figs.values():
            for ax in f.axes:
                for h, s in ax.lines:
                    if h == handle:
                        return s
        return None

    def replace_line(self, handle: int, spec: SeriesSpec) -> int:
        """Replace line ``handle``; returns the number of its figure."""
        for f in self._figs.values():
            for ax in f.axes:
                for item in ax.lines:
                    if item[0] == handle:
                        item[1] = spec
                        return f.number
        raise ValidationError("set: invalid line handle.")

    def figure_of(self, handle: int) -> int:
        if handle in self._figs:
            return handle
        for f in self._figs.values():
            for ax in f.axes:
                if ax.handle == handle or any(h == handle for h, _ in ax.lines + ax.texts):
                    return f.number
        raise ValidationError("invalid graphics handle.")

    def _find_axes(self, handle: int | None) -> _Axes:
        if handle is None:
            return self._axes()
        for f in self._figs.values():
            for ax in f.axes:
                if ax.handle == handle:
                    return ax
        raise ValidationError("invalid axes handle.")

    # -- snapshots -------------------------------------------------------------
    def snapshot(self, number: int | None = None) -> FigureSpec:
        number = self.gcf() if number is None else number
        fig = self._figs[number]
        rows = cols = 1
        for ax in fig.axes:
            rows, cols = math.lcm(rows, ax.grid[0]), math.lcm(cols, ax.grid[1])
        if rows > 600 or cols > 600:
            raise ValidationError("subplot: these grids cannot be combined in one figure.")
        axes = []
        for ax in fig.axes:
            m, n, r0, c0, rs, cs = ax.grid
            fr, fc = rows // m, cols // n
            axes.append(AxesSpec(
                series=tuple(s for _, s in ax.lines),
                texts=tuple(t for _, t in ax.texts),
                surfaces=tuple(g for _, g in ax.surfaces),
                cell=(r0 * fr, c0 * fc, rs * fr, cs * fc),
                **ax.props,  # type: ignore[arg-type]
            ))
        pos = fig.props.get("Position")
        size = (pos[2], pos[3]) if isinstance(pos, list) and pos[2] > 0 and pos[3] > 0 else None
        return FigureSpec(number=number, axes=tuple(axes), rows=rows, cols=cols,
                          name=fig.name, title=fig.title, size=size)
