"""Axes and annotation commands (P5.2): subplot, axes, title, xlabel, ylabel, sgtitle, grid,
box, legend, xlim, ylim, axis, xticks, yticks, xticklabels, yticklabels, text, set, get.

Used through ``lang.builtins_plot.install_plot``; every command that changes a figure
publishes a new snapshot of it.

Differences from MATLAB:
- Text objects are not returned by title/xlabel/ylabel (they return nothing); ``get(ax,
  'Title')`` gives the title text.
- Font, colour and layout properties (FontSize, FontWeight, LineWidth of axes, Box, TickDir,
  Position, ...) are accepted and ignored. ``axis off``/``axis on`` and ``box`` are no-ops.
- One text interpreter per axes: 'Interpreter','none' on any of its labels applies to all;
  'latex' is treated as the TeX subset.
- ``legend`` labels series in drawing order; 'Location' is accepted and ignored.
- ``xticklabels`` without ``xticks`` places the labels at 1, 2, 3, ...
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _arith, _int, _need, _scalar
from engstudio.lang.figstate import MAX_FIGURE, FigureManager, parse_color, parse_linespec
from engstudio.lang.values import CellArray, CharArray, class_of
from engstudio.plotting.model import LINE_STYLES, SeriesSpec, TextSpec

__all__ = ["axes_functions", "label_text", "to_py"]

Push = Callable[[int | None], None]

_IGNORED_TEXT_PROPS = {"fontsize", "fontweight", "fontname", "fontangle", "color",
                       "horizontalalignment", "verticalalignment", "rotation", "units",
                       "position", "backgroundcolor", "edgecolor", "margin"}
_IGNORED_AXES_PROPS = {"fontsize", "fontname", "fontweight", "linewidth", "box", "tickdir",
                       "ticklength", "color", "xcolor", "ycolor", "zcolor", "layer", "gridalpha",
                       "gridlinestyle", "gridcolor", "xminortick", "yminortick", "xminorgrid",
                       "yminorgrid", "position", "units", "outerposition", "innerposition",
                       "xaxislocation", "yaxislocation", "ticklabelinterpreter", "fontangle",
                       "labelfontsizemultiplier", "titlefontsizemultiplier", "plotboxaspectratio",
                       "xdir", "visible", "clipping", "colororder", "linestyleorder",
                       "titlefontweight", "minorgridalpha", "xticklabelrotation",
                       "yticklabelrotation", "tag"}
_IGNORED_LINE_PROPS = {"markerfacecolor", "markeredgecolor", "tag", "visible", "clipping",
                       "linejoin", "facealpha", "edgealpha", "showbaseline", "basevalue"}


# ----------------------------------------------------------------------- value helpers
def to_py(v: object, who: str) -> object:
    """Interpreter value -> ``str`` (character vector) or 2-D float/complex array."""
    if isinstance(v, CharArray):
        return label_text(v, who)
    if isinstance(v, np.ndarray):
        a = _arith(v, who)
        return a if a.dtype.kind == "c" else a.astype(np.float64, copy=False)
    raise ValidationError(f"{who}: unsupported argument of class {class_of(v)}.")


def label_text(v: object, who: str) -> str:
    """Text for a label: char row, char matrix or cell array of rows (joined with newlines);
    numbers are formatted with %g."""
    if isinstance(v, CharArray):
        rows = ["".join(r) for r in v.data]
        return "\n".join(r.rstrip() for r in rows) if len(rows) > 1 else (rows[0] if rows else "")
    if isinstance(v, CellArray):
        return "\n".join(label_text(x, who) for x in v.data.ravel(order="F"))
    if isinstance(v, np.ndarray) and v.size <= 1 and v.dtype.kind in "fiub":
        return "" if v.size == 0 else f"{float(v.reshape(-1)[0]):g}"
    raise ValidationError(f"{who}: text must be a character vector or cell array, "
                          f"not {class_of(v)}.")


def _labels(v: object, who: str) -> tuple[str, ...]:
    """Tick labels: cell array of text, char matrix (one label per row) or numeric vector."""
    if isinstance(v, CellArray):
        return tuple(label_text(x, who) for x in v.data.ravel(order="F"))
    if isinstance(v, CharArray):
        return tuple("".join(r).rstrip() for r in v.data)
    if isinstance(v, np.ndarray):
        return tuple(f"{float(x):g}" for x in _arith(v, who).reshape(-1, order="F"))
    raise ValidationError(f"{who}: labels must be a cell array of text.")


def _word(v: object, who: str) -> str | None:
    if isinstance(v, CharArray) and v.data.shape[0] <= 1:
        return v.to_str()
    return None


def _vec(v: object, who: str) -> np.ndarray:
    a = _arith(v, who)
    if a.dtype.kind == "c":
        raise ValidationError(f"{who}: values must be real.")
    return a.astype(float).reshape(-1, order="F")


def _onoff(v: object, who: str) -> bool:
    w = _word(v, who)
    if w is not None and w.lower() in ("on", "off"):
        return w.lower() == "on"
    if isinstance(v, np.ndarray) and v.size == 1:
        return bool(v.reshape(-1)[0])
    raise ValidationError(f"{who}: expected 'on' or 'off'.")


def _pairs(rest: list, who: str) -> list[tuple[str, object]]:
    if len(rest) % 2:
        raise ValidationError(f"{who}: property names and values must come in pairs.")
    out = []
    for name, value in zip(rest[::2], rest[1::2], strict=True):
        key = _word(name, who)
        if key is None:
            raise ValidationError(f"{who}: property names must be text.")
        out.append((key, value))
    return out


def _limits(v: object, who: str) -> tuple[float, float]:
    a = _vec(v, who)
    if a.size != 2:
        raise ValidationError(f"{who}: limits must be a two-element vector [min max].")
    lo, hi = float(a[0]), float(a[1])
    if np.isnan(lo) or np.isnan(hi) or not lo < hi:
        raise ValidationError(f"{who}: limits must be increasing ([min max] with min < max).")
    return lo, hi


def _rgb(hex_color: str | None) -> np.ndarray:
    if hex_color is None:
        return np.zeros((1, 3))
    return np.array([[int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]])


# ------------------------------------------------------------------------- data limits
def data_limits(series: list[SeriesSpec]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Tight (x, y) limits of the data, as ``axis tight`` uses them; (0, 1) when empty."""
    xs, ys = [], []
    for s in series:
        ok = np.isfinite(s.x) & np.isfinite(s.y)
        if not ok.any():
            continue
        x, y = s.x[ok], s.y[ok]
        if s.kind == "bar":
            half = (s.bar_width or 0.8) / 2
            xs += [x.min() - half, x.max() + half]
            ys.append(s.base_value)
        elif s.kind in ("stem", "area"):
            ys.append(s.base_value)
        xs += [x.min(), x.max()]
        ys += [y.min(), y.max()]

    def span(v: list[float]) -> tuple[float, float]:
        if not v:
            return (0.0, 1.0)
        lo, hi = float(min(v)), float(max(v))
        if lo == hi:
            lo, hi = lo - 0.5, hi + 0.5
        return lo, hi

    return span(xs), span(ys)


# --------------------------------------------------------------------------- commands
def axes_functions(manager: FigureManager, push: Push) -> dict[str, Builtin]:
    def axes_target(args: list) -> tuple[int | None, list]:
        """Strip a leading axes handle argument: (handle or None, remaining args)."""
        if args and isinstance(args[0], np.ndarray) and args[0].size == 1:
            h = float(args[0].reshape(-1)[0])
            if h == int(h) and manager.is_axes(int(h)):
                return int(h), list(args[1:])
        return None, list(args)

    def publish_axes(handle: int | None) -> None:
        push(manager.figure_of(handle) if handle is not None else None)

    # -- subplot / axes ----------------------------------------------------------
    def subplot(args: list, nargout: int) -> list:
        _need("subplot", args, 1, 3)
        if len(args) == 1:
            code = _int(args[0], "subplot")
            if not 111 <= code <= 999:
                raise ValidationError("subplot: use subplot(m, n, p) or a three-digit mnp.")
            m, n, p = code // 100, (code // 10) % 10, code % 10
            positions = [p]
        elif len(args) == 3:
            m, n = _int(args[0], "subplot"), _int(args[1], "subplot")
            pv = _vec(args[2], "subplot")
            if pv.size == 0 or np.any(pv != np.round(pv)):
                raise ValidationError("subplot: position must be integers.")
            positions = [int(p) for p in pv]
        else:
            raise ValidationError("subplot: use subplot(m, n, p).")
        h = manager.subplot(m, n, positions)
        push(None)
        return [_scalar(float(h))] if nargout else []

    def axes_cmd(args: list, nargout: int) -> list:
        _need("axes", args, 0, 1)
        if not args:
            h = manager.gca()
        else:
            h = _int(args[0], "axes")
            manager.select_axes(h)
        push(None)
        return [_scalar(float(h))] if nargout else []

    # -- labels ------------------------------------------------------------------
    def text_and_props(args: list, who: str) -> tuple[int | None, str, str | None]:
        ax, rest = axes_target(args)
        if not rest:
            raise ValidationError(f"{who}: Not enough input arguments.")
        text = label_text(rest[0], who)
        interpreter = None
        for key, value in _pairs(rest[1:], who):
            low = key.lower()
            if low == "interpreter":
                mode = (_word(value, who) or "").lower()
                if mode not in ("none", "tex", "latex"):
                    raise ValidationError(f"{who}: Interpreter must be 'tex', 'latex' or 'none'.")
                interpreter = "none" if mode == "none" else "tex"
            elif low not in _IGNORED_TEXT_PROPS:
                raise ValidationError(f"{who}: unrecognized property {key!r}.")
        return ax, text, interpreter

    def labeler(field: str) -> Builtin:
        def run(args: list, nargout: int) -> list:
            ax, text, interpreter = text_and_props(args, field)
            changes: dict[str, object] = {field: text}
            if interpreter is not None:
                changes["interpreter"] = interpreter
            manager.set_axes(ax, **changes)
            publish_axes(ax)
            return []
        return run

    def sgtitle(args: list, nargout: int) -> list:
        _need("sgtitle", args, 1, 99)
        text = label_text(args[0], "sgtitle")
        for key, _ in _pairs(list(args[1:]), "sgtitle"):
            if key.lower() not in _IGNORED_TEXT_PROPS | {"interpreter"}:
                raise ValidationError(f"sgtitle: unrecognized property {key!r}.")
        push(manager.set_title(text))
        return []

    # -- grid / box / legend ----------------------------------------------------
    def grid(args: list, nargout: int) -> list:
        ax, rest = axes_target(args)
        if len(rest) > 1:
            raise ValidationError("grid: Too many input arguments.")
        if rest:
            mode = (_word(rest[0], "grid") or "").lower()
            if mode not in ("on", "off", "minor"):
                raise ValidationError("grid: use grid on, grid off or grid minor.")
            state = mode != "off"
        else:
            state = not bool(manager.axes_props(ax).get("grid", False))
        manager.set_axes(ax, grid=state)
        publish_axes(ax)
        return []

    def box(args: list, nargout: int) -> list:
        _need("box", args, 0, 2)
        return []

    def legend(args: list, nargout: int) -> list:
        ax, rest = axes_target(args)
        labels: list[str] | None = None
        show = True
        i = 0
        if rest and isinstance(rest[0], CellArray):
            labels = [label_text(x, "legend") for x in rest[0].data.ravel(order="F")]
            i = 1
        else:
            words = []
            while i < len(rest):
                w = _word(rest[i], "legend")
                if w is None or w.lower() in ("location", "orientation", "interpreter",
                                               "fontsize", "box", "numcolumns", "autoupdate",
                                               "textcolor", "color", "edgecolor"):
                    break
                words.append(w)
                i += 1
            if len(words) == 1 and words[0].lower() in ("off", "hide", "show", "toggle",
                                                         "boxoff", "boxon"):
                cmd = words[0].lower()
                if cmd in ("off", "hide"):
                    show = False
                elif cmd == "toggle":
                    show = not bool(manager.axes_props(ax).get("legend", False))
                words = []
            if words:
                labels = words
        if i < len(rest) and isinstance(rest[i], np.ndarray):
            raise NotSupportedError("legend: legend(handles, ...) is not supported yet.")
        _pairs(rest[i:], "legend")  # Location, Orientation, ...: checked, then ignored
        if show:
            series = manager.axes_series(ax)
            if labels is None:
                fill = [None if s.label else f"data{k + 1}" for k, s in enumerate(series)]
                manager.relabel(fill, ax)
            else:
                if len(labels) > len(series):
                    labels = labels[:len(series)]  # MATLAB warns about the extra entries
                manager.relabel(list(labels), ax)
        manager.set_axes(ax, legend=show)
        publish_axes(ax)
        return []

    # -- limits / axis -------------------------------------------------------------
    def current_limits(ax: int | None, which: str) -> tuple[float, float]:
        lim = manager.axes_props(ax).get(f"{which}lim")
        if lim is not None:
            return lim  # type: ignore[return-value]
        xl, yl = data_limits(manager.axes_series(ax))
        return xl if which == "x" else yl

    def limiter(which: str) -> Builtin:
        who = f"{which}lim"

        def run(args: list, nargout: int) -> list:
            ax, rest = axes_target(args)
            if len(rest) > 1:
                raise ValidationError(f"{who}: Too many input arguments.")
            if not rest:
                lo, hi = current_limits(ax, which)
                return [np.array([[lo, hi]])]
            w = _word(rest[0], who)
            if w is not None:
                if w.lower() not in ("auto", "manual", "tight", "mode"):
                    raise ValidationError(f"{who}: unknown option {w!r}.")
                if w.lower() == "mode":
                    return [CharArray.from_str("manual" if manager.axes_props(ax).get(who)
                                               else "auto")]
                if w.lower() == "auto":
                    manager.set_axes(ax, **{who: None})
                elif w.lower() == "tight":
                    xl, yl = data_limits(manager.axes_series(ax))
                    manager.set_axes(ax, **{who: xl if which == "x" else yl})
                publish_axes(ax)
                return []
            a = _vec(rest[0], who)
            if a.size != 2:
                raise ValidationError(f"{who}: limits must be a two-element vector [min max].")
            if np.isinf(a).any():  # -inf / inf: keep the data limit on that side
                dl = data_limits(manager.axes_series(ax))[0 if which == "x" else 1]
                a = np.array([dl[0] if a[0] == -np.inf else a[0],
                              dl[1] if a[1] == np.inf else a[1]])
            manager.set_axes(ax, **{who: _limits(a.reshape(1, -1), who)})
            publish_axes(ax)
            return []
        return run

    def axis(args: list, nargout: int) -> list:
        ax, rest = axes_target(args)
        if not rest:
            xl, yl = current_limits(ax, "x"), current_limits(ax, "y")
            return [np.array([[xl[0], xl[1], yl[0], yl[1]]])]
        for arg in rest:
            w = _word(arg, "axis")
            if w is None:
                a = _vec(arg, "axis")
                if a.size not in (4, 6):
                    raise ValidationError("axis: limits must be [xmin xmax ymin ymax].")
                manager.set_axes(ax, xlim=_limits(a[0:2].reshape(1, 2), "axis"),
                                 ylim=_limits(a[2:4].reshape(1, 2), "axis"))
                continue
            low = w.lower()
            if low == "tight":
                xl, yl = data_limits(manager.axes_series(ax))
                manager.set_axes(ax, xlim=xl, ylim=yl)
            elif low in ("auto", "fill"):
                manager.set_axes(ax, xlim=None, ylim=None)
            elif low in ("equal", "image", "square", "vis3d"):
                manager.set_axes(ax, equal_aspect=True)
                if low == "image":
                    xl, yl = data_limits(manager.axes_series(ax))
                    manager.set_axes(ax, xlim=xl, ylim=yl)
            elif low == "normal":
                manager.set_axes(ax, equal_aspect=False)
            elif low in ("on", "off", "xy", "manual", "padded", "tickaligned"):
                pass
            elif low == "ij":
                raise NotSupportedError("axis ij (reversed y axis) is not supported yet.")
            else:
                raise ValidationError(f"axis: unknown option {w!r}.")
        publish_axes(ax)
        return []

    # -- ticks ---------------------------------------------------------------------
    def ticks(which: str) -> Builtin:
        who = f"{which}ticks"

        def run(args: list, nargout: int) -> list:
            ax, rest = axes_target(args)
            _need(who, rest, 0, 1)
            if not rest:
                t = manager.axes_props(ax).get(who)
                return [np.array([list(t)]) if t else np.zeros((1, 0))]
            w = _word(rest[0], who)
            if w is not None:
                if w.lower() not in ("auto", "manual"):
                    raise ValidationError(f"{who}: unknown option {w!r}.")
                if w.lower() == "auto":
                    manager.set_axes(ax, **{who: None})
            else:
                v = np.unique(_vec(rest[0], who))
                manager.set_axes(ax, **{who: tuple(float(x) for x in v)})
            publish_axes(ax)
            return []
        return run

    def ticklabels(which: str) -> Builtin:
        who = f"{which}ticklabels"

        def run(args: list, nargout: int) -> list:
            ax, rest = axes_target(args)
            _need(who, rest, 0, 1)
            props = manager.axes_props(ax)
            if not rest:
                labels = props.get(who) or ()
                data = np.empty((len(labels), 1), dtype=object)  # type: ignore[arg-type]
                for k, s in enumerate(labels):  # type: ignore[arg-type]
                    data[k, 0] = CharArray.from_str(s)
                return [CellArray(data)]
            w = _word(rest[0], who)
            if w is not None and w.lower() in ("auto", "manual"):
                if w.lower() == "auto":
                    manager.set_axes(ax, **{who: None})
            else:
                set_ticklabels(ax, which, _labels(rest[0], who))
            publish_axes(ax)
            return []
        return run

    def set_ticklabels(ax: int | None, which: str, labels: tuple[str, ...]) -> None:
        props = manager.axes_props(ax)
        if props.get(f"{which}ticks") is None and labels:
            manager.set_axes(ax, **{f"{which}ticks": tuple(
                float(k) for k in range(1, len(labels) + 1))})
        manager.set_axes(ax, **{f"{which}ticklabels": labels})

    # -- text ------------------------------------------------------------------------
    def text(args: list, nargout: int) -> list:
        ax, rest = axes_target(args)
        if len(rest) < 3:
            raise ValidationError("text: use text(x, y, txt).")
        x, y = _vec(rest[0], "text"), _vec(rest[1], "text")
        if x.size != 1 or y.size != 1:
            raise NotSupportedError("text: only one position per call is supported.")
        color = None
        for key, value in _pairs(rest[3:], "text"):
            low = key.lower()
            if low == "color":
                color = parse_color(to_py(value, "text"), "text")
            elif low == "interpreter":
                mode = (_word(value, "text") or "").lower()
                if mode == "none":
                    manager.set_axes(ax, interpreter="none")
            elif low not in _IGNORED_TEXT_PROPS:
                raise ValidationError(f"text: unrecognized property {key!r}.")
        if ax is not None:
            manager.select_axes(ax)
        h = manager.add_text(TextSpec(float(x[0]), float(y[0]), label_text(rest[2], "text"),
                                      color=color))
        publish_axes(ax)
        return [_scalar(float(h))] if nargout else []

    # -- set / get ---------------------------------------------------------------------
    def handles_of(v: object, who: str) -> list[int]:
        a = _vec(v, who)
        if a.size == 0:
            return []
        if np.any(a != np.round(a)):
            raise ValidationError(f"{who}: invalid graphics handle.")
        return [int(h) for h in a]

    def set_axes_prop(h: int, key: str, value: object) -> None:
        low = key.lower()
        if low in ("xlim", "ylim"):
            manager.set_axes(h, **{low: _limits(value, "set")})
        elif low in ("xscale", "yscale"):
            w = (_word(value, "set") or "").lower()
            if w not in ("linear", "log"):
                raise ValidationError(f"set: {key} must be 'linear' or 'log'.")
            manager.set_axes(h, **{low: w})
        elif low in ("xtick", "ytick"):
            manager.set_axes(h, **{low + "s": tuple(float(v) for v in
                                                   np.unique(_vec(value, "set")))})
        elif low in ("xticklabel", "yticklabel"):
            set_ticklabels(h, low[0], _labels(value, "set"))
        elif low in ("xgrid", "ygrid"):
            manager.set_axes(h, grid=_onoff(value, "set"))
        elif low in ("xlimmode", "ylimmode"):
            if (_word(value, "set") or "").lower() == "auto":
                manager.set_axes(h, **{low[:4]: None})
        elif low == "nextplot":
            w = (_word(value, "set") or "").lower()
            manager.select_axes(h)
            manager.hold("on" if w == "add" else "off")
        elif low == "dataaspectratio":
            a = _vec(value, "set")
            manager.set_axes(h, equal_aspect=bool(a.size >= 2 and a[0] == a[1]))
        elif low == "title":
            manager.set_axes(h, title=label_text(value, "set"))
        elif low in ("xlabel", "ylabel"):
            manager.set_axes(h, **{low: label_text(value, "set")})
        elif low not in _IGNORED_AXES_PROPS:
            raise ValidationError(f"set: unrecognized axes property {key!r}.")

    def set_line_prop(h: int, s: SeriesSpec, key: str, value: object) -> SeriesSpec:
        low = key.lower()
        if low in ("color", "facecolor"):
            w = _word(value, "set")
            if w is not None and w.lower() in ("flat", "auto", "none"):
                return s
            return replace(s, color=parse_color(to_py(value, "set"), "set"))
        if low == "edgecolor":
            w = _word(value, "set")
            if w is not None and w.lower() in ("flat", "auto", "none"):
                return replace(s, edge_color=None)
            return replace(s, edge_color=parse_color(to_py(value, "set"), "set"))
        if low == "linewidth":
            return replace(s, line_width=float(_vec(value, "set")[0]))
        if low == "markersize":
            return replace(s, marker_size=float(_vec(value, "set")[0]))
        if low == "linestyle":
            w = _word(value, "set")
            if w not in LINE_STYLES:
                raise ValidationError("set: LineStyle must be one of -, --, :, -.")
            return replace(s, line_style=w)
        if low == "marker":
            w = _word(value, "set") or ""
            if w == "none":
                return replace(s, marker=None)
            marker = parse_linespec(w, "set")[2] if len(w) == 1 else None
            if marker is None:
                raise ValidationError(f"set: Marker {w!r} is not supported.")
            return replace(s, marker=marker)
        if low == "displayname":
            return replace(s, label=label_text(value, "set"))
        if low == "xdata":
            return replace(s, x=_vec(value, "set"))
        if low == "ydata":
            return replace(s, y=_vec(value, "set"))
        if low == "barwidth":
            if s.kind != "bar":
                raise ValidationError("set: BarWidth applies to bar series only.")
            ratio = float(_vec(value, "set")[0])
            xs = np.unique(s.x[np.isfinite(s.x)])
            gap = float(np.min(np.diff(xs))) if xs.size > 1 else 1.0
            return replace(s, bar_width=ratio * gap)
        if low in _IGNORED_LINE_PROPS:
            return s
        raise ValidationError(f"set: unrecognized line property {key!r}.")

    def set_cmd(args: list, nargout: int) -> list:
        _need("set", args, 3, 999)
        pairs = _pairs(list(args[1:]), "set")
        touched: set[int] = set()
        for h in handles_of(args[0], "set"):
            if manager.is_figure(h):
                name, props = None, {}
                for key, value in pairs:
                    if key.lower() == "name":
                        name = label_text(value, "set")
                    else:
                        props[key] = value if not isinstance(value, np.ndarray) else value.copy()
                manager.update_figure(h, name, props)
                touched.add(h)
            elif manager.is_axes(h):
                for key, value in pairs:
                    set_axes_prop(h, key, value)
                touched.add(manager.figure_of(h))
            else:
                s = manager.line(h)
                if s is None:
                    if 1 <= h <= MAX_FIGURE:
                        raise ValidationError(f"set: figure {h} does not exist.")
                    raise ValidationError("set: invalid graphics handle.")
                for key, value in pairs:
                    s = set_line_prop(h, s, key, value)
                touched.add(manager.replace_line(h, s))
        for number in sorted(touched):
            push(number)
        return []

    def get_cmd(args: list, nargout: int) -> list:
        _need("get", args, 2)
        hs = handles_of(args[0], "get")
        if len(hs) != 1:
            raise NotSupportedError("get: one handle at a time is supported.")
        h = hs[0]
        key = _word(args[1], "get")
        if key is None:
            raise ValidationError("get: property name must be text.")
        low = key.lower()
        if manager.is_figure(h):
            if low == "number":
                return [_scalar(float(h))]
            if low == "name":
                return [CharArray.from_str(manager.figure_name(h))]
            props = {k.lower(): v for k, v in manager.props(h).items()}
            if low == "position":
                return [np.array([props.get("position", [100.0, 100.0, 720.0, 480.0])],
                                 dtype=float)]
            if low == "color":
                return [_rgb(props.get("color", "#ffffff"))]  # type: ignore[arg-type]
            raise NotSupportedError(f"get: figure property {key!r} is not supported.")
        if manager.is_axes(h):
            props = manager.axes_props(h)
            if low in ("xlim", "ylim"):
                lo, hi = current_limits(h, low[0])
                return [np.array([[lo, hi]])]
            if low in ("xscale", "yscale"):
                return [CharArray.from_str(str(props.get(low, "linear")))]
            if low in ("xtick", "ytick"):
                t = props.get(low + "s")
                return [np.array([list(t)]) if t else np.zeros((1, 0))]
            if low in ("title", "xlabel", "ylabel"):
                return [CharArray.from_str(str(props.get(low, "")))]
            if low in ("xgrid", "ygrid"):
                return [CharArray.from_str("on" if props.get("grid") else "off")]
            if low == "nextplot":
                manager.select_axes(h)
                return [CharArray.from_str("add" if manager.ishold() else "replace")]
            raise NotSupportedError(f"get: axes property {key!r} is not supported.")
        s = manager.line(h)
        if s is None:
            raise ValidationError("get: invalid graphics handle.")
        values = {
            "xdata": lambda: s.x.reshape(1, -1).copy(),
            "ydata": lambda: s.y.reshape(1, -1).copy(),
            "color": lambda: _rgb(s.color),
            "linewidth": lambda: _scalar(s.line_width),
            "linestyle": lambda: CharArray.from_str(s.line_style),
            "marker": lambda: CharArray.from_str(s.marker or "none"),
            "markersize": lambda: _scalar(s.marker_size),
            "displayname": lambda: CharArray.from_str(s.label),
            "type": lambda: CharArray.from_str(s.kind),
        }
        if low not in values:
            raise NotSupportedError(f"get: line property {key!r} is not supported.")
        return [values[low]()]

    return {
        "subplot": subplot, "axes": axes_cmd,
        "title": labeler("title"), "xlabel": labeler("xlabel"), "ylabel": labeler("ylabel"),
        "sgtitle": sgtitle, "grid": grid, "box": box, "legend": legend,
        "xlim": limiter("x"), "ylim": limiter("y"), "axis": axis,
        "xticks": ticks("x"), "yticks": ticks("y"),
        "xticklabels": ticklabels("x"), "yticklabels": ticklabels("y"),
        "text": text, "set": set_cmd, "get": get_cmd,
    }
