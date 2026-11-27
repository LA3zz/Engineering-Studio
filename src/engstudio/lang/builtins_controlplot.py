"""Control-system response plots (Phase 6, C3): step, impulse, initial, lsim, bode, margin,
nyquist, rlocus, pzmap.

Called without outputs they draw into the current figure (several systems in one call are
overlaid, each optionally followed by a line spec such as 'r--'); with outputs they return
the data and draw nothing, as in MATLAB.

Differences from MATLAB:
- Data outputs are 2-D: ``[y, t] = step(sys)`` gives columns; ``[mag, phase, w] = bode(sys)``
  gives column vectors (MATLAB returns 1x1xN arrays). ``mag`` is absolute, ``phase`` degrees.
- Plots are ordinary figures (no interactive characteristic markers or right-click menus);
  ``margin(sys)`` draws the Bode plot with dashed lines at the crossover frequencies and the
  margins in the title. ``nyquist`` draws positive frequencies solid, negative dashed, and marks
  -1 with a red '+'. Bode phase is unwrapped (it may differ from MATLAB by multiples of 360).
- ``rlocus`` gains are chosen automatically (python-control's algorithm) unless given.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from engstudio.control import lti
from engstudio.core.errors import ValidationError
from engstudio.lang.builtins_core import Builtin, _real
from engstudio.lang.figstate import FigureManager, parse_linespec
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray, LtiValue
from engstudio.plotting.model import SeriesSpec

__all__ = ["control_plot_functions", "install_control_plots"]


def _split(args: list, who: str) -> tuple[list[tuple[lti.LtiSystem, str | None]], list]:
    """Leading systems (each optionally followed by a line spec) and the remaining args."""
    systems: list[tuple[lti.LtiSystem, str | None]] = []
    i = 0
    while i < len(args) and isinstance(args[i], LtiValue):
        spec = None
        if i + 1 < len(args) and isinstance(args[i + 1], CharArray):
            spec = args[i + 1].to_str()
            i += 1
        systems.append((args[i - (1 if spec else 0)].system, spec))
        i += 1
    if not systems:
        raise ValidationError(f"{who}: the first argument must be a system (tf, zpk or ss).")
    return systems, list(args[i:])


def _style(spec: str | None, who: str) -> dict[str, object]:
    if not spec:
        return {}
    color, style, marker = parse_linespec(spec, who)
    out: dict[str, object] = {}
    if color:
        out["color"] = color
    if style:
        out["line_style"] = style
    if marker:
        out["marker"] = marker
    return out


def _vec(v: object, who: str) -> np.ndarray:
    return np.asarray(_real(v, who), dtype=float).reshape(-1, order="F")


def _col(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=float).reshape(-1, 1)


def control_plot_functions(interp: Interpreter, manager: FigureManager,
                           push: Callable[[int | None], None]) -> dict[str, Builtin]:
    def draw(series: list[SeriesSpec], **props: object) -> None:
        manager.add_lines(series, props)
        push(None)

    def time_response(kind: str, title: str) -> Builtin:
        def run(args: list, nargout: int) -> list:
            systems, rest = _split(args, kind)
            x0 = None
            if kind == "initial":
                if not rest:
                    raise ValidationError("initial: use initial(sys, x0) or initial(sys, x0, t).")
                x0 = _vec(rest.pop(0), kind)
            t_arg = _vec(rest[0], kind) if rest else None
            if len(rest) > 1:
                raise ValidationError(f"{kind}: too many arguments.")
            curves = []
            for sys, spec in systems:
                if kind == "step":
                    t, y = lti.step(sys, t_arg)
                elif kind == "impulse":
                    t, y = lti.impulse(sys, t_arg)
                else:
                    t, y = lti.initial(sys, x0, t_arg)
                curves.append((t, y, spec, sys))
            if nargout:
                t, y, _, _ = curves[0]
                return [_col(y), _col(t)][:max(1, nargout)]
            series = []
            for t, y, spec, sys in curves:
                style = _style(spec, kind)
                if sys.is_discrete:  # sampled response: stairs, as MATLAB
                    xs, ys = np.repeat(t, 2)[1:], np.repeat(y, 2)[:-1]
                    series.append(SeriesSpec("line", xs, ys, **style))  # type: ignore[arg-type]
                else:
                    series.append(SeriesSpec("line", t, y, **style))  # type: ignore[arg-type]
            draw(series, title=title, xlabel="Time (seconds)", ylabel="Amplitude", grid=True)
            return []
        return run

    def lsim_cmd(args: list, nargout: int) -> list:
        systems, rest = _split(args, "lsim")
        if len(rest) < 2:
            raise ValidationError("lsim: use lsim(sys, u, t) or lsim(sys, u, t, x0).")
        u, t = _vec(rest[0], "lsim"), _vec(rest[1], "lsim")
        x0 = _vec(rest[2], "lsim") if len(rest) > 2 else None
        results = [(lti.lsim(sys, u, t, x0), spec) for sys, spec in systems]
        if nargout:
            (tt, y), _ = results[0]
            return [_col(y), _col(tt)][:max(1, nargout)]
        series = [SeriesSpec("line", t, u, color="#a0a0a0", label="input")]
        series += [SeriesSpec("line", tt, y, **_style(spec, "lsim"))  # type: ignore[arg-type]
                   for (tt, y), spec in results]
        draw(series, title="Linear Simulation Results", xlabel="Time (seconds)",
             ylabel="Amplitude", grid=True)
        return []

    def bode_data(args: list, who: str):
        systems, rest = _split(args, who)
        w = _vec(rest[0], who) if rest else None
        return [(lti.bode(sys, w), spec) for sys, spec in systems]

    def bode_plot(results: list, title: str, marks: tuple[float, float] | None = None) -> None:
        manager.subplot(2, 1, [1])
        mags = [SeriesSpec("line", w, 20 * np.log10(np.maximum(m, 1e-300)),
                           **_style(spec, "bode"))  # type: ignore[arg-type]
                for (m, _p, w), spec in results]
        phases = [SeriesSpec("line", w, p, **_style(spec, "bode"))  # type: ignore[arg-type]
                  for (_m, p, w), spec in results]
        if marks is not None:
            for wv in marks:
                if math.isfinite(wv) and wv > 0:
                    mags.append(SeriesSpec("xline", [wv], [math.nan], line_style="--"))
                    phases.append(SeriesSpec("xline", [wv], [math.nan], line_style="--"))
        manager.add_lines(mags, {"title": title, "ylabel": "Magnitude (dB)", "xscale": "log",
                                 "grid": True})
        manager.subplot(2, 1, [2])
        manager.add_lines(phases, {"ylabel": "Phase (deg)", "xlabel": "Frequency (rad/s)",
                                   "xscale": "log", "grid": True})
        push(None)

    def bode_cmd(args: list, nargout: int) -> list:
        results = bode_data(args, "bode")
        if nargout:
            (m, p, w), _ = results[0]
            return [_col(m), _col(p), _col(w)][:max(1, nargout)]
        bode_plot(results, "Bode Diagram")
        return []

    def margin_cmd(args: list, nargout: int) -> list:
        systems, _rest = _split(args, "margin")
        sys = systems[0][0]
        gm, pm, wcg, wcp = lti.margin(sys)
        if nargout:
            return [np.array([[gm]]), np.array([[pm]]), np.array([[wcg]]),
                    np.array([[wcp]])][:max(1, nargout)]
        gm_db = 20 * math.log10(gm) if gm > 0 and math.isfinite(gm) else gm
        title = (f"Bode Diagram\nGm = {_num(gm_db)} dB (at {_num(wcg)} rad/s), "
                 f"Pm = {_num(pm)} deg (at {_num(wcp)} rad/s)")
        bode_plot([(lti.bode(sys), systems[0][1])], title, (wcg, wcp))
        return []

    def nyquist_cmd(args: list, nargout: int) -> list:
        systems, rest = _split(args, "nyquist")
        w = _vec(rest[0], "nyquist") if rest else None
        data = [(lti.nyquist(sys, w), spec) for sys, spec in systems]
        if nargout:
            (re, im, ww), _ = data[0]
            return [_col(re), _col(im), _col(ww)][:max(1, nargout)]
        series = []
        for (re, im, _ww), spec in data:
            style = _style(spec, "nyquist")
            series.append(SeriesSpec("line", re, im, **style))  # type: ignore[arg-type]
            mirror = {**style, "line_style": "--"}
            series.append(SeriesSpec("line", re[::-1], -im[::-1], **mirror))  # type: ignore[arg-type]
        series.append(SeriesSpec("scatter", [-1.0], [0.0], marker="+", color="#ff0000",
                                 marker_size=10))
        draw(series, title="Nyquist Diagram", xlabel="Real Axis", ylabel="Imaginary Axis",
             grid=True)
        return []

    def rlocus_cmd(args: list, nargout: int) -> list:
        systems, rest = _split(args, "rlocus")
        k = _vec(rest[0], "rlocus") if rest else None
        sys = systems[0][0]
        roots, gains = lti.rlocus(sys, k)
        if nargout:
            return [np.asarray(roots).T, gains.reshape(1, -1)][:max(1, nargout)]
        series = []
        for j in range(roots.shape[1]):
            branch = roots[:, j]
            series.append(SeriesSpec("line", branch.real, branch.imag,
                                     **_style(systems[0][1], "rlocus")))  # type: ignore[arg-type]
        series += _pz_series(sys)
        draw(series, title="Root Locus", xlabel="Real Axis (seconds^{-1})",
             ylabel="Imaginary Axis (seconds^{-1})", grid=True)
        return []

    def pzmap_cmd(args: list, nargout: int) -> list:
        systems, _rest = _split(args, "pzmap")
        sys = systems[0][0]
        if nargout:
            return [lti.poles(sys).reshape(-1, 1), lti.zeros(sys).reshape(-1, 1)][
                :max(1, nargout)]
        series = []
        for s, _spec in systems:
            series += _pz_series(s)
        draw(series, title="Pole-Zero Map", xlabel="Real Axis (seconds^{-1})",
             ylabel="Imaginary Axis (seconds^{-1})", grid=True)
        return []

    return {
        "step": time_response("step", "Step Response"),
        "impulse": time_response("impulse", "Impulse Response"),
        "initial": time_response("initial", "Response to Initial Conditions"),
        "lsim": lsim_cmd, "bode": bode_cmd, "margin": margin_cmd, "nyquist": nyquist_cmd,
        "rlocus": rlocus_cmd, "pzmap": pzmap_cmd,
    }


def _num(v: float) -> str:
    if math.isinf(v):
        return "Inf" if v > 0 else "-Inf"
    return "NaN" if math.isnan(v) else f"{v:.3g}"


def _pz_series(sys: lti.LtiSystem) -> list[SeriesSpec]:
    out = []
    p = np.asarray(lti.poles(sys), dtype=complex)
    if p.size:
        out.append(SeriesSpec("scatter", p.real, p.imag, marker="x", marker_size=9,
                              color="#1f6fb4"))
    z = np.asarray(lti.zeros(sys), dtype=complex) if sys.is_siso else np.array([])
    if z.size:
        out.append(SeriesSpec("scatter", z.real, z.imag, marker="o", marker_size=8,
                              color="#1f6fb4"))
    return out


def install_control_plots(interp: Interpreter, manager: FigureManager) -> None:
    """Install after ``install_control`` (replaces its text-only ``margin``) and
    ``install_plot`` (needs its figure manager)."""
    push = manager.publisher.push  # type: ignore[union-attr]
    interp.functions.update(control_plot_functions(interp, manager, push))
