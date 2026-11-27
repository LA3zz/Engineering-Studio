"""Control systems in the interpreter (Phase 6, C2): tf, zpk, ss, pid, pidstd, feedback,
series, parallel, pole, zero, dcgain, damp, isstable, stepinfo, margin (values), c2d, tfdata,
zpkdata, ssdata, order, isdt, minreal.

A system is an ``LtiValue`` (class 'tf', 'zpk' or 'ss') wrapping ``control.lti.LtiSystem``.
Operators: ``G1*G2`` (series), ``G1+G2``/``G1-G2`` (parallel), ``-G``, ``k*G``, ``G/k``,
``G1/G2`` (SISO), ``G^n`` (integer n >= 0); ``s = tf('s')`` builds systems from expressions.

Differences from MATLAB (see also ``control.lti``):
- SISO transfer functions and zpk; ``ss`` may be MIMO for creation, poles and dcgain only.
- ``pid`` returns the controller as a transfer function (class 'tf'), not a pid object;
  ``tf(pid(...))`` is therefore the same value. Discrete PID is not supported yet.
- ``margin`` with outputs returns ``[Gm, Pm, Wcg, Wcp]``; without outputs it prints them (the
  margin plot comes with C3). ``minreal`` cancels pole-zero pairs closer than 1e-6.
- ``tfdata``/``zpkdata`` return numeric vectors directly (MATLAB returns cells unless 'v').
- No time delays, no 'Variable' option, no system names or I/O names.
"""

from __future__ import annotations

import math

import numpy as np

from engstudio.control import lti
from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _need, _real, _scalar, _text
from engstudio.lang.interp import Interpreter
from engstudio.lang.symops import register_system_ops
from engstudio.lang.values import CharArray, LtiValue, StructValue

__all__ = ["control_functions", "install_control", "lti_binary", "lti_text", "lti_unary"]


# ------------------------------------------------------------------------- formatting
def _num_text(c: float) -> str:
    return f"{c:.4g}"


def poly_text(coeffs: np.ndarray, var: str) -> str:
    """[1 2 1] -> 's^2 + 2 s + 1' (MATLAB's layout)."""
    n = coeffs.size - 1
    terms: list[str] = []
    for i, c in enumerate(coeffs):
        p = n - i
        if c == 0 and coeffs.size > 1:
            continue
        mag = abs(c)
        power = "" if p == 0 else var if p == 1 else f"{var}^{p}"
        if p == 0:
            body = _num_text(mag)
        elif mag == 1:
            body = power
        else:
            body = f"{_num_text(mag)} {power}"
        sign = "-" if c < 0 else "+"
        terms.append(body if not terms and sign == "+" else
                     ("-" + body if not terms else f"{sign} {body}"))
    return " ".join(terms) if terms else "0"


def _roots_text(roots: np.ndarray, var: str) -> str:
    parts = []
    r = np.asarray(roots, dtype=complex)
    used = np.zeros(r.size, dtype=bool)
    for i, x in enumerate(r):
        if used[i]:
            continue
        used[i] = True
        if abs(x.imag) > 1e-12:  # quadratic factor for the conjugate pair
            j = next((k for k in range(r.size) if not used[k] and abs(r[k] - x.conjugate())
                      < 1e-9 * max(1, abs(x))), None)
            if j is not None:
                used[j] = True
            parts.append(f"({poly_text(np.array([1, -2 * x.real, abs(x) ** 2]), var)})")
        elif x.real == 0:
            parts.append(var)
        else:
            parts.append(f"({var}{'+' if x.real < 0 else '-'}{_num_text(abs(x.real))})")
    return " ".join(parts) if parts else "1"


def _fraction(top: str, bottom: str) -> str:
    if bottom in ("1",):
        return f"  {top}"
    width = max(len(top), len(bottom))
    pad = lambda s: " " * ((width - len(s)) // 2) + s  # noqa: E731
    return f"  {pad(top)}\n  {'-' * width}\n  {pad(bottom)}"


def lti_text(v: LtiValue) -> str:
    sys = v.system
    var = "z" if sys.is_discrete else "s"
    if sys.form == "tf":
        body = _fraction(poly_text(sys.data[0], var), poly_text(sys.data[1], var))
        kind = "transfer function"
    elif sys.form == "zpk":
        z, p, k = sys.data
        top = _roots_text(z, var)
        top = _num_text(k) if top == "1" else (top if k == 1 else f"{_num_text(k)} {top}")
        body = _fraction(top, _roots_text(p, var))
        kind = "zero/pole/gain model"
    else:
        a, b, c, d = sys.data
        body = "\n".join(f"  {name} =\n{_matrix(m)}" for name, m in
                         (("A", a), ("B", b), ("C", c), ("D", d)))
        kind = "state-space model"
    when = "Continuous-time" if not sys.is_discrete else "Discrete-time"
    ts = "" if not sys.is_discrete else (
        "\nSample time: unspecified" if sys.dt == -1 else f"\nSample time: {sys.dt:g} seconds")
    return f"{body}\n\n{when} {kind}.{ts}"


def _matrix(m: np.ndarray) -> str:
    return "\n".join("    " + "  ".join(f"{x:9.4g}" for x in row) for row in m)


def lti_preview(v: LtiValue) -> str:
    r, c = v.system.shape
    return f"{r}x{c} {v.system.form}"


# ------------------------------------------------------------------------- arithmetic
def _sys(v: object, like: LtiValue | None = None) -> lti.LtiSystem:
    if isinstance(v, LtiValue):
        return v.system
    x = _real(v, "system arithmetic")
    if x.size != 1:
        raise NotSupportedError("only scalars can be combined with systems")
    dt = like.system.dt if like is not None else 0.0
    return lti.tf([float(x.reshape(-1)[0])], [1.0], dt=dt)


def _inverse(s: lti.LtiSystem) -> lti.LtiSystem:
    if not s.is_siso:
        raise NotSupportedError("inverting MIMO systems is not supported")
    t = lti.to_tf(s)
    inv = lti.tf(t.data[1], t.data[0], dt=t.dt)
    return lti.to_zpk(inv) if s.form == "zpk" else inv


def lti_binary(op: str, a: object, b: object) -> LtiValue:
    like = a if isinstance(a, LtiValue) else b
    sa, sb = _sys(a, like), _sys(b, like)  # type: ignore[arg-type]
    if op in ("*", ".*"):
        return LtiValue(lti.series(sb, sa))
    if op == "+":
        return LtiValue(lti.parallel(sa, sb))
    if op == "-":
        return LtiValue(lti.parallel(sa, lti.negate(sb)))
    if op in ("/", "./"):
        return LtiValue(lti.series(_inverse(sb), sa))
    if op in ("\\", ".\\"):
        return LtiValue(lti.series(sb, _inverse(sa)))
    if op in ("^", ".^"):
        if not isinstance(a, LtiValue) or isinstance(b, LtiValue):
            raise NotSupportedError("only system^integer is supported")
        n = float(_real(b, "^").reshape(-1)[0])
        if n != int(n) or n < -1:
            raise NotSupportedError("system powers must be integers >= -1")
        if n == -1:
            return LtiValue(_inverse(sa))
        out = lti.tf([1.0], [1.0], dt=sa.dt)
        if sa.form != "tf":
            out = lti.to_zpk(out) if sa.form == "zpk" else lti.to_ss(out)
        for _ in range(int(n)):
            out = lti.series(out, sa)
        return LtiValue(out)
    raise NotSupportedError(f"Operator '{op}' is not supported for systems.")


def lti_unary(op: str, a: LtiValue) -> LtiValue:
    if op == "+":
        return a
    if op == "-":
        return LtiValue(lti.negate(a.system))
    raise NotSupportedError(f"Operator '{op}' is not supported for systems.")


# ------------------------------------------------------------------------- builtins
def _vec(v: object, who: str) -> np.ndarray:
    x = np.asarray(_real(v, who), dtype=float)
    return x.reshape(-1, order="F")


def _cvec(v: object, who: str) -> np.ndarray:
    if isinstance(v, np.ndarray):
        return v.reshape(-1, order="F").astype(complex if v.dtype.kind == "c" else float)
    return _vec(v, who)


def _one(v: object, who: str) -> float:
    x = _vec(v, who)
    if x.size != 1:
        raise ValidationError(f"{who}: expected a scalar.")
    return float(x[0])


def _system_arg(v: object, who: str) -> lti.LtiSystem:
    if not isinstance(v, LtiValue):
        raise ValidationError(f"{who}: the first argument must be a system (tf, zpk or ss).")
    return v.system


def _row(x: np.ndarray) -> np.ndarray:
    return np.asarray(x).reshape(1, -1)


def _col(x: np.ndarray) -> np.ndarray:
    return np.asarray(x).reshape(-1, 1)


def control_functions(interp: Interpreter) -> dict[str, Builtin]:
    def sample_time(args: list, who: str) -> float:
        return _one(args[0], who) if args else 0.0

    def tf_cmd(args: list, nargout: int) -> list:
        _need("tf", args, 1, 3)
        if isinstance(args[0], CharArray):
            var = _text(args[0], "tf")
            if var not in ("s", "z", "p"):
                raise ValidationError("tf: use tf('s') or tf('z', Ts).")
            dt = _one(args[1], "tf") if len(args) > 1 else (-1.0 if var == "z" else 0.0)
            return [LtiValue(lti.tf([1.0, 0.0], [1.0], dt=dt))]
        if isinstance(args[0], LtiValue):
            return [LtiValue(lti.to_tf(args[0].system))]
        if len(args) == 1:
            return [LtiValue(lti.tf(_vec(args[0], "tf"), [1.0]))]
        return [LtiValue(lti.tf(_vec(args[0], "tf"), _vec(args[1], "tf"),
                                dt=sample_time(args[2:], "tf")))]

    def zpk_cmd(args: list, nargout: int) -> list:
        _need("zpk", args, 1, 4)
        if isinstance(args[0], LtiValue):
            return [LtiValue(lti.to_zpk(args[0].system))]
        if isinstance(args[0], CharArray):
            return [LtiValue(lti.zpk([0.0], [], 1.0, dt=0.0))]
        _need("zpk", args, 3, 4)
        return [LtiValue(lti.zpk(_cvec(args[0], "zpk"), _cvec(args[1], "zpk"),
                                 _one(args[2], "zpk"), dt=sample_time(args[3:], "zpk")))]

    def ss_cmd(args: list, nargout: int) -> list:
        _need("ss", args, 1, 5)
        if isinstance(args[0], LtiValue):
            return [LtiValue(lti.to_ss(args[0].system))]
        _need("ss", args, 4, 5)
        mats = [np.asarray(_real(a, "ss"), dtype=float) for a in args[:4]]
        return [LtiValue(lti.ss(*mats, dt=sample_time(args[4:], "ss")))]

    def pid_cmd(args: list, nargout: int) -> list:
        _need("pid", args, 0, 5)
        vals = [_one(a, "pid") for a in args[:4]]
        if len(args) == 5:
            raise NotSupportedError("pid: discrete PID controllers are not supported yet.")
        return [LtiValue(lti.pid(*vals))]

    def pidstd_cmd(args: list, nargout: int) -> list:
        _need("pidstd", args, 1, 4)
        vals = [_one(a, "pidstd") for a in args]
        return [LtiValue(lti.pidstd(*vals))]

    def feedback_cmd(args: list, nargout: int) -> list:
        _need("feedback", args, 1, 3)
        g = args[0]
        h = args[1] if len(args) > 1 else np.array([[1.0]])
        sign = int(_one(args[2], "feedback")) if len(args) > 2 else -1
        like = g if isinstance(g, LtiValue) else h
        return [LtiValue(lti.feedback(_sys(g, like), _sys(h, like), sign))]  # type: ignore[arg-type]

    def series_cmd(args: list, nargout: int) -> list:
        _need("series", args, 2)
        like = args[0] if isinstance(args[0], LtiValue) else args[1]
        return [LtiValue(lti.series(_sys(args[0], like), _sys(args[1], like)))]

    def parallel_cmd(args: list, nargout: int) -> list:
        _need("parallel", args, 2)
        like = args[0] if isinstance(args[0], LtiValue) else args[1]
        return [LtiValue(lti.parallel(_sys(args[0], like), _sys(args[1], like)))]

    def pole_cmd(args: list, nargout: int) -> list:
        _need("pole", args, 1)
        return [_col(_narrow(lti.poles(_system_arg(args[0], "pole"))))]

    def zero_cmd(args: list, nargout: int) -> list:
        _need("zero", args, 1)
        return [_col(_narrow(lti.zeros(_system_arg(args[0], "zero"))))]

    def dcgain_cmd(args: list, nargout: int) -> list:
        _need("dcgain", args, 1)
        g = lti.dcgain(_system_arg(args[0], "dcgain"))
        return [np.atleast_2d(np.asarray(g, dtype=float))]

    def damp_cmd(args: list, nargout: int) -> list:
        _need("damp", args, 1)
        wn, zeta, p = lti.damp(_system_arg(args[0], "damp"))
        if nargout:
            return [_col(wn), _col(zeta), _col(_narrow(p))][:max(1, nargout)]
        lines = ["", f"{'Pole':>26} {'Damping':>12} {'Frequency':>14}", ""]
        for pi, z, w in zip(p, zeta, wn, strict=True):
            pole = f"{pi.real:.3g}" + (f" {'-' if pi.imag < 0 else '+'} {abs(pi.imag):.3g}i"
                                        if abs(pi.imag) > 0 else "")
            lines.append(f"{pole:>26} {z:>12.3g} {w:>14.3g}")
        interp.host.write("\n".join(lines) + "\n\n")
        return []

    def isstable_cmd(args: list, nargout: int) -> list:
        _need("isstable", args, 1)
        return [_scalar(lti.is_stable(_system_arg(args[0], "isstable")))]

    def stepinfo_cmd(args: list, nargout: int) -> list:
        _need("stepinfo", args, 1, 5)
        info = lti.stepinfo(_system_arg(args[0], "stepinfo"))
        fields = {"RiseTime": info.rise_time, "SettlingTime": info.settling_time,
                  "SettlingMin": info.settling_min, "SettlingMax": info.settling_max,
                  "Overshoot": info.overshoot, "Undershoot": info.undershoot,
                  "Peak": info.peak, "PeakTime": info.peak_time}
        return [StructValue({k: _scalar(float(v)) for k, v in fields.items()})]

    def margin_cmd(args: list, nargout: int) -> list:
        _need("margin", args, 1)
        gm, pm, wcg, wcp = lti.margin(_system_arg(args[0], "margin"))
        if nargout:
            return [_scalar(gm), _scalar(pm), _scalar(wcg), _scalar(wcp)][:max(1, nargout)]
        gm_db = 20 * math.log10(gm) if gm > 0 and math.isfinite(gm) else gm
        interp.host.write(
            f"Gain margin: {gm_db:.4g} dB (at {wcg:.4g} rad/s)\n"
            f"Phase margin: {pm:.4g} deg (at {wcp:.4g} rad/s)\n\n")
        return []

    def c2d_cmd(args: list, nargout: int) -> list:
        _need("c2d", args, 2, 3)
        method = _text(args[2], "c2d").lower() if len(args) == 3 else "zoh"
        return [LtiValue(lti.c2d(_system_arg(args[0], "c2d"), _one(args[1], "c2d"), method))]

    def tfdata_cmd(args: list, nargout: int) -> list:
        _need("tfdata", args, 1, 2)
        t = lti.to_tf(_system_arg(args[0], "tfdata"))
        return [_row(t.data[0]), _row(t.data[1]), _scalar(max(t.dt, 0.0))][:max(1, nargout)]

    def zpkdata_cmd(args: list, nargout: int) -> list:
        _need("zpkdata", args, 1, 2)
        z = lti.to_zpk(_system_arg(args[0], "zpkdata"))
        return [_col(_narrow(z.data[0])), _col(_narrow(z.data[1])), _scalar(z.data[2]),
                _scalar(max(z.dt, 0.0))][:max(1, nargout)]

    def ssdata_cmd(args: list, nargout: int) -> list:
        _need("ssdata", args, 1)
        s = lti.to_ss(_system_arg(args[0], "ssdata"))
        return [np.array(m) for m in s.data][:max(1, nargout)]

    def order_cmd(args: list, nargout: int) -> list:
        _need("order", args, 1)
        return [_scalar(float(_system_arg(args[0], "order").order))]

    def isdt_cmd(args: list, nargout: int) -> list:
        _need("isdt", args, 1)
        return [_scalar(_system_arg(args[0], "isdt").is_discrete)]

    def minreal_cmd(args: list, nargout: int) -> list:
        _need("minreal", args, 1, 2)
        s = _system_arg(args[0], "minreal")
        if not s.is_siso:
            raise NotSupportedError("minreal: MIMO systems are not supported yet.")
        z = lti.to_zpk(s)
        zeros, poles = list(z.data[0]), list(z.data[1])
        tol = _one(args[1], "minreal") if len(args) > 1 else 1e-6
        for zz in list(zeros):
            match = next((p for p in poles if abs(p - zz) <= tol * max(1, abs(zz))), None)
            if match is not None:
                zeros.remove(zz)
                poles.remove(match)
        out = lti.zpk(np.array(zeros), np.array(poles), z.data[2], dt=z.dt)
        return [LtiValue(out if s.form == "zpk" else lti.to_tf(out) if s.form == "tf"
                         else lti.to_ss(out))]

    def pidtune_cmd(args: list, nargout: int) -> list:
        """[C, info] = pidtune(G, type) or pidtune(G, type, wc): C as a transfer function,
        info with Stable, CrossoverFrequency, PhaseMargin, Kp, Ki, Kd, Tf."""
        _need("pidtune", args, 2, 3)
        plant = _system_arg(args[0], "pidtune")
        kind = _text(args[1], "pidtune")
        wc = _one(args[2], "pidtune") if len(args) == 3 else None
        ctrl, info = lti.pidtune(plant, kind, wc)
        gm, pm, _wcg, wcp = lti.margin(lti.series(ctrl, plant))
        fields = {"Stable": _scalar(info.stable), "CrossoverFrequency": _scalar(wcp),
                  "PhaseMargin": _scalar(pm), "Kp": _scalar(info.kp), "Ki": _scalar(info.ki),
                  "Kd": _scalar(info.kd), "Tf": _scalar(info.tf)}
        return [LtiValue(ctrl), StructValue(fields)][:max(1, nargout)]

    return {
        "pidtune": pidtune_cmd,
        "tf": tf_cmd, "zpk": zpk_cmd, "ss": ss_cmd, "pid": pid_cmd, "pidstd": pidstd_cmd,
        "feedback": feedback_cmd, "series": series_cmd, "parallel": parallel_cmd,
        "pole": pole_cmd, "zero": zero_cmd, "dcgain": dcgain_cmd, "damp": damp_cmd,
        "isstable": isstable_cmd, "stepinfo": stepinfo_cmd, "margin": margin_cmd,
        "c2d": c2d_cmd, "tfdata": tfdata_cmd, "zpkdata": zpkdata_cmd, "ssdata": ssdata_cmd,
        "order": order_cmd, "isdt": isdt_cmd, "minreal": minreal_cmd,
    }


def _narrow(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x)
    if x.dtype.kind == "c" and not np.any(np.abs(x.imag) > 1e-12 * np.maximum(1, np.abs(x))):
        return x.real.astype(float)
    return x


def install_control(interp: Interpreter) -> None:
    interp.functions.update(control_functions(interp))


register_system_ops(lti_binary, lti_unary)
