"""3-D, gridded, polar and reference-line plots (P5.4): plot3, scatter3, surf, mesh, contour,
contourf, zlabel, zlim, view, colorbar, colormap, shading, polarplot, errorbar, xline, yline.

These axes are drawn with Matplotlib inside the figure window (design pick 1); errorbar,
xline and yline also work in ordinary 2-D axes.

Differences from MATLAB:
- ``surf``/``mesh`` colour by z with the axes colormap; per-vertex colour matrices (C) are not
  supported. ``shading interp`` is drawn like ``shading flat`` (no edges).
- ``contour``/``contourf`` accept a level count or level vector; ``[C, h] = contour(...)``
  returns ``C = []`` (the contour matrix is not built).
- ``colormap`` names: parula (shown with Matplotlib's similar 'viridis'), jet, hot, cool, gray,
  bone, copper, spring, summer, autumn, winter, turbo, hsv, viridis, pink, lines. Custom
  colormap matrices are not supported.
- ``view(az, el)`` uses MATLAB's azimuth convention; ``view(2)`` is a top view, ``view(3)``
  the default 3-D view (-37.5, 30).
- ``polarplot(theta, rho)`` draws lines in a polar axes; ``rlim``/``thetalim`` are not
  supported yet.
- ``xline``/``yline`` labels go to the legend (not drawn on the line).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _need, _scalar
from engstudio.lang.builtins_plotaxes import label_text, to_py
from engstudio.lang.figstate import FigureManager, build_series, parse_color, parse_linespec
from engstudio.lang.values import CharArray
from engstudio.plotting.model import COLORMAPS, SeriesSpec, SurfaceSpec

__all__ = ["plot3d_functions"]

Push = Callable[[int | None], None]


def _flat(a: np.ndarray) -> np.ndarray:
    return a.reshape(-1, order="F")


def _real(a: object, who: str) -> np.ndarray:
    if isinstance(a, str):
        raise ValidationError(f"{who}: expected numeric data, got text {a!r}.")
    arr = np.asarray(a)
    if arr.dtype.kind == "c":
        raise ValidationError(f"{who}: complex data is not supported.")
    return arr.astype(float)


def _props(rest: list, who: str, allowed: set[str]) -> dict[str, object]:
    if len(rest) % 2:
        raise ValidationError(f"{who}: property names and values must come in pairs.")
    out: dict[str, object] = {}
    for name, value in zip(rest[::2], rest[1::2], strict=True):
        if not isinstance(name, str) or name.lower() not in allowed:
            shown = name if isinstance(name, str) else "<number>"
            raise ValidationError(f"{who}: unrecognized property {shown!r}.")
        out[name.lower()] = value
    return out


def _positive(value: object, who: str, what: str) -> float:
    a = np.asarray(value, dtype=float).reshape(-1) if not isinstance(value, str) else None
    if a is None or a.size != 1 or not (np.isfinite(a[0]) and a[0] > 0):
        raise ValidationError(f"{who}: {what} must be a positive number.")
    return float(a[0])


def _edge(value: object, who: str) -> str | None:
    if isinstance(value, str) and value.lower() in ("none", "flat", "interp"):
        return "none" if value.lower() == "none" else None
    return parse_color(value, who)


# ------------------------------------------------------------------------ builders
def plot3_series(items: list, scatter: bool = False) -> list[SeriesSpec]:
    who = "scatter3" if scatter else "plot3"
    data = []
    while items and not isinstance(items[0], str):
        data.append(_real(items.pop(0), who))
    if len(data) < 3:
        raise ValidationError(f"{who}: use {who}(x, y, z).")
    x, y, z = data[:3]
    color, style, marker = None, None, None
    if scatter:
        size = 36.0
        if len(data) >= 4 and data[3].size:
            if data[3].size != 1:
                raise NotSupportedError("scatter3: per-point marker sizes are not supported.")
            size = _positive(data[3], who, "the marker size")
        if len(data) >= 5 and data[4].size:
            if data[4].size != 3:
                raise NotSupportedError("scatter3: per-point colours are not supported.")
            color = parse_color(data[4], who)
        while items and isinstance(items[0], str) and items[0].lower() not in (
                "markerfacecolor", "marker", "displayname", "color"):
            word = items.pop(0)
            if word.lower() != "filled":
                c, _s, m = parse_linespec(word, who)
                color, marker = c or color, m or marker
        props = _props(items, who, {"markerfacecolor", "marker", "displayname", "color"})
        for key in ("markerfacecolor", "color"):
            if key in props:
                color = parse_color(props[key], who)
        xs, ys, zs = _flat(x), _flat(y), _flat(z)
        if not xs.size == ys.size == zs.size:
            raise ValidationError(f"{who}: x, y and z must have the same number of points.")
        label = props.get("displayname", "")
        return [SeriesSpec("scatter", xs, ys, z=zs, marker=marker or "o",
                           marker_size=float(np.sqrt(size)), color=color,
                           label=label if isinstance(label, str) else "")]
    if items and isinstance(items[0], str):
        try:
            color, style, marker = parse_linespec(items[0], who)
            items = items[1:]
        except ValidationError:
            pass
    props = _props(items, who, {"color", "linewidth", "linestyle", "marker", "markersize",
                                "displayname"})
    kw: dict[str, object] = {"line_style": style or "-", "marker": marker, "color": color}
    if "color" in props:
        kw["color"] = parse_color(props["color"], who)
    if "linewidth" in props:
        kw["line_width"] = _positive(props["linewidth"], who, "LineWidth")
    if "markersize" in props:
        kw["marker_size"] = _positive(props["markersize"], who, "MarkerSize")
    if "linestyle" in props:
        kw["line_style"] = props["linestyle"]
    if "marker" in props:
        kw["marker"] = parse_linespec(str(props["marker"]), who)[2]
    if "displayname" in props:
        kw["label"] = props["displayname"]
    vec = all(1 in a.shape or a.ndim < 2 for a in (x, y, z))
    if vec:
        cols = [(_flat(x), _flat(y), _flat(z))]
    else:
        if not x.shape == y.shape == z.shape:
            raise ValidationError(f"{who}: x, y and z matrices must have the same size.")
        cols = [(x[:, j], y[:, j], z[:, j]) for j in range(x.shape[1])]
    out = []
    for xs, ys, zs in cols:
        if not xs.size == ys.size == zs.size:
            raise ValidationError(f"{who}: x, y and z must have the same number of points.")
        out.append(SeriesSpec("line", xs, ys, z=zs, **kw))  # type: ignore[arg-type]
    return out


_SURF_PROPS = {"edgecolor", "facecolor", "facealpha", "linewidth", "displayname", "linestyle",
               "showtext", "levellist", "linecolor", "levelstep", "fill"}


def grid_spec(kind: str, items: list, who: str) -> SurfaceSpec:
    data = []
    while items and not isinstance(items[0], str):
        data.append(_real(items.pop(0), who))
    levels: int | tuple[float, ...] | None = None
    if kind in ("contour", "contourf") and len(data) in (2, 4):
        lv = data.pop()
        levels = int(lv.reshape(-1)[0]) if lv.size == 1 else tuple(float(v) for v in _flat(lv))
    if len(data) == 1:
        z = data[0]
        x, y = np.arange(1.0, z.shape[1] + 1), np.arange(1.0, z.shape[0] + 1)
    elif len(data) == 3:
        x, y, z = data
    elif len(data) == 4:
        raise NotSupportedError(f"{who}: a colour matrix C is not supported yet.")
    else:
        raise ValidationError(f"{who}: use {who}(Z) or {who}(X, Y, Z).")
    face = None
    color = None
    if items and isinstance(items[0], str) and items[0].lower() not in _SURF_PROPS:
        color = parse_linespec(items.pop(0), who)[0]
    props = _props(items, who, _SURF_PROPS)
    edge = _edge(props["edgecolor"], who) if "edgecolor" in props else None
    if "linecolor" in props:
        edge = _edge(props["linecolor"], who)
    if color is not None:
        edge = color
    if "facecolor" in props:
        fc = props["facecolor"]
        face = None if isinstance(fc, str) and fc.lower() in ("flat", "interp") else (
            parse_color(fc, who))
    if "levellist" in props:
        levels = tuple(float(v) for v in _flat(_real(props["levellist"], who)))
    alpha = float(np.asarray(props.get("facealpha", 1.0), dtype=float).reshape(-1)[0])
    width = _positive(props["linewidth"], who, "LineWidth") if "linewidth" in props else 0.5
    show = props.get("showtext", "off")
    show_text = isinstance(show, str) and show.lower() == "on"

    try:
        return SurfaceSpec(kind, x, y, z, levels=levels, edge_color=edge, face_color=face,
                           line_width=width, alpha=alpha, show_text=show_text)
    except ValidationError as exc:
        raise ValidationError(f"{who}: {exc}") from None


def plot3d_functions(manager: FigureManager, push: Push) -> dict[str, Builtin]:
    def py(args: list, who: str) -> list:
        return [to_py(a, who) for a in args]

    def draw(series: list, nargout: int, props: dict, surfaces: list | None = None) -> list:
        handles = manager.add_lines(series, props, surfaces)
        push(None)
        return [np.array([[float(h)] for h in handles])] if nargout else []

    def plot3(args: list, nargout: int) -> list:
        return draw(plot3_series(py(args, "plot3")), nargout, {"projection": "3d", "grid": True})

    def scatter3(args: list, nargout: int) -> list:
        return draw(plot3_series(py(args, "scatter3"), scatter=True), nargout,
                    {"projection": "3d", "grid": True})

    def gridded(kind: str, who: str, three_d: bool) -> Builtin:
        def run(args: list, nargout: int) -> list:
            spec = grid_spec(kind, py(args, who), who)
            props = {"projection": "3d"} if three_d else {}
            out = draw([], nargout, props, [spec])
            if kind in ("contour", "contourf") and nargout:
                return [np.zeros((0, 0)), *out][:nargout]
            return out
        return run

    def zlabel(args: list, nargout: int) -> list:
        _need("zlabel", args, 1, 99)
        manager.set_axes(None, zlabel=label_text(args[0], "zlabel"))
        push(None)
        return []

    def zlim(args: list, nargout: int) -> list:
        _need("zlim", args, 0, 1)
        if not args:
            lim = manager.axes_props().get("zlim")
            return [np.array([list(lim)]) if lim else np.array([[0.0, 1.0]])]
        if isinstance(args[0], CharArray):
            if args[0].to_str().lower() != "auto":
                raise ValidationError("zlim: use zlim([zmin zmax]) or zlim auto.")
            manager.set_axes(None, zlim=None)
        else:
            a = _flat(_real(to_py(args[0], "zlim"), "zlim"))
            if a.size != 2 or not a[0] < a[1]:
                raise ValidationError("zlim: limits must be increasing [zmin zmax].")
            manager.set_axes(None, zlim=(float(a[0]), float(a[1])))
        push(None)
        return []

    def view(args: list, nargout: int) -> list:
        _need("view", args, 0, 2)
        if not args:
            v = manager.axes_props().get("view") or (-37.5, 30.0)
            return [np.array([list(v)])]
        vals = [_flat(_real(to_py(a, "view"), "view")) for a in args]
        flat = np.concatenate(vals)
        if flat.size == 1 and flat[0] in (2, 3):
            v = (0.0, 90.0) if flat[0] == 2 else (-37.5, 30.0)
        elif flat.size == 2:
            v = (float(flat[0]), float(flat[1]))
        else:
            raise ValidationError("view: use view(az, el), view(2) or view(3).")
        manager.set_axes(None, view=v)
        if manager.axes_props().get("projection", "2d") == "2d" and v != (0.0, 90.0):
            manager.set_axes(None, projection="3d")
        push(None)
        return []

    def colormap(args: list, nargout: int) -> list:
        _need("colormap", args, 0, 2)
        names = [a for a in args if isinstance(a, CharArray)]
        if not names:
            if args:
                raise NotSupportedError("colormap: custom colormap matrices are not supported.")
            return [CharArray.from_str(str(manager.axes_props().get("colormap", "parula")))]
        name = names[-1].to_str().lower()
        if name == "default":
            name = "parula"
        if name not in COLORMAPS:
            raise ValidationError(f"colormap: unknown colormap {name!r}.")
        manager.set_axes(None, colormap=name)
        push(None)
        return []

    def colorbar(args: list, nargout: int) -> list:
        on = not (args and isinstance(args[0], CharArray) and args[0].to_str().lower() == "off")
        manager.set_axes(None, colorbar=on)
        push(None)
        return [_scalar(float(manager.gca()))] if nargout else []

    def shading(args: list, nargout: int) -> list:
        _need("shading", args, 1)
        mode = args[0].to_str().lower() if isinstance(args[0], CharArray) else ""
        if mode not in ("flat", "interp", "faceted"):
            raise ValidationError("shading: use shading flat, interp or faceted.")
        edge = None if mode == "faceted" else "none"
        if manager.update_surfaces(
                lambda s: replace(s, edge_color=edge) if s.kind == "surface" else s):
            push(None)
        return []

    def polarplot(args: list, nargout: int) -> list:
        series = build_series(py(args, "polarplot"))
        return draw(series, nargout, {"projection": "polar"})

    def errorbar(args: list, nargout: int) -> list:
        items = py(args, "errorbar")
        data = []
        while items and not isinstance(items[0], str):
            data.append(_flat(_real(items.pop(0), "errorbar")))
        if len(data) == 2:
            y, err = data
            x, lo, hi = np.arange(1.0, y.size + 1), err, err
        elif len(data) == 3:
            x, y, err = data
            lo = hi = err
        elif len(data) == 4:
            x, y, lo, hi = data
        else:
            raise ValidationError(
                "errorbar: use errorbar(x, y, err) or errorbar(x, y, neg, pos).")
        color = style = marker = None
        if items and isinstance(items[0], str):
            try:
                color, style, marker = parse_linespec(items[0], "errorbar")
                items = items[1:]
            except ValidationError:
                pass
        props = _props(items, "errorbar", {"color", "linewidth", "displayname", "marker",
                                           "markersize", "linestyle", "capsize"})
        kw: dict[str, object] = {"color": parse_color(props["color"], "errorbar")
                                 if "color" in props else color,
                                 "line_style": style or "-", "marker": marker}
        if "linewidth" in props:
            kw["line_width"] = _positive(props["linewidth"], "errorbar", "LineWidth")
        if "displayname" in props:
            kw["label"] = props["displayname"]
        if "marker" in props:
            kw["marker"] = parse_linespec(str(props["marker"]), "errorbar")[2]
        try:
            series = SeriesSpec("errorbar", x, y, err_low=np.abs(lo), err_high=np.abs(hi),
                                **kw)  # type: ignore[arg-type]
        except ValidationError as exc:
            raise ValidationError(f"errorbar: {exc}") from None
        return draw([series], nargout, {})

    def refline(kind: str) -> Builtin:
        def run(args: list, nargout: int) -> list:
            items = py(args, kind)
            if not items or isinstance(items[0], str):
                raise ValidationError(f"{kind}: use {kind}(value).")
            values = _flat(_real(items.pop(0), kind))
            color = style = None
            if items and isinstance(items[0], str) and items[0].lower() not in (
                    "color", "linewidth", "linestyle", "displayname", "label"):
                color, style, _m = parse_linespec(items.pop(0), kind)
            label = ""
            if items and isinstance(items[0], str) and len(items) % 2 == 1:
                label = items.pop(0)  # xline(x, '--', 'label')
            props = _props(items, kind, {"color", "linewidth", "linestyle", "displayname",
                                         "label", "labelorientation", "labelhorizontalalignment",
                                         "labelverticalalignment", "alpha"})
            kw: dict[str, object] = {"color": color or "#262626", "line_style": style or "-",
                                     "label": label}
            if "color" in props:
                kw["color"] = parse_color(props["color"], kind)
            if "linewidth" in props:
                kw["line_width"] = _positive(props["linewidth"], kind, "LineWidth")
            if "linestyle" in props:
                kw["line_style"] = props["linestyle"]
            for key in ("displayname", "label"):
                if key in props:
                    kw["label"] = props[key]
            series = SeriesSpec(kind, values, np.full(values.size, np.nan),
                                **kw)  # type: ignore[arg-type]
            handles = manager.add_overlay([series])  # reference lines never clear the axes
            push(None)
            return [_scalar(float(handles[0]))] if nargout else []
        return run

    return {
        "plot3": plot3, "scatter3": scatter3,
        "surf": gridded("surface", "surf", True), "mesh": gridded("mesh", "mesh", True),
        "contour": gridded("contour", "contour", False),
        "contourf": gridded("contourf", "contourf", False),
        "zlabel": zlabel, "zlim": zlim, "view": view, "colormap": colormap,
        "colorbar": colorbar, "shading": shading, "polarplot": polarplot,
        "errorbar": errorbar, "xline": refline("xline"), "yline": refline("yline"),
    }
