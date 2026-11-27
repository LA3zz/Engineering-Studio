"""Figure description as plain, immutable data (no Qt, no Matplotlib).

The interpreter/kernel builds a ``FigureSpec``; renderers (PyQtGraph in the GUI, Matplotlib for
export) draw it. Validation happens at construction (invalid specs cannot exist) and numeric
data is normalised: copied, converted to a read-only 1-D float64 array. Row/column vectors
(1xN, Nx1) are flattened because interpreter arrays are always 2-D; real matrices are rejected.
NaN is allowed (a gap in a line); complex data is not.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

import numpy as np

from engstudio.core.errors import DimensionError, ValidationError

__all__ = ["COLORMAPS", "PROJECTIONS", "SURFACE_KINDS", "AxesSpec", "FigureSpec", "INTERPRETERS",
           "LINE_STYLES", "MARKERS", "SCALES", "SERIES_KINDS", "SeriesSpec", "SurfaceSpec",
           "TextSpec"]

SeriesKind = Literal["line", "scatter", "bar", "stem", "area", "errorbar", "xline", "yline"]
SERIES_KINDS = ("line", "scatter", "bar", "stem", "area", "errorbar", "xline", "yline")
SURFACE_KINDS = ("surface", "mesh", "contour", "contourf")
PROJECTIONS = ("2d", "3d", "polar")
COLORMAPS = ("parula", "jet", "hot", "cool", "gray", "bone", "copper", "spring", "summer",
             "autumn", "winter", "turbo", "hsv", "viridis", "pink", "lines")
LINE_STYLES = ("-", "--", ":", "-.")
MARKERS = ("o", "s", "^", "x", "+", "*", ".", "d", "v", "<", ">", "p", "h")
SCALES = ("linear", "log")
INTERPRETERS = ("tex", "none")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _set(obj: object, name: str, value: object) -> None:
    object.__setattr__(obj, name, value)  # frozen dataclasses: normalise in __post_init__


def _vector(name: str, value: object) -> np.ndarray:
    try:
        raw = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name}: cannot convert to an array ({exc})") from None
    if raw.dtype.kind == "c":
        raise ValidationError(f"{name}: complex data cannot be plotted")
    if raw.dtype.kind in "USV":
        raise ValidationError(f"{name}: expected numbers, got {raw.dtype.kind!r} data")
    try:
        arr = np.array(raw, dtype=np.float64)  # copy: the caller's data is never shared
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name}: expected numbers ({exc})") from None
    if arr.ndim == 0:
        arr = arr.reshape(1)
    elif arr.ndim == 2 and 1 in arr.shape:
        arr = arr.reshape(-1)
    elif arr.ndim != 1:
        raise DimensionError(
            f"{name}: expected a vector, got an array of shape {tuple(arr.shape)}"
        )
    arr.setflags(write=False)
    return arr


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{name}: expected text, got {type(value).__name__}")
    return value


def _positive(name: str, value: object) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationError(f"{name}: expected a number, got {value!r}") from None
    if not (math.isfinite(v) and v > 0):
        raise ValidationError(f"{name}: must be a positive finite number, got {value!r}")
    return v


def _int_at_least_one(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{name}: expected an integer >= 1, got {value!r}")
    return value


def _choice(name: str, value: object, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise ValidationError(f"{name}: {value!r} is not one of {list(allowed)}")
    return value  # type: ignore[return-value]


def _limits(name: str, value: object, scale: str) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        lo, hi = (float(v) for v in value)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        raise ValidationError(f"{name}: expected (min, max) numbers, got {value!r}") from None
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise ValidationError(f"{name}: limits must be finite, got {value!r}")
    if lo >= hi:
        raise ValidationError(f"{name}: need min < max, got ({lo}, {hi})")
    if scale == "log" and lo <= 0:
        raise ValidationError(f"{name}: a logarithmic axis needs min > 0, got {lo}")
    return (lo, hi)


def _color_or_none(name: str, value: object) -> str | None:
    if value is not None and not (isinstance(value, str) and _COLOR.match(value)):
        raise ValidationError(f"{name}: expected None or '#rrggbb', got {value!r}")
    return value  # type: ignore[return-value]


def _finite(name: str, value: object) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationError(f"{name}: expected a number, got {value!r}") from None
    if not math.isfinite(v):
        raise ValidationError(f"{name}: must be finite, got {value!r}")
    return v


def _ticks(name: str, value: object) -> tuple[float, ...] | None:
    if value is None:
        return None
    ticks = tuple(_finite(name, v) for v in value)  # type: ignore[attr-defined]
    if any(b <= a for a, b in zip(ticks, ticks[1:], strict=False)):
        raise ValidationError(f"{name}: tick values must be strictly increasing")
    return ticks


def _labels(name: str, value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    return tuple(_text(name, v) for v in value)  # type: ignore[attr-defined]


@dataclass(frozen=True, eq=False)
class SeriesSpec:
    """One data series. ``color`` is ``None`` (renderer picks) or ``#rrggbb``;
    ``marker`` is ``None`` or one of ``MARKERS``.

    Kinds: ``line``, ``scatter`` (markers only), ``bar`` (bars from ``base_value``; width
    ``bar_width`` in x units, ``None`` = 80% of the smallest x gap), ``stem`` (vertical lines
    from ``base_value`` with markers), ``area`` (line filled down to ``base_value``).
    ``edge_color`` is the bar/area outline (``None`` = same as ``color``).
    ``errorbar``: a line with vertical error bars from ``y - err_low`` to ``y + err_high``.
    ``xline``/``yline``: one infinite reference line per value in ``x`` (``y`` is ignored).
    ``z`` (optional) makes a 3-D line or scatter (plot3/scatter3).
    """

    kind: SeriesKind
    x: np.ndarray
    y: np.ndarray
    label: str = ""
    color: str | None = None
    line_style: str = "-"
    line_width: float = 1.5
    marker: str | None = None
    marker_size: float = 6.0
    bar_width: float | None = None
    edge_color: str | None = None
    base_value: float = 0.0
    z: np.ndarray | None = None
    err_low: np.ndarray | None = None
    err_high: np.ndarray | None = None

    def __post_init__(self) -> None:
        _choice("kind", self.kind, SERIES_KINDS)
        x, y = _vector("x", self.x), _vector("y", self.y)
        if x.size != y.size:
            raise DimensionError(f"x has {x.size} points but y has {y.size}")
        _set(self, "x", x)
        _set(self, "y", y)
        _set(self, "label", _text("label", self.label))
        _color_or_none("color", self.color)
        _choice("line_style", self.line_style, LINE_STYLES)
        _set(self, "line_width", _positive("line_width", self.line_width))
        if self.marker is not None:
            _choice("marker", self.marker, MARKERS)
        _set(self, "marker_size", _positive("marker_size", self.marker_size))
        if self.bar_width is not None:
            _set(self, "bar_width", _positive("bar_width", self.bar_width))
        _color_or_none("edge_color", self.edge_color)
        _set(self, "base_value", _finite("base_value", self.base_value))
        for name in ("z", "err_low", "err_high"):
            value = getattr(self, name)
            if value is not None:
                arr = _vector(name, value)
                if arr.size != x.size:
                    raise DimensionError(f"{name} has {arr.size} points but x has {x.size}")
                _set(self, name, arr)
        if self.kind == "errorbar" and (self.err_low is None or self.err_high is None):
            raise ValidationError("errorbar series need err_low and err_high")

    @property
    def n_points(self) -> int:
        return int(self.x.size)

    def __reduce__(self):
        # Unpickling (kernel -> GUI pipe, copy.deepcopy) must go through the validating
        # constructor, otherwise the arrays would come back writable.
        return (SeriesSpec, (self.kind, self.x, self.y, self.label, self.color,
                             self.line_style, self.line_width, self.marker, self.marker_size,
                             self.bar_width, self.edge_color, self.base_value, self.z,
                             self.err_low, self.err_high))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SeriesSpec):
            return NotImplemented
        return (
            self.kind == other.kind and self.label == other.label
            and self.color == other.color and self.line_style == other.line_style
            and self.line_width == other.line_width and self.marker == other.marker
            and self.marker_size == other.marker_size
            and self.bar_width == other.bar_width and self.edge_color == other.edge_color
            and self.base_value == other.base_value
            and np.array_equal(self.x, other.x, equal_nan=True)
            and np.array_equal(self.y, other.y, equal_nan=True)
            and all(_same(getattr(self, n), getattr(other, n))
                    for n in ("z", "err_low", "err_high"))
        )


def _same(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    if a is None or b is None:
        return a is b
    return a.shape == b.shape and bool(np.array_equal(a, b, equal_nan=True))


def _grid(name: str, value: object) -> np.ndarray:
    try:
        arr = np.array(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name}: expected real numbers ({exc})") from None
    if arr.ndim != 2:
        raise DimensionError(f"{name}: expected a matrix, got shape {tuple(arr.shape)}")
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, eq=False)
class SurfaceSpec:
    """Gridded data: ``surface``/``mesh`` (3-D) or ``contour``/``contourf`` (2-D).

    ``x``, ``y`` and ``z`` are matrices of the same shape (vectors are expanded like
    meshgrid: x along columns, y along rows). ``levels``: number of contour levels or the
    level values; ``None`` lets the renderer choose. ``edge_color`` ``None`` = renderer
    default, ``"none"`` = no edges. ``face_color`` ``None`` = coloured by z (colormap).
    """

    kind: str
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    levels: int | tuple[float, ...] | None = None
    edge_color: str | None = None
    face_color: str | None = None
    line_width: float = 0.5
    alpha: float = 1.0
    show_text: bool = False
    label: str = ""

    def __post_init__(self) -> None:
        _choice("kind", self.kind, SURFACE_KINDS)
        z = _grid("z", self.z)
        if z.shape[0] < 2 or z.shape[1] < 2:
            raise DimensionError(f"z must be at least 2x2, got {z.shape[0]}x{z.shape[1]}")
        x, y = np.array(self.x, dtype=np.float64), np.array(self.y, dtype=np.float64)
        if x.ndim <= 1 or 1 in x.shape:
            x = np.tile(x.reshape(1, -1), (z.shape[0], 1))
        if y.ndim <= 1 or 1 in y.shape:
            y = np.tile(y.reshape(-1, 1), (1, z.shape[1]))
        if x.shape != z.shape or y.shape != z.shape:
            raise DimensionError(f"x {x.shape}, y {y.shape} and z {z.shape} must match")
        _set(self, "x", _grid("x", x))
        _set(self, "y", _grid("y", y))
        _set(self, "z", z)
        if self.levels is not None:
            if isinstance(self.levels, int) and not isinstance(self.levels, bool):
                if self.levels < 1:
                    raise ValidationError("levels: need at least one level")
            else:
                levels = _ticks("levels", self.levels)
                _set(self, "levels", levels)
        if self.edge_color != "none":
            _color_or_none("edge_color", self.edge_color)
        _color_or_none("face_color", self.face_color)
        _set(self, "line_width", _positive("line_width", self.line_width))
        a = _finite("alpha", self.alpha)
        if not 0 <= a <= 1:
            raise ValidationError(f"alpha: must be in [0, 1], got {a}")
        _set(self, "alpha", a)
        _set(self, "show_text", bool(self.show_text))
        _text("label", self.label)

    def __reduce__(self):
        return (SurfaceSpec, (self.kind, self.x, self.y, self.z, self.levels, self.edge_color,
                              self.face_color, self.line_width, self.alpha, self.show_text,
                              self.label))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SurfaceSpec):
            return NotImplemented
        return (self.kind == other.kind and self.levels == other.levels
                and self.edge_color == other.edge_color and self.face_color == other.face_color
                and self.line_width == other.line_width and self.alpha == other.alpha
                and self.show_text == other.show_text and self.label == other.label
                and all(_same(getattr(self, n), getattr(other, n)) for n in ("x", "y", "z")))


@dataclass(frozen=True)
class TextSpec:
    """A text annotation at data coordinates (x, y)."""

    x: float
    y: float
    text: str
    color: str | None = None

    def __post_init__(self) -> None:
        _set(self, "x", _finite("x", self.x))
        _set(self, "y", _finite("y", self.y))
        _text("text", self.text)
        _color_or_none("color", self.color)


@dataclass(frozen=True)
class AxesSpec:
    """One axes. ``cell`` = (row, col, rowspan, colspan) in the figure grid; ``None`` places
    the axes row-major by its index. Tick labels pair with tick values in order (labels repeat
    if there are fewer). Text fields use MATLAB's TeX subset unless ``interpreter`` is 'none'."""

    series: tuple[SeriesSpec, ...] = ()
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    xlim: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    xscale: str = "linear"
    yscale: str = "linear"
    grid: bool = False
    legend: bool = False
    cell: tuple[int, int, int, int] | None = None
    xticks: tuple[float, ...] | None = None
    xticklabels: tuple[str, ...] | None = None
    yticks: tuple[float, ...] | None = None
    yticklabels: tuple[str, ...] | None = None
    texts: tuple[TextSpec, ...] = ()
    equal_aspect: bool = False
    interpreter: str = "tex"
    surfaces: tuple[SurfaceSpec, ...] = ()
    projection: str = "2d"
    zlabel: str = ""
    zlim: tuple[float, float] | None = None
    view: tuple[float, float] | None = None
    colormap: str = "parula"
    colorbar: bool = False

    def __post_init__(self) -> None:
        series = tuple(self.series)
        for i, s in enumerate(series):
            if not isinstance(s, SeriesSpec):
                raise ValidationError(f"series[{i}]: expected SeriesSpec, got {type(s).__name__}")
        _set(self, "series", series)
        for name in ("title", "xlabel", "ylabel"):
            _text(name, getattr(self, name))
        _choice("xscale", self.xscale, SCALES)
        _choice("yscale", self.yscale, SCALES)
        _set(self, "xlim", _limits("xlim", self.xlim, self.xscale))
        _set(self, "ylim", _limits("ylim", self.ylim, self.yscale))
        _set(self, "grid", bool(self.grid))
        _set(self, "legend", bool(self.legend))
        if self.cell is not None:
            cell = tuple(self.cell)
            if len(cell) != 4:
                raise ValidationError(f"cell: expected (row, col, rowspan, colspan), got {cell!r}")
            r, c, rs, cs = cell
            for nm, v, lo in (("row", r, 0), ("col", c, 0), ("rowspan", rs, 1),
                              ("colspan", cs, 1)):
                if isinstance(v, bool) or not isinstance(v, int) or v < lo:
                    raise ValidationError(f"cell {nm}: expected an integer >= {lo}, got {v!r}")
            _set(self, "cell", cell)
        _set(self, "xticks", _ticks("xticks", self.xticks))
        _set(self, "yticks", _ticks("yticks", self.yticks))
        _set(self, "xticklabels", _labels("xticklabels", self.xticklabels))
        _set(self, "yticklabels", _labels("yticklabels", self.yticklabels))
        texts = tuple(self.texts)
        for i, t in enumerate(texts):
            if not isinstance(t, TextSpec):
                raise ValidationError(f"texts[{i}]: expected TextSpec, got {type(t).__name__}")
        _set(self, "texts", texts)
        _set(self, "equal_aspect", bool(self.equal_aspect))
        _choice("interpreter", self.interpreter, INTERPRETERS)
        surfaces = tuple(self.surfaces)
        for i, s in enumerate(surfaces):
            if not isinstance(s, SurfaceSpec):
                raise ValidationError(
                    f"surfaces[{i}]: expected SurfaceSpec, got {type(s).__name__}")
        _set(self, "surfaces", surfaces)
        _choice("projection", self.projection, PROJECTIONS)
        _text("zlabel", self.zlabel)
        _set(self, "zlim", _limits("zlim", self.zlim, "linear"))
        if self.view is not None:
            az, el = (_finite("view", v) for v in self.view)  # type: ignore[attr-defined]
            _set(self, "view", (az, el))
        _choice("colormap", self.colormap, COLORMAPS)
        _set(self, "colorbar", bool(self.colorbar))

    @property
    def needs_matplotlib(self) -> bool:
        """3-D, polar and gridded (surface/contour) axes are drawn with Matplotlib."""
        return self.projection != "2d" or bool(self.surfaces)

    def tick_pairs(self, axis: str) -> list[tuple[float, str]] | None:
        """[(value, label)] for 'x' or 'y' when custom ticks are set, else None."""
        ticks = self.xticks if axis == "x" else self.yticks
        labels = self.xticklabels if axis == "x" else self.yticklabels
        if ticks is None:
            return None
        if not labels:
            return [(v, f"{v:g}") for v in ticks] if labels is None else [(v, "") for v in ticks]
        return [(v, labels[i % len(labels)]) for i, v in enumerate(ticks)]


@dataclass(frozen=True)
class FigureSpec:
    """A figure window's content: ``axes`` fill a ``rows`` x ``cols`` grid in row-major order."""

    number: int = 1
    title: str = ""
    axes: tuple[AxesSpec, ...] = ()
    rows: int = 1
    cols: int = 1
    name: str = ""
    size: tuple[int, int] | None = None  # window (width, height) in pixels; None = default

    def __post_init__(self) -> None:
        _int_at_least_one("number", self.number)
        if self.size is not None:
            w, h = (int(round(_positive("size", v))) for v in self.size)  # type: ignore[attr-defined]
            _set(self, "size", (min(max(w, 100), 10000), min(max(h, 100), 10000)))
        _int_at_least_one("rows", self.rows)
        _int_at_least_one("cols", self.cols)
        _text("title", self.title)
        _text("name", self.name)
        axes = tuple(self.axes)
        for i, a in enumerate(axes):
            if not isinstance(a, AxesSpec):
                raise ValidationError(f"axes[{i}]: expected AxesSpec, got {type(a).__name__}")
        if len(axes) > self.rows * self.cols:
            raise ValidationError(
                f"{len(axes)} axes do not fit a {self.rows}x{self.cols} grid"
            )
        for i, a in enumerate(axes):
            if a.cell is not None:
                r, c, rs, cs = a.cell
                if r + rs > self.rows or c + cs > self.cols:
                    raise ValidationError(
                        f"axes[{i}]: cell {a.cell} is outside the {self.rows}x{self.cols} grid")
        _set(self, "axes", axes)

    @property
    def needs_matplotlib(self) -> bool:
        return any(a.needs_matplotlib for a in self.axes)

    def placements(self) -> list[tuple[int, int, int, int]]:
        """(row, col, rowspan, colspan) for every axes, in order."""
        out = []
        for i, a in enumerate(self.axes):
            if a.cell is not None:
                out.append(a.cell)
            else:
                r, c = divmod(i, self.cols)
                out.append((r, c, 1, 1))
        return out
