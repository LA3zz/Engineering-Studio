"""2-D plot types (P5.3): bar, stem, stairs, area, scatter, semilogx, semilogy, loglog,
histogram, hist, histcounts.

Differences from MATLAB:
- ``bar``: grouped bars for matrices (one series per column); 'stacked' and horizontal bars
  are not supported. Bar widths assume evenly spaced x.
- ``stairs`` and ``area`` take vectors only (no stacked areas). ``stairs`` is drawn as a line.
- ``scatter``: one size and one colour for all points (per-point sizes/colours are not
  supported). Size is the marker area in points^2 as in MATLAB (default 36).
- ``histogram``: default bins follow NumPy's 'auto' rule (MATLAB's automatic rule differs
  slightly); Normalization 'count', 'probability', 'pdf', 'countdensity', 'cdf' and
  'cumcount'; edges must be evenly spaced. ``hist(y, n)`` uses n equal bins (default 10) and
  returns ``[counts, centers]`` when outputs are requested (then nothing is drawn).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _int, _need
from engstudio.lang.builtins_plotaxes import to_py
from engstudio.lang.figstate import FigureManager, build_series, parse_color, parse_linespec
from engstudio.plotting.model import SeriesSpec

__all__ = ["plot2d_functions"]

Push = Callable[[int | None], None]


def _handles(hs: list[int]) -> list:
    return [np.array([[float(h)] for h in hs])]


def _spacing(x: np.ndarray) -> float:
    xs = np.unique(x[np.isfinite(x)])
    return float(np.min(np.diff(xs))) if xs.size > 1 else 1.0


def _is_word(v: object) -> bool:
    return isinstance(v, str)


def _data_and_rest(items: list, who: str, max_data: int = 2) -> tuple[list[np.ndarray], list]:
    """Leading numeric arguments (up to ``max_data``) and the rest."""
    data = []
    while items and not _is_word(items[0]) and len(data) < max_data:
        data.append(items.pop(0))
    if not data:
        raise ValidationError(f"{who}: Not enough input arguments.")
    for a in data:
        if a.dtype.kind == "c":
            raise ValidationError(f"{who}: complex data is not supported.")
    return data, items


def _flat(a: np.ndarray) -> np.ndarray:
    return a.reshape(-1, order="F")


def _is_vector(a: np.ndarray) -> bool:
    return a.ndim == 2 and (a.shape[0] == 1 or a.shape[1] == 1)


def _xy(data: list[np.ndarray], who: str) -> tuple[np.ndarray, np.ndarray]:
    """(x, Y) with Y as a matrix of columns; vectors become one column."""
    if len(data) == 1:
        y = data[0]
        y = _flat(y).reshape(-1, 1) if _is_vector(y) else y
        return np.arange(1.0, y.shape[0] + 1), y
    x, y = data
    xv = _flat(x)
    if _is_vector(y):
        y = _flat(y).reshape(-1, 1)
    elif y.shape[0] != xv.size and y.shape[1] == xv.size:
        y = y.T
    if y.shape[0] != xv.size:
        raise ValidationError(f"{who}: x must have one value per row of y "
                              f"(x has {xv.size}, y has {y.shape[0]} rows).")
    return xv, y


def _props(rest: list, who: str, allowed: set[str]) -> dict[str, object]:
    if len(rest) % 2:
        raise ValidationError(f"{who}: property names and values must come in pairs.")
    out: dict[str, object] = {}
    for name, value in zip(rest[::2], rest[1::2], strict=True):
        if not _is_word(name):
            raise ValidationError(f"{who}: property names must be text.")
        key = name.lower()
        if key not in allowed:
            raise ValidationError(f"{who}: unrecognized property {name!r}.")
        out[key] = value
    return out


def _color(value: object, who: str) -> str | None:
    if _is_word(value) and value.lower() in ("flat", "auto", "none"):  # type: ignore[union-attr]
        return None
    return parse_color(value, who)


def _positive(value: object, who: str, what: str) -> float:
    if _is_word(value):
        raise ValidationError(f"{who}: {what} must be a number.")
    a = np.asarray(value, dtype=float).reshape(-1)
    if a.size != 1 or not (np.isfinite(a[0]) and a[0] > 0):
        raise ValidationError(f"{who}: {what} must be a positive number.")
    return float(a[0])


_COMMON = {"displayname", "linewidth", "color"}
_BAR_PROPS = _COMMON | {"facecolor", "edgecolor", "barwidth", "facealpha", "basevalue",
                        "showbaseline", "linestyle"}


def bar_series(items: list) -> list[SeriesSpec]:
    data, rest = _data_and_rest(list(items), "bar")
    ratio = 0.8
    color = None
    if rest and not _is_word(rest[0]):
        raise ValidationError("bar: too many numeric arguments.")
    # bar(y, width) puts the width as second numeric argument when y is not followed by y
    if len(data) == 2 and data[1].size == 1 and data[0].size > 1:
        ratio = _positive(data.pop(), "bar", "the bar width")
    while rest and _is_word(rest[0]) and rest[0].lower() in (
            "grouped", "stacked", "hist", "histc", "r", "g", "b", "c", "m", "y", "k", "w"):
        word = rest.pop(0).lower()
        if word in ("stacked", "hist", "histc"):
            raise NotSupportedError(f"bar: the '{word}' style is not supported yet.")
        if word != "grouped":
            color = parse_color(word, "bar")
    props = _props(rest, "bar", _BAR_PROPS)
    if "barwidth" in props:
        ratio = _positive(props["barwidth"], "bar", "BarWidth")
    if ratio > 1:
        ratio = 1.0
    face = props.get("facecolor", props.get("color"))
    if face is not None:
        color = _color(face, "bar")
    edge = _color(props["edgecolor"], "bar") if "edgecolor" in props else None
    base = 0.0
    if "basevalue" in props:
        base = float(np.asarray(props["basevalue"], dtype=float).reshape(-1)[0])
    label = props.get("displayname", "")
    x, y = _xy(data, "bar")
    gap = _spacing(x)
    k = y.shape[1]
    out = []
    if k == 1:
        out.append(SeriesSpec("bar", x, y[:, 0], color=color, edge_color=edge,
                              bar_width=ratio * gap, base_value=base,
                              label=label if isinstance(label, str) else ""))
        return out
    group = min(0.8, k / (k + 1.5)) * gap
    width = group / k * (ratio / 0.8)
    for j in range(k):
        offset = (j - (k - 1) / 2) * group / k
        out.append(SeriesSpec("bar", x + offset, y[:, j], color=color, edge_color=edge,
                              bar_width=width, base_value=base))
    return out


def _linespec_first(rest: list, who: str) -> tuple[tuple[str | None, str | None, str | None],
                                                   list]:
    if rest and _is_word(rest[0]) and rest[0].lower() not in _COMMON | {
            "marker", "markersize", "linestyle", "filled", "markerfacecolor", "basevalue"}:
        try:
            spec = parse_linespec(rest[0], who)
        except ValidationError:
            return (None, None, None), rest
        return spec, rest[1:]
    return (None, None, None), rest


_LINE_PROPS = _COMMON | {"marker", "markersize", "linestyle", "markerfacecolor",
                         "markeredgecolor", "basevalue", "showbaseline"}


def _line_kwargs(color, style, marker, props: dict, who: str) -> dict[str, object]:
    kw: dict[str, object] = {"color": color, "line_style": style or "-", "marker": marker}
    if "color" in props:
        kw["color"] = parse_color(props["color"], who)
    if "linewidth" in props:
        kw["line_width"] = _positive(props["linewidth"], who, "LineWidth")
    if "markersize" in props:
        kw["marker_size"] = _positive(props["markersize"], who, "MarkerSize")
    if "linestyle" in props:
        ls = props["linestyle"]
        if ls not in ("-", "--", ":", "-."):
            raise ValidationError(f"{who}: LineStyle must be one of -, --, :, -.")
        kw["line_style"] = ls
    if "marker" in props:
        m = props["marker"]
        kw["marker"] = None if m == "none" else parse_linespec(str(m), who)[2]
    if "displayname" in props:
        kw["label"] = props["displayname"]
    return kw


def stem_series(items: list) -> list[SeriesSpec]:
    data, rest = _data_and_rest(list(items), "stem")
    filled = False
    if rest and _is_word(rest[0]) and rest[0].lower() == "filled":
        filled = True
        rest = rest[1:]
    (color, style, marker), rest = _linespec_first(rest, "stem")
    if rest and _is_word(rest[0]) and rest[0].lower() == "filled":
        filled = True
        rest = rest[1:]
    props = _props(rest, "stem", _LINE_PROPS)
    kw = _line_kwargs(color, style, marker or "o", props, "stem")
    base = float(np.asarray(props.get("basevalue", 0.0), dtype=float).reshape(-1)[0])
    x, y = _xy(data, "stem")
    del filled  # markers are always drawn filled
    return [SeriesSpec("stem", x, y[:, j], base_value=base, **kw)  # type: ignore[arg-type]
            for j in range(y.shape[1])]


def stairs_series(items: list) -> list[SeriesSpec]:
    data, rest = _data_and_rest(list(items), "stairs")
    (color, style, marker), rest = _linespec_first(rest, "stairs")
    props = _props(rest, "stairs", _LINE_PROPS)
    kw = _line_kwargs(color, style, marker, props, "stairs")
    x, y = _xy(data, "stairs")
    out = []
    for j in range(y.shape[1]):
        yj = y[:, j]
        if x.size == 0:
            xs, ys = x, yj
        else:
            xs = np.repeat(x, 2)[1:]
            ys = np.repeat(yj, 2)[:-1]
        out.append(SeriesSpec("line", xs, ys, **kw))  # type: ignore[arg-type]
    return out


def area_series(items: list) -> list[SeriesSpec]:
    data, rest = _data_and_rest(list(items), "area")
    props = _props(rest, "area", _BAR_PROPS)
    x, y = _xy(data, "area")
    if y.shape[1] != 1:
        raise NotSupportedError("area: stacked areas (matrix input) are not supported yet.")
    color = _color(props.get("facecolor", props.get("color")), "area") if (
        "facecolor" in props or "color" in props) else None
    edge = _color(props["edgecolor"], "area") if "edgecolor" in props else None
    base = float(np.asarray(props.get("basevalue", 0.0), dtype=float).reshape(-1)[0])
    kw: dict[str, object] = {"color": color, "edge_color": edge, "base_value": base}
    if "linewidth" in props:
        kw["line_width"] = _positive(props["linewidth"], "area", "LineWidth")
    if "displayname" in props:
        kw["label"] = props["displayname"]
    return [SeriesSpec("area", x, y[:, 0], **kw)]  # type: ignore[arg-type]


def scatter_series(items: list) -> list[SeriesSpec]:
    items = list(items)
    data, rest = _data_and_rest(items, "scatter", 4)
    if len(data) < 2:
        raise ValidationError("scatter: use scatter(x, y).")
    x, y = _flat(data[0]), _flat(data[1])
    if x.size != y.size:
        raise ValidationError("scatter: x and y must have the same length.")
    size = 36.0
    color = None
    if len(data) >= 3 and data[2].size:
        if data[2].size != 1:
            raise NotSupportedError("scatter: per-point marker sizes are not supported yet.")
        size = _positive(data[2], "scatter", "the marker size")
    if len(data) >= 4 and data[3].size:
        if data[3].size != 3:
            raise NotSupportedError("scatter: per-point colours are not supported yet.")
        color = parse_color(data[3], "scatter")
    marker = "o"
    while rest and _is_word(rest[0]) and rest[0].lower() not in _COMMON | {
            "marker", "markerfacecolor", "markeredgecolor", "sizedata"}:
        word = rest.pop(0)
        if word.lower() == "filled":
            continue
        c, _s, m = parse_linespec(word, "scatter")
        color = c or color
        marker = m or marker
    props = _props(rest, "scatter", _COMMON | {"marker", "markerfacecolor", "markeredgecolor",
                                               "sizedata"})
    for key in ("markerfacecolor", "color", "markeredgecolor"):
        if key in props and not (_is_word(props[key]) and props[key].lower() in (
                "flat", "auto", "none")):
            color = parse_color(props[key], "scatter")
            break
    if "marker" in props:
        marker = parse_linespec(str(props["marker"]), "scatter")[2] or marker
    if "sizedata" in props:
        size = _positive(props["sizedata"], "scatter", "SizeData")
    label = props.get("displayname", "")
    return [SeriesSpec("scatter", x, y, marker=marker, marker_size=float(np.sqrt(size)),
                       color=color, label=label if isinstance(label, str) else "")]


_HIST_PROPS = {"facecolor", "edgecolor", "displayname", "normalization", "binedges",
               "numbins", "binwidth", "facealpha", "linewidth", "binlimits", "displaystyle"}


def _edges(data: np.ndarray, spec: object, props: dict, who: str) -> np.ndarray:
    finite = data[np.isfinite(data)]
    if "binedges" in props:
        spec = props["binedges"]
    if isinstance(spec, np.ndarray) and spec.size > 1:
        edges = np.asarray(spec, dtype=float).reshape(-1)
        if np.any(np.diff(edges) <= 0):
            raise ValidationError(f"{who}: bin edges must be increasing.")
        return edges
    lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)
    if "binlimits" in props:
        lo, hi = (float(v) for v in np.asarray(props["binlimits"], dtype=float).reshape(-1)[:2])
    if "binwidth" in props:
        w = _positive(props["binwidth"], who, "BinWidth")
        start = np.floor(lo / w) * w
        n = max(1, int(np.ceil((hi - start) / w)))
        if start + n * w <= hi:
            n += 1
        return start + w * np.arange(n + 1)
    nbins = None
    if isinstance(spec, np.ndarray) and spec.size == 1:
        nbins = int(spec.reshape(-1)[0])
    if "numbins" in props:
        nbins = int(np.asarray(props["numbins"], dtype=float).reshape(-1)[0])
    if nbins is not None:
        if nbins < 1:
            raise ValidationError(f"{who}: the number of bins must be positive.")
        if lo == hi:
            lo, hi = lo - 0.5, hi + 0.5
        return np.linspace(lo, hi, nbins + 1)
    if finite.size == 0:
        return np.array([0.0, 1.0])
    return np.histogram_bin_edges(finite, bins="auto", range=(lo, hi) if lo < hi else None)


def histogram_counts(data: np.ndarray, edges: np.ndarray) -> np.ndarray:
    counts, _ = np.histogram(data[np.isfinite(data)], bins=edges)
    return counts.astype(float)


def _normalize(counts: np.ndarray, edges: np.ndarray, mode: str, who: str) -> np.ndarray:
    widths = np.diff(edges)
    total = counts.sum()
    if mode == "count":
        return counts
    if mode == "probability":
        return counts / total if total else counts
    if mode == "pdf":
        return counts / (total * widths) if total else counts
    if mode == "countdensity":
        return counts / widths
    if mode == "cumcount":
        return np.cumsum(counts)
    if mode == "cdf":
        return np.cumsum(counts) / total if total else counts
    raise ValidationError(f"{who}: unknown Normalization {mode!r}.")


def histogram_series(items: list) -> tuple[list[SeriesSpec], np.ndarray, np.ndarray]:
    data, rest = _data_and_rest(list(items), "histogram")
    values = _flat(data[0])
    spec = data[1] if len(data) > 1 else None
    props = _props(rest, "histogram", _HIST_PROPS)
    edges = _edges(values, spec, props, "histogram")
    widths = np.diff(edges)
    if widths.size > 1 and not np.allclose(widths, widths[0], rtol=1e-9, atol=0):
        raise NotSupportedError("histogram: unevenly spaced bin edges are not supported yet.")
    mode = str(props.get("normalization", "count")).lower()
    heights = _normalize(histogram_counts(values, edges), edges, mode, "histogram")
    face = _color(props["facecolor"], "histogram") if "facecolor" in props else None
    edge = _color(props["edgecolor"], "histogram") if "edgecolor" in props else None
    label = props.get("displayname", "")
    centers = (edges[:-1] + edges[1:]) / 2
    series = SeriesSpec("bar", centers, heights, color=face, edge_color=edge,
                        bar_width=float(widths[0]), label=label if isinstance(label, str) else "")
    return [series], heights, edges


def plot2d_functions(manager: FigureManager, push: Push) -> dict[str, Builtin]:
    def py_args(args: list, who: str) -> list:
        return [to_py(a, who) for a in args]

    def draw(series: list[SeriesSpec], nargout: int, props: dict | None = None) -> list:
        handles = manager.add_lines(series, props)
        push(None)
        return _handles(handles) if nargout else []

    def bar(args: list, nargout: int) -> list:
        return draw(bar_series(py_args(args, "bar")), nargout)

    def stem(args: list, nargout: int) -> list:
        return draw(stem_series(py_args(args, "stem")), nargout)

    def stairs(args: list, nargout: int) -> list:
        return draw(stairs_series(py_args(args, "stairs")), nargout)

    def area(args: list, nargout: int) -> list:
        return draw(area_series(py_args(args, "area")), nargout)

    def scatter(args: list, nargout: int) -> list:
        return draw(scatter_series(py_args(args, "scatter")), nargout)

    def logplot(who: str, xs: bool, ys: bool) -> Builtin:
        def run(args: list, nargout: int) -> list:
            series = build_series(py_args(args, who))
            props = {"xscale": "log" if xs else "linear", "yscale": "log" if ys else "linear"}
            return draw(series, nargout, props)
        return run

    def histogram(args: list, nargout: int) -> list:
        series, _h, _e = histogram_series(py_args(args, "histogram"))
        return draw(series, nargout)

    def hist(args: list, nargout: int) -> list:
        _need("hist", args, 1, 2)
        values = _flat(to_py(args[0], "hist"))  # type: ignore[arg-type]
        if len(args) == 2:
            spec = to_py(args[1], "hist")
            if isinstance(spec, str):
                raise ValidationError("hist: the second argument must be numeric.")
            if spec.size > 1:  # bin centers
                c = _flat(spec)
                mids = (c[:-1] + c[1:]) / 2
                edges = np.concatenate(([-np.inf], mids, [np.inf]))
                counts, _ = np.histogram(values[np.isfinite(values)], bins=edges)
                centers = c
            else:
                n = _int(args[1], "hist")
                edges = _edges(values, np.array([[float(n)]]), {}, "hist")
                counts, centers = histogram_counts(values, edges), (edges[:-1] + edges[1:]) / 2
        else:
            edges = _edges(values, np.array([[10.0]]), {}, "hist")
            counts, centers = histogram_counts(values, edges), (edges[:-1] + edges[1:]) / 2
        counts = np.asarray(counts, dtype=float)
        if nargout:
            return [counts.reshape(1, -1), np.asarray(centers, dtype=float).reshape(1, -1)][
                :max(1, nargout)]
        width = _spacing(np.asarray(centers, dtype=float))
        manager.add_lines([SeriesSpec("bar", np.asarray(centers), counts, bar_width=width)])
        push(None)
        return []

    def histcounts(args: list, nargout: int) -> list:
        items = py_args(args, "histcounts")
        data, rest = _data_and_rest(items, "histcounts")
        values = _flat(data[0])
        props = _props(rest, "histcounts", _HIST_PROPS)
        edges = _edges(values, data[1] if len(data) > 1 else None, props, "histcounts")
        mode = str(props.get("normalization", "count")).lower()
        counts = _normalize(histogram_counts(values, edges), edges, mode, "histcounts")
        return [counts.reshape(1, -1), edges.reshape(1, -1)][:max(1, nargout)]

    return {
        "bar": bar, "stem": stem, "stairs": stairs, "area": area, "scatter": scatter,
        "semilogx": logplot("semilogx", True, False), "semilogy": logplot("semilogy", False, True),
        "loglog": logplot("loglog", True, True), "histogram": histogram, "hist": hist,
        "histcounts": histcounts,
    }
