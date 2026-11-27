"""Export a ``FigureSpec`` to PNG, SVG or PDF with Matplotlib (Agg, no Qt, no pyplot).

Matplotlib is imported lazily inside the functions, so importing this module is cheap.
Defaults: where a series has no colour, Matplotlib's own colour cycle is used (not the GUI's).
Bar series are drawn on logarithmic axes too (the PyQtGraph renderer skips them there).
Files are written atomically: a failed export never leaves a partial file behind.
"""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from engstudio.core.errors import EngStudioError, ValidationError
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec, SurfaceSpec
from engstudio.plotting.text import tex_to_mathtext

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

__all__ = ["EXPORT_FORMATS", "MATPLOTLIB_LOCK", "build_figure", "cmap_name", "draw_figure",
           "export_figure", "load_matplotlib", "render_png", "write_gif"]

EXPORT_FORMATS: dict[str, str] = {
    "png": "PNG image",
    "svg": "SVG vector graphics",
    "pdf": "PDF document",
}
_MAX_DPI = 2400


def _bar_width(x: np.ndarray) -> float:
    """80% of the smallest gap between distinct finite x positions (0.8 if fewer than two)."""
    xs = np.unique(x[np.isfinite(x)])
    if xs.size < 2:
        return 0.8
    return float(0.8 * np.min(np.diff(xs)))


def _size(size_in: object) -> tuple[float, float]:
    try:
        w, h = (float(v) for v in size_in)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        raise ValidationError(f"size_in: expected (width, height) in inches, got {size_in!r}"
                              ) from None
    if not (math.isfinite(w) and math.isfinite(h) and 0.5 <= w <= 100 and 0.5 <= h <= 100):
        raise ValidationError(f"size_in: each side must be 0.5..100 inches, got {size_in!r}")
    return w, h


_MPL_MARKERS = {"o": "o", "s": "s", "^": "^", "v": "v", "<": "<", ">": ">", "x": "x", "+": "+",
                "*": "*", ".": ".", "d": "D", "p": "p", "h": "h"}


def _marker(m: str | None) -> str | None:
    return None if m is None else _MPL_MARKERS[m]


_CMAPS = {"parula": "viridis", "lines": "tab10"}  # MATLAB names without a Matplotlib twin


def cmap_name(name: str) -> str:
    return _CMAPS.get(name, name)


def _draw_series(ax: Axes, s: SeriesSpec, mode: str, three_d: bool) -> None:
    label = tex_to_mathtext(s.label, mode) if s.label else None
    if three_d:  # plot3 / scatter3 (other kinds have no 3-D form here)
        z = s.z if s.z is not None else np.zeros_like(s.x)
        if s.kind == "scatter":
            ax.scatter(s.x, s.y, z, marker=_marker(s.marker) or "o", s=s.marker_size ** 2,
                       color=s.color, label=label)
        else:
            ax.plot(s.x, s.y, z, linestyle=s.line_style, linewidth=s.line_width,
                    marker=_marker(s.marker), markersize=s.marker_size, color=s.color,
                    label=label)
        return
    if s.kind == "bar":
        width = s.bar_width if s.bar_width is not None else _bar_width(s.x)
        ax.bar(s.x, s.y - s.base_value, width=width, bottom=s.base_value, color=s.color,
               edgecolor=s.edge_color, label=label)
    elif s.kind == "scatter":
        ax.plot(s.x, s.y, linestyle="none", marker=_marker(s.marker) or "o",
                markersize=s.marker_size, color=s.color, label=label)
    elif s.kind == "stem":
        container = ax.stem(s.x, s.y, bottom=s.base_value, label=label)
        color = s.color or container.markerline.get_color()
        container.markerline.set(marker=_marker(s.marker) or "o", markersize=s.marker_size,
                                 color=color)
        container.stemlines.set(color=color, linewidth=s.line_width,
                                linestyle=s.line_style)
        container.baseline.set(visible=False)
    elif s.kind == "area":
        (line,) = ax.plot(s.x, s.y, color=s.edge_color or s.color, linewidth=s.line_width)
        ax.fill_between(s.x, s.y, s.base_value, color=s.color or line.get_color(), label=label)
    elif s.kind == "errorbar":
        ax.errorbar(s.x, s.y, yerr=np.vstack([s.err_low, s.err_high]),
                    linestyle=s.line_style, linewidth=s.line_width, marker=_marker(s.marker),
                    markersize=s.marker_size, color=s.color, capsize=3, label=label)
    elif s.kind in ("xline", "yline"):
        draw = ax.axvline if s.kind == "xline" else ax.axhline
        for k, v in enumerate(s.x):
            draw(float(v), linestyle=s.line_style, linewidth=s.line_width,
                 color=s.color or "#262626", label=label if k == 0 else None)
    else:
        ax.plot(s.x, s.y, linestyle=s.line_style, linewidth=s.line_width,
                marker=_marker(s.marker), markersize=s.marker_size, color=s.color, label=label)


def _draw_surface(ax: Axes, s: SurfaceSpec, a: AxesSpec):
    cmap = cmap_name(a.colormap)
    edge = None if s.edge_color == "none" else s.edge_color
    if s.kind in ("surface", "mesh"):
        if s.kind == "mesh":  # wireframe: one colour, nothing for a colorbar
            ax.plot_wireframe(s.x, s.y, s.z, color=s.face_color or edge or "#1f6fb4",
                              linewidth=s.line_width)
            return None
        kw: dict[str, object] = {"alpha": s.alpha, "linewidth": s.line_width,
                                 "edgecolor": edge if edge else (
                                     "none" if s.edge_color == "none" else "#00000040")}
        if s.face_color is not None:
            kw["color"] = s.face_color
        else:
            kw["cmap"] = cmap
        return ax.plot_surface(s.x, s.y, s.z, **kw)
    levels = list(s.levels) if isinstance(s.levels, tuple) else s.levels
    if s.kind == "contourf":
        cs = ax.contourf(s.x, s.y, s.z, levels=levels, cmap=cmap, alpha=s.alpha)
        if edge:
            ax.contour(s.x, s.y, s.z, levels=cs.levels, colors=edge, linewidths=s.line_width)
    else:
        kw = {"colors": s.face_color or edge} if (s.face_color or edge) else {"cmap": cmap}
        cs = ax.contour(s.x, s.y, s.z, levels=levels, linewidths=s.line_width, **kw)
    if s.show_text:
        ax.clabel(cs, inline=True, fontsize=8)
    return cs


def _draw_axes(ax: Axes, a: AxesSpec) -> None:
    mode = a.interpreter
    three_d = a.projection == "3d"
    if a.projection == "2d":
        ax.set_xscale(a.xscale)  # scales first: bars and limits depend on them
        ax.set_yscale(a.yscale)
    for s in a.series:
        _draw_series(ax, s, mode, three_d)
    mappable = None
    for surf in a.surfaces:
        mappable = _draw_surface(ax, surf, a) or mappable
    for t in a.texts:
        ax.text(t.x, t.y, tex_to_mathtext(t.text, mode), color=t.color, va="center")
    if a.title:
        ax.set_title(tex_to_mathtext(a.title, mode))
    if a.xlabel:
        ax.set_xlabel(tex_to_mathtext(a.xlabel, mode))
    if a.ylabel:
        ax.set_ylabel(tex_to_mathtext(a.ylabel, mode))
    if three_d:
        if a.zlabel:
            ax.set_zlabel(tex_to_mathtext(a.zlabel, mode))  # type: ignore[attr-defined]
        if a.zlim is not None:
            ax.set_zlim(*a.zlim)  # type: ignore[attr-defined]
        az, el = a.view if a.view is not None else (-37.5, 30.0)
        ax.view_init(elev=el, azim=az - 90)  # type: ignore[attr-defined]  # MATLAB azimuth
    for which in ("x", "y"):
        pairs = a.tick_pairs(which)
        if pairs is not None:
            setter = ax.set_xticks if which == "x" else ax.set_yticks
            setter([v for v, _ in pairs], [tex_to_mathtext(lbl, mode) for _, lbl in pairs])
    if a.grid or three_d:
        ax.grid(True, alpha=0.3)
    if a.xlim is not None:
        ax.set_xlim(*a.xlim)
    if a.ylim is not None:
        ax.set_ylim(*a.ylim)
    if a.equal_aspect and not three_d:
        ax.set_aspect("equal", adjustable="datalim")
    if a.colorbar and mappable is not None:
        ax.figure.colorbar(mappable, ax=ax)
    if a.legend and ax.get_legend_handles_labels()[0]:
        ax.legend()


def draw_figure(fig: Figure, spec: FigureSpec) -> None:
    """Draw ``spec`` onto an empty Matplotlib figure (export or the GUI's embedded canvas)."""
    if not isinstance(spec, FigureSpec):
        raise ValidationError(f"expected a FigureSpec, got {type(spec).__name__}")
    grid = fig.add_gridspec(spec.rows, spec.cols)
    for a, (r, c, rs, cs) in zip(spec.axes, spec.placements(), strict=True):
        projection = {"3d": "3d", "polar": "polar"}.get(a.projection)
        _draw_axes(fig.add_subplot(grid[r:r + rs, c:c + cs], projection=projection), a)
    if spec.title:
        fig.suptitle(tex_to_mathtext(spec.title))


MATPLOTLIB_LOCK = threading.RLock()  # first import of Matplotlib is not thread-safe


def load_matplotlib() -> None:
    """Import Matplotlib's core once, under a lock. The kernel thread (export) and the GUI
    thread (embedded canvas) may both need it first at the same moment."""
    with MATPLOTLIB_LOCK:
        import matplotlib.backends.backend_agg  # noqa: F401
        import matplotlib.figure  # noqa: F401


def build_figure(spec: FigureSpec, size_in: tuple[float, float] = (7.2, 4.8)) -> Figure:
    """The Matplotlib figure for ``spec`` (not tied to pyplot or any GUI backend)."""
    if not isinstance(spec, FigureSpec):
        raise ValidationError(f"expected a FigureSpec, got {type(spec).__name__}")
    load_matplotlib()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=_size(size_in), layout="constrained")
    FigureCanvasAgg(fig)
    draw_figure(fig, spec)
    return fig

def render_png(spec: FigureSpec, *, dpi: int = 100,
               size_in: tuple[float, float] = (7.2, 4.8)) -> bytes:
    """The figure as PNG bytes (one animation frame)."""
    import io

    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 1 <= dpi <= _MAX_DPI:
        raise ValidationError(f"dpi: expected an integer 1..{_MAX_DPI}, got {dpi!r}")
    buf = io.BytesIO()
    build_figure(spec, size_in).savefig(buf, format="png", dpi=dpi)
    return buf.getvalue()


def write_gif(path: Path | str, frames: list[bytes], delay_s: float = 0.1) -> Path:
    """Write PNG ``frames`` as a looping animated GIF (atomically). Frames of another size
    are resized to the first frame's size."""
    from PIL import Image

    if not frames:
        raise ValidationError("write_gif: no frames")
    if not (math.isfinite(delay_s) and 0 < delay_s <= 60):
        raise ValidationError(f"delay: must be in (0, 60] seconds, got {delay_s!r}")
    import io

    images = [Image.open(io.BytesIO(b)).convert("RGB") for b in frames]
    size = images[0].size
    images = [im if im.size == size else im.resize(size) for im in images]
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            images[0].save(f, format="GIF", save_all=True, append_images=images[1:],
                           duration=int(round(delay_s * 1000)), loop=0)
        os.replace(tmp, target)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise EngStudioError(f"cannot write {target}: {exc}") from None
    return target


def export_figure(
    spec: FigureSpec,
    path: Path | str,
    *,
    dpi: int = 150,
    size_in: tuple[float, float] = (7.2, 4.8),
) -> Path:
    """Write ``spec`` to ``path``; the format comes from the suffix (.png, .svg, .pdf)."""
    target = Path(path)
    fmt = target.suffix.lower().lstrip(".")
    if fmt not in EXPORT_FORMATS:
        shown = target.suffix or "a file name without extension"
        raise ValidationError(
            f"cannot export to {shown}; supported: "
            + ", ".join(f".{k}" for k in EXPORT_FORMATS))
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 1 <= dpi <= _MAX_DPI:
        raise ValidationError(f"dpi: expected an integer 1..{_MAX_DPI}, got {dpi!r}")
    fig = build_figure(spec, size_in)  # validates spec and size before touching the disk
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            fig.savefig(f, format=fmt, dpi=dpi)
        os.replace(tmp, target)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise EngStudioError(f"cannot write {target}: {exc}") from None
    return target
