"""Animation and figure files (P5.5): pause, animatedline, addpoints, clearpoints, saveas,
print, exportgraphics.

Animation (design pick 5A): figure updates are throttled by the kernel (about 30 per second
per figure); ``drawnow`` and every plot command request an update, ``pause(t)`` shows the
latest frame and then waits. Animated GIFs: ``exportgraphics(gcf, 'a.gif', 'Append', true)``
inside the loop adds one frame per call (MATLAB R2022a+ style).

Differences from MATLAB:
- ``pause`` without arguments (wait for a key press) and ``pause('on'/'off')`` are not
  supported; the longest pause is 3600 s. ``pause`` can be stopped with Stop.
- ``saveas``/``print``/``exportgraphics`` write PNG, SVG, PDF (and GIF for exportgraphics);
  relative file names are relative to the working folder of the application process.
  ``print`` takes '-dpng', '-dsvg', '-dpdf' and '-r<dpi>'; '-clipboard' and printers are not
  supported. The page size follows the figure (7.2 x 4.8 in), not MATLAB's paper settings.
- GIF frames are kept in memory until the file is complete; frame delay 0.1 s
  ('DelayTime' is not a MATLAB option of exportgraphics; it is accepted here).
- ``animatedline`` supports Color, LineWidth, LineStyle, Marker, MarkerSize, DisplayName and
  MaximumNumPoints.
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Protocol

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _need, _scalar
from engstudio.lang.builtins_plotaxes import label_text, to_py
from engstudio.lang.figstate import MAX_FIGURE, FigureManager, parse_color, parse_linespec
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray
from engstudio.plotting.export import EXPORT_FORMATS, export_figure, render_png, write_gif
from engstudio.plotting.model import SeriesSpec

__all__ = ["plotio_functions"]

_MAX_PAUSE = 3600.0
_GIF_DPI = 100


class _Publisher(Protocol):
    def push(self, number: int | None = None) -> None: ...
    def flush(self) -> None: ...


def _num(v: object, who: str) -> float:
    a = np.asarray(to_py(v, who), dtype=float).reshape(-1)
    if a.size != 1 or not np.isfinite(a[0]):
        raise ValidationError(f"{who}: expected a finite number.")
    return float(a[0])


def _word(v: object) -> str | None:
    return v.to_str() if isinstance(v, CharArray) and v.data.shape[0] <= 1 else None


def plotio_functions(interp: Interpreter, manager: FigureManager,
                     publisher: _Publisher) -> dict[str, Builtin]:
    gif_frames: dict[Path, list[bytes]] = {}
    animated: dict[int, int] = {}  # animatedline handle -> MaximumNumPoints

    def figure_number(v: object, who: str) -> int:
        h = _num(v, who)
        if h != int(h):
            raise ValidationError(f"{who}: invalid figure or axes handle.")
        h = int(h)
        if manager.is_figure(h):
            return h
        if h > MAX_FIGURE and manager.is_axes(h):
            raise NotSupportedError(f"{who}: exporting a single axes is not supported yet; "
                                    "pass the figure (gcf).")
        raise ValidationError(f"{who}: figure {h} does not exist.")

    # -- animation --------------------------------------------------------------
    def pause(args: list, nargout: int) -> list:
        _need("pause", args, 0, 1)
        if not args or _word(args[0]) is not None:
            raise NotSupportedError("pause: use pause(seconds); waiting for a key press and "
                                    "pause on/off are not supported.")
        seconds = _num(args[0], "pause")
        if seconds < 0:
            raise ValidationError("pause: the time must be non-negative.")
        publisher.flush()
        end = time.monotonic() + min(seconds, _MAX_PAUSE)
        while True:
            interp.check_cancel()
            left = end - time.monotonic()
            if left <= 0:
                break
            time.sleep(min(left, 0.05))
        return []

    def animatedline(args: list, nargout: int) -> list:
        items = [to_py(a, "animatedline") for a in args]
        xs = ys = np.empty(0)
        if items and not isinstance(items[0], str):
            if len(items) < 2 or isinstance(items[1], str):
                raise ValidationError("animatedline: use animatedline(x, y, ...).")
            xs = np.asarray(items.pop(0), dtype=float).reshape(-1)
            ys = np.asarray(items.pop(0), dtype=float).reshape(-1)
        if len(items) % 2:
            raise ValidationError("animatedline: properties must be name-value pairs.")
        kw: dict[str, object] = {}
        max_points = 1_000_000
        for name, value in zip(items[::2], items[1::2], strict=True):
            key = str(name).lower()
            if key == "color":
                kw["color"] = parse_color(value, "animatedline")
            elif key == "linewidth":
                kw["line_width"] = float(np.asarray(value, dtype=float).reshape(-1)[0])
            elif key == "linestyle":
                kw["line_style"] = value
            elif key == "marker":
                kw["marker"] = None if value == "none" else parse_linespec(
                    str(value), "animatedline")[2]
            elif key == "markersize":
                kw["marker_size"] = float(np.asarray(value, dtype=float).reshape(-1)[0])
            elif key == "displayname":
                kw["label"] = value
            elif key == "maximumnumpoints":
                max_points = int(np.asarray(value, dtype=float).reshape(-1)[0])
                if max_points < 1:
                    raise ValidationError("animatedline: MaximumNumPoints must be positive.")
            else:
                raise ValidationError(f"animatedline: unrecognized property {name!r}.")
        try:
            spec = SeriesSpec("line", xs, ys, **kw)  # type: ignore[arg-type]
        except ValidationError as exc:
            raise ValidationError(f"animatedline: {exc}") from None
        (h,) = manager.add_overlay([spec])
        animated[h] = max_points
        publisher.push(None)
        return [_scalar(float(h))]

    def line_handle(v: object, who: str) -> tuple[int, SeriesSpec]:
        h = _num(v, who)
        s = manager.line(int(h)) if h == int(h) else None
        if s is None or int(h) not in animated:
            raise ValidationError(f"{who}: the first argument must be an animatedline.")
        return int(h), s

    def addpoints(args: list, nargout: int) -> list:
        _need("addpoints", args, 3)
        h, s = line_handle(args[0], "addpoints")
        x = np.asarray(to_py(args[1], "addpoints"), dtype=float).reshape(-1)
        y = np.asarray(to_py(args[2], "addpoints"), dtype=float).reshape(-1)
        if x.size != y.size:
            raise ValidationError("addpoints: x and y must have the same length.")
        keep = animated[h]
        nx, ny = np.concatenate([s.x, x])[-keep:], np.concatenate([s.y, y])[-keep:]
        publisher.push(manager.replace_line(h, replace(s, x=nx, y=ny)))
        return []

    def clearpoints(args: list, nargout: int) -> list:
        _need("clearpoints", args, 1)
        h, s = line_handle(args[0], "clearpoints")
        publisher.push(manager.replace_line(h, replace(s, x=np.empty(0), y=np.empty(0))))
        return []

    # -- files ------------------------------------------------------------------
    def write(number: int, filename: str, fmt: str | None, dpi: int, who: str,
              append: bool = False) -> None:
        publisher.flush()
        path = Path(filename)
        ext = (fmt or path.suffix.lstrip(".") or "png").lower()
        if not path.suffix:
            path = path.with_suffix("." + ext)
        spec = manager.snapshot(number)
        if ext == "gif":
            key = path.resolve()
            frames = gif_frames.get(key, []) if append else []
            frames.append(render_png(spec, dpi=min(dpi, _GIF_DPI)))
            gif_frames[key] = frames
            write_gif(path, frames)
            return
        if ext not in EXPORT_FORMATS:
            raise ValidationError(f"{who}: unsupported format {ext!r}; use png, svg, pdf"
                                  + (" or gif." if who == "exportgraphics" else "."))
        if path.suffix.lower().lstrip(".") != ext:
            path = path.with_name(path.name + "." + ext)
        if append:
            raise NotSupportedError(f"{who}: 'Append' is only supported for GIF files.")
        export_figure(spec, path, dpi=dpi)

    def saveas(args: list, nargout: int) -> list:
        _need("saveas", args, 2, 3)
        number = figure_number(args[0], "saveas")
        name = label_text(args[1], "saveas")
        fmt = label_text(args[2], "saveas").lower() if len(args) == 3 else None
        write(number, name, fmt, 150, "saveas")
        return []

    def print_cmd(args: list, nargout: int) -> list:
        fmt, dpi, name = None, 150, None
        number = manager.current_number()
        for a in args:
            w = _word(a)
            if w is None:
                number = figure_number(a, "print")
            elif w.startswith("-d"):
                fmt = {"png": "png", "svg": "svg", "pdf": "pdf", "epsc": None}.get(w[2:].lower())
                if fmt is None:
                    raise NotSupportedError(f"print: format {w!r} is not supported; use -dpng,"
                                            " -dsvg or -dpdf.")
            elif w.startswith("-r"):
                dpi = int(_num(CharArray.from_str(w[2:] or "150"), "print"))
            elif w.startswith("-f") and w[2:].isdigit():
                number = figure_number(np.array([[float(w[2:])]]), "print")
            elif w.startswith("-"):
                raise NotSupportedError(f"print: option {w!r} is not supported.")
            else:
                name = w
        if name is None:
            raise NotSupportedError("print: printing to a printer is not supported; give a "
                                    "file name.")
        if number is None:
            raise ValidationError("print: there is no figure to print.")
        write(number, name, fmt, dpi, "print")
        return []

    def exportgraphics(args: list, nargout: int) -> list:
        _need("exportgraphics", args, 2, 99)
        number = figure_number(args[0], "exportgraphics")
        name = label_text(args[1], "exportgraphics")
        rest = list(args[2:])
        if len(rest) % 2:
            raise ValidationError("exportgraphics: options must be name-value pairs.")
        dpi, append = 150, False
        for key, value in zip(rest[::2], rest[1::2], strict=True):
            k = (_word(key) or "").lower()
            if k == "resolution":
                dpi = int(_num(value, "exportgraphics"))
            elif k == "append":
                append = bool(np.asarray(to_py(value, "exportgraphics")).reshape(-1)[0]) \
                    if _word(value) is None else _word(value).lower() in ("on", "true")
            elif k in ("contenttype", "backgroundcolor", "colorspace", "delaytime", "padding"):
                pass
            else:
                raise ValidationError(f"exportgraphics: unrecognized option {key!r}.")
        write(number, name, None, dpi, "exportgraphics", append)
        return []

    return {"pause": pause, "animatedline": animatedline, "addpoints": addpoints,
            "clearpoints": clearpoints, "saveas": saveas, "print": print_cmd,
            "exportgraphics": exportgraphics}
