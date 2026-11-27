"""Plot commands of the interpreter (P5.1): figure, gcf, gca, clf, cla, close, hold, ishold,
plot, drawnow; plus the axes/annotation commands of ``lang.builtins_plotaxes`` (P5.2) and the
2-D plot types of ``lang.builtins_plot2d`` (P5.3), installed together by ``install_plot``.
Thin layer over ``lang.figstate``; the kernel client supplies ``publish(spec)``
(send a figure snapshot to the GUI) and ``retire(number)`` (tell the GUI to close a window).

Differences from MATLAB: see ``lang.figstate``. ``figure`` accepts the properties Name, Color,
Position, NumberTitle, Visible, Tag, Units, MenuBar, ToolBar and Resize; only Name is used so far.
``plot`` publishes a snapshot on every call (throttling comes with the animation milestone).
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.lang.builtins_core import Builtin, _arith, _int, _need, _scalar, _text
from engstudio.lang.builtins_plot2d import plot2d_functions
from engstudio.lang.builtins_plot3d import plot3d_functions
from engstudio.lang.builtins_plotaxes import axes_functions
from engstudio.lang.builtins_plotio import plotio_functions
from engstudio.lang.figstate import MAX_FIGURE, FigureManager, build_series, parse_color
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray, class_of
from engstudio.plotting.model import FigureSpec

__all__ = ["Publisher", "install_plot", "plot_functions"]

_FIGURE_PROPS = {"name", "color", "position", "numbertitle", "visible", "tag", "units",
                 "menubar", "toolbar", "resize"}


def _py(v: object, who: str) -> object:
    """Interpreter value -> ``str`` (character vector) or 2-D float/complex array."""
    if isinstance(v, CharArray):
        return _text(v, who)
    if isinstance(v, np.ndarray):
        a = _arith(v, who)
        return a if a.dtype.kind == "c" else a.astype(np.float64, copy=False)
    raise ValidationError(f"{who}: unsupported argument of class {class_of(v)}.")


def _handle(h: int) -> list:
    return [_scalar(float(h))]


class Publisher:
    """Sends figure snapshots to the GUI, at most one per figure every ``min_interval``
    seconds (design pick 5A: throttled drawing, so animation loops do not flood the GUI).
    A skipped update is kept as pending and sent by the next allowed push or by ``flush()``
    (the kernel flushes when a request ends; ``pause`` flushes before sleeping)."""

    def __init__(self, publish: Callable[[FigureSpec], None], manager: FigureManager,
                 min_interval: float = 0.0, clock: Callable[[], float] = time.monotonic):
        self._publish = publish
        self._manager = manager
        self.min_interval = min_interval
        self._clock = clock
        self._last: dict[int, float] = {}
        self._pending: set[int] = set()

    def push(self, number: int | None = None) -> None:
        number = self._manager.gcf() if number is None else number
        now = self._clock()
        if self.min_interval > 0 and now - self._last.get(number, -1e18) < self.min_interval:
            self._pending.add(number)
            return
        self._send(number, now)

    def wait_time(self, number: int) -> float:
        """Seconds until figure ``number`` may be drawn again (0 if now)."""
        if self.min_interval <= 0:
            return 0.0
        return max(0.0, self._last.get(number, -1e18) + self.min_interval - self._clock())

    def push_now(self, number: int) -> None:
        """Send figure ``number`` immediately (the caller has waited ``wait_time``)."""
        self._send(number, self._clock())

    def flush(self) -> None:
        for number in sorted(self._pending):
            if number in self._manager.numbers():
                self._send(number, self._clock())
        self._pending.clear()

    def forget(self, number: int) -> None:
        self._pending.discard(number)
        self._last.pop(number, None)

    def _send(self, number: int, now: float) -> None:
        self._pending.discard(number)
        self._last[number] = now
        self._publish(self._manager.snapshot(number))


def plot_functions(
    interp: Interpreter,
    publish: Callable[[FigureSpec], None],
    retire: Callable[[int], None],
    manager: FigureManager,
    publisher: Publisher | None = None,
) -> dict[str, Builtin]:
    publisher = publisher or Publisher(publish, manager)

    def push(number: int | None = None) -> None:
        publisher.push(number)

    def figure(args: list, nargout: int) -> list:
        number = None
        rest = list(args)
        if rest and isinstance(rest[0], np.ndarray):
            number = _int(rest.pop(0), "figure")
        if len(rest) % 2:
            raise ValidationError("figure: property names and values must come in pairs.")
        name, props = None, {}
        for key, value in zip(rest[::2], rest[1::2], strict=True):
            prop = _text(key, "figure")
            low = prop.lower()
            if low not in _FIGURE_PROPS:
                raise ValidationError(f"figure: unrecognized property {prop!r}.")
            if low == "name":
                name = _text(value, "figure")
            elif low == "color":
                props["Color"] = parse_color(_py(value, "figure"), "figure")
            elif low == "position":
                pos = _arith(value, "figure")
                if pos.size != 4:
                    raise ValidationError("figure: Position must have four elements.")
                props["Position"] = [float(v) for v in pos.reshape(-1)]
            else:
                props[prop] = _py(value, "figure") if isinstance(value, np.ndarray) else _text(
                    value, "figure")
        n = manager.figure(number, name, props)
        push(n)
        return _handle(n) if nargout else []

    def gcf(args: list, nargout: int) -> list:
        _need("gcf", args, 0)
        existed = manager.current_number() is not None
        n = manager.gcf()
        if not existed:
            push(n)
        return _handle(n)

    def gca(args: list, nargout: int) -> list:
        _need("gca", args, 0)
        existed = manager.current_number() is not None
        h = manager.gca()
        if not existed:
            push()
        return _handle(h)

    def clf(args: list, nargout: int) -> list:
        _need("clf", args, 0)
        push(manager.clf())
        return []

    def cla(args: list, nargout: int) -> list:
        _need("cla", args, 0)
        push(manager.cla())
        return []

    def close(args: list, nargout: int) -> list:
        _need("close", args, 0, 1)
        which: int | str | None = None
        if args:
            if isinstance(args[0], CharArray):
                which = _text(args[0], "close")
                if which != "all":
                    raise ValidationError("close: expected a figure number or 'all'.")
            else:
                which = _int(args[0], "close")
                if not 1 <= which <= MAX_FIGURE:
                    raise ValidationError("close: expected a figure number or 'all'.")
        for number in manager.close(which):
            publisher.forget(number)
            retire(number)
        return []

    def hold(args: list, nargout: int) -> list:
        _need("hold", args, 0, 1)
        mode = _text(args[0], "hold").lower() if args else None
        state = manager.hold(mode)
        return [_scalar(state)] if nargout else []

    def ishold(args: list, nargout: int) -> list:
        _need("ishold", args, 0)
        return [_scalar(manager.ishold())]

    def plot(args: list, nargout: int) -> list:
        series = build_series([_py(a, "plot") for a in args])
        handles = manager.add_lines(series)
        push()
        if not nargout:
            return []
        return [np.array([[float(h)] for h in handles])]

    def drawnow(args: list, nargout: int) -> list:
        """Show the current figure now. Like MATLAB (which waits for rendering), a loop that
        calls drawnow is paced to the frame rate so an animation can be seen; ``drawnow
        limitrate`` (or 'nocallbacks' + 'limitrate') skips frames instead of waiting."""
        _need("drawnow", args, 0, 2)
        words = {_text(a, "drawnow").lower() for a in args}
        if not words <= {"limitrate", "nocallbacks", "update", "expose"}:
            raise ValidationError("drawnow: options are limitrate, nocallbacks, update, expose.")
        number = manager.current_number()
        if number is None:
            return []
        if "limitrate" in words:
            push(number)
            return []
        wait = publisher.wait_time(number)
        end = time.monotonic() + wait
        while wait > 0:
            interp.check_cancel()
            time.sleep(min(wait, 0.02))
            wait = end - time.monotonic()
        publisher.push_now(number)
        return []

    out: dict[str, Builtin] = {
        "figure": figure, "gcf": gcf, "gca": gca, "clf": clf, "cla": cla, "close": close,
        "hold": hold, "ishold": ishold, "plot": plot, "drawnow": drawnow}
    out.update(axes_functions(manager, push))
    out.update(plot2d_functions(manager, push))
    out.update(plot3d_functions(manager, push))
    out.update(plotio_functions(interp, manager, publisher))
    return out


def install_plot(
    interp: Interpreter,
    publish: Callable[[FigureSpec], None],
    retire: Callable[[int], None],
    min_interval: float = 0.0,
) -> FigureManager:
    """Register the plot commands on ``interp``; returns the figure manager they use.
    ``min_interval`` > 0 throttles figure updates (seconds per figure); the caller must then
    call ``manager.publisher.flush()`` when a run ends so the last frame is shown."""
    manager = FigureManager()
    publisher = Publisher(publish, manager, min_interval)
    manager.publisher = publisher
    interp.functions.update(plot_functions(interp, publish, retire, manager, publisher))
    return manager
