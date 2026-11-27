"""Linear time-invariant systems (Phase 6, C1): pure engine layer, no GUI, no interpreter.

``LtiSystem`` is immutable data in one of three forms - transfer function ('tf': numerator and
denominator coefficients, highest power first), zero-pole-gain ('zpk') or state space ('ss':
A, B, C, D) - continuous (``dt == 0``) or discrete (``dt > 0`` seconds, ``dt == -1``
unspecified). The numerics are delegated to python-control, imported lazily because importing
it takes seconds.

Combining systems follows MATLAB's precedence for the result form: ss > zpk > tf.

Scope and differences from MATLAB (C1):
- Responses, margins, root locus and PID tuning are for single-input single-output systems;
  ``ss`` may be MIMO for creation, conversion, poles and dcgain.
- ``step``/``impulse`` pick the final time from the slowest pole (MATLAB uses a similar but
  not identical rule); ``stepinfo`` uses 10-90% rise time and a 2% settling band, as MATLAB.
- ``pidtune`` targets a 60 degree phase margin and chooses the fastest crossover frequency
  that keeps the closed loop stable with a gain margin of at least 6 dB (MATLAB's algorithm
  is proprietary; results are similar in robustness, not identical in gains).
- Time delays are not supported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from engstudio.core.errors import DimensionError, NotSupportedError, ValidationError

__all__ = [
    "LtiSystem", "PidInfo", "StepInfo", "bode", "c2d", "damp", "dcgain", "feedback", "impulse",
    "initial", "is_stable", "lsim", "margin", "nyquist", "parallel", "pid", "pidstd", "pidtune",
    "poles", "rlocus", "series", "ss", "step", "stepinfo", "tf", "to_ss", "to_tf", "to_zpk",
    "zeros", "zpk",
]

_FORMS = ("tf", "zpk", "ss")
_RANK = {"tf": 0, "zpk": 1, "ss": 2}


def _ct() -> Any:
    import control  # lazy: about 3 s

    return control


# ---------------------------------------------------------------------------- validation
def _vec(name: str, v: object, allow_complex: bool = False, allow_empty: bool = True
         ) -> np.ndarray:
    arr = np.asarray(v)
    if arr.dtype.kind not in "biufc":
        raise ValidationError(f"{name}: expected numbers")
    arr = np.array(arr, dtype=np.complex128 if arr.dtype.kind == "c" else np.float64)
    arr = arr.reshape(-1)
    if arr.dtype.kind == "c":
        if not allow_complex:
            if np.any(arr.imag):
                raise ValidationError(f"{name}: complex values are not allowed")
            arr = arr.real.copy()
    if not np.all(np.isfinite(arr)):
        raise ValidationError(f"{name}: values must be finite")
    if arr.size == 0 and not allow_empty:
        raise ValidationError(f"{name}: must not be empty")
    arr.setflags(write=False)
    return arr


def _mat(name: str, v: object) -> np.ndarray:
    arr = np.array(v, dtype=np.float64)
    if arr.ndim == 0:
        arr = arr.reshape(1, 1)
    elif arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2:
        raise DimensionError(f"{name}: expected a matrix")
    if not np.all(np.isfinite(arr)):
        raise ValidationError(f"{name}: values must be finite")
    arr.setflags(write=False)
    return arr


def _trim(c: np.ndarray) -> np.ndarray:
    nz = np.flatnonzero(c)
    out = c[nz[0]:] if nz.size else np.zeros(1)
    out = np.array(out)
    out.setflags(write=False)
    return out


def _dt(dt: float) -> float:
    dt = float(dt)
    if not (dt == 0 or dt == -1 or (math.isfinite(dt) and dt > 0)):
        raise ValidationError(f"sample time must be 0 (continuous), positive or -1, got {dt}")
    return dt


# ------------------------------------------------------------------------------- system
@dataclass(frozen=True, eq=False)
class LtiSystem:
    """``form`` 'tf': data = (num, den); 'zpk': (z, p, k); 'ss': (A, B, C, D)."""

    form: str
    data: tuple
    dt: float = 0.0

    @property
    def is_discrete(self) -> bool:
        return self.dt != 0

    @property
    def shape(self) -> tuple[int, int]:
        """(outputs, inputs)."""
        if self.form == "ss":
            return (self.data[2].shape[0], self.data[1].shape[1])
        return (1, 1)

    @property
    def is_siso(self) -> bool:
        return self.shape == (1, 1)

    @property
    def order(self) -> int:
        if self.form == "ss":
            return self.data[0].shape[0]
        if self.form == "zpk":
            return self.data[1].size
        return self.data[1].size - 1

    def __reduce__(self):
        return (_rebuild, (self.form, self.data, self.dt))

    def to_control(self) -> Any:
        """The equivalent python-control object (for the numerics)."""
        ct = _ct()
        dt = None if self.dt == -1 else self.dt  # python-control: True/None for unspecified
        if self.dt == -1:
            dt = True
        if self.form == "tf":
            return ct.tf(list(self.data[0]), list(self.data[1]), dt)
        if self.form == "zpk":
            z, p, k = self.data
            return ct.zpk(list(z), list(p), float(k), dt=dt)
        a, b, c, d = self.data
        return ct.ss(np.array(a), np.array(b), np.array(c), np.array(d), dt)


def _rebuild(form: str, data: tuple, dt: float) -> LtiSystem:
    if form == "tf":
        return tf(*data, dt=dt)
    if form == "zpk":
        return zpk(*data, dt=dt)
    return ss(*data, dt=dt)


def tf(num: object, den: object, dt: float = 0.0) -> LtiSystem:
    n = _trim(_vec("num", num, allow_empty=False))
    d = _trim(_vec("den", den, allow_empty=False))
    if not np.any(d):
        raise ValidationError("den: the denominator must not be zero")
    return LtiSystem("tf", (n, d), _dt(dt))


def zpk(z: object, p: object, k: float, dt: float = 0.0) -> LtiSystem:
    zz = _vec("z", z, allow_complex=True)
    pp = _vec("p", p, allow_complex=True)
    kk = float(np.asarray(k, dtype=float).reshape(-1)[0])
    for name, roots in (("z", zz), ("p", pp)):
        if roots.dtype.kind == "c" and not _conjugate_pairs(roots):
            raise ValidationError(f"{name}: complex roots must come in conjugate pairs")
    return LtiSystem("zpk", (zz, pp, kk), _dt(dt))


def _conjugate_pairs(r: np.ndarray) -> bool:
    poly = np.poly(r)
    return bool(np.allclose(poly.imag, 0, atol=1e-9 * max(1.0, float(np.abs(poly).max()))))


def ss(a: object, b: object, c: object, d: object, dt: float = 0.0) -> LtiSystem:
    A, B, C, D = (_mat(n, v) for n, v in (("A", a), ("B", b), ("C", c), ("D", d)))
    n = A.shape[0]
    if A.shape != (n, n):
        raise DimensionError(f"A must be square, got {A.shape[0]}x{A.shape[1]}")
    if B.shape[0] != n or C.shape[1] != n:
        raise DimensionError("B must have as many rows and C as many columns as A")
    if D.shape != (C.shape[0], B.shape[1]):
        if D.size == 1 and D[0, 0] == 0:
            D = np.zeros((C.shape[0], B.shape[1]))
            D.setflags(write=False)
        else:
            raise DimensionError(f"D must be {C.shape[0]}x{B.shape[1]}")
    return LtiSystem("ss", (A, B, C, D), _dt(dt))


def _from_control(obj: Any, form: str) -> LtiSystem:
    ct = _ct()
    raw_dt = getattr(obj, "dt", 0)
    dt = -1.0 if raw_dt is True else float(raw_dt or 0)
    if form == "ss":
        s = ct.ss(obj)
        return ss(s.A, s.B, s.C, s.D, dt=dt)
    t = ct.tf(obj)
    if t.ninputs != 1 or t.noutputs != 1:
        raise NotSupportedError("MIMO systems can only be kept in state-space form")
    num, den = np.atleast_1d(np.squeeze(t.num[0][0])), np.atleast_1d(np.squeeze(t.den[0][0]))
    if form == "tf":
        return tf(num, den, dt=dt)
    z, p = np.roots(num) if num.size > 1 else np.array([]), np.roots(den)
    lead = _trim(num)[0] / _trim(den)[0]
    return zpk(_clean(z), _clean(p), float(lead), dt=dt)


def _clean(r: np.ndarray) -> np.ndarray:
    r = np.asarray(r, dtype=np.complex128)
    return r.real if not np.any(np.abs(r.imag) > 1e-12 * np.maximum(1, np.abs(r))) else r


def to_tf(sys: LtiSystem) -> LtiSystem:
    return sys if sys.form == "tf" else _from_control(sys.to_control(), "tf")


def to_zpk(sys: LtiSystem) -> LtiSystem:
    return sys if sys.form == "zpk" else _from_control(sys.to_control(), "zpk")


def to_ss(sys: LtiSystem) -> LtiSystem:
    return sys if sys.form == "ss" else _from_control(sys.to_control(), "ss")


def _as_system(v: object, like: LtiSystem) -> LtiSystem:
    if isinstance(v, LtiSystem):
        return v
    gain = float(np.asarray(v, dtype=float).reshape(-1)[0])
    return tf([gain], [1.0], dt=like.dt)


def _check_dt(a: LtiSystem, b: LtiSystem) -> None:
    if a.dt != b.dt and (0 in (a.dt, b.dt) or -1 not in (a.dt, b.dt)):
        raise ValidationError("cannot combine systems with different sample times")


def _combine(a: LtiSystem, b: LtiSystem, obj: Any) -> LtiSystem:
    form = a.form if _RANK[a.form] >= _RANK[b.form] else b.form
    return _from_control(obj, form)


def series(a: object, b: object) -> LtiSystem:
    """b * a (a first, then b), as MATLAB's series(a, b)."""
    sa = a if isinstance(a, LtiSystem) else _as_system(a, b)  # type: ignore[arg-type]
    sb = _as_system(b, sa)
    _check_dt(sa, sb)
    return _combine(sa, sb, sb.to_control() * sa.to_control())


def parallel(a: object, b: object) -> LtiSystem:
    sa = a if isinstance(a, LtiSystem) else _as_system(a, b)  # type: ignore[arg-type]
    sb = _as_system(b, sa)
    _check_dt(sa, sb)
    return _combine(sa, sb, sa.to_control() + sb.to_control())


def feedback(g: object, h: object = 1.0, sign: int = -1) -> LtiSystem:
    """Closed loop g / (1 - sign*g*h); ``sign`` -1 (default) is negative feedback."""
    if sign not in (-1, 1):
        raise ValidationError("feedback sign must be -1 or +1")
    sg = g if isinstance(g, LtiSystem) else _as_system(g, h)  # type: ignore[arg-type]
    sh = _as_system(h, sg)
    _check_dt(sg, sh)
    return _combine(sg, sh, _ct().feedback(sg.to_control(), sh.to_control(), sign))


def negate(sys: LtiSystem) -> LtiSystem:
    return _from_control(-sys.to_control(), sys.form)


def poles(sys: LtiSystem) -> np.ndarray:
    if sys.form == "zpk":
        return np.array(sys.data[1])
    if sys.form == "tf":
        return np.roots(sys.data[1]) if sys.data[1].size > 1 else np.array([])
    return np.linalg.eigvals(sys.data[0])


def zeros(sys: LtiSystem) -> np.ndarray:
    _siso(sys, "zero")
    if sys.form == "zpk":
        return np.array(sys.data[0])
    num = to_tf(sys).data[0]
    return np.roots(num) if num.size > 1 else np.array([])


def dcgain(sys: LtiSystem) -> np.ndarray | float:
    g = np.asarray(_ct().dcgain(sys.to_control()), dtype=float)
    return float(g) if g.size == 1 else g


def is_stable(sys: LtiSystem) -> bool:
    p = poles(sys)
    if p.size == 0:
        return True
    if sys.is_discrete:
        return bool(np.all(np.abs(p) < 1 - 1e-12))
    return bool(np.all(np.real(p) < -1e-12 * max(1.0, float(np.max(np.abs(p))))))


def damp(sys: LtiSystem) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(natural frequencies, damping ratios, poles), sorted by frequency as MATLAB."""
    p = poles(sys).astype(complex)
    if sys.is_discrete:
        ts = 1.0 if sys.dt == -1 else sys.dt
        s = np.log(p.astype(complex)) / ts
    else:
        s = p
    wn = np.abs(s)
    with np.errstate(divide="ignore", invalid="ignore"):
        zeta = np.where(wn > 0, -np.real(s) / wn, -1.0)
    order = np.argsort(wn, kind="stable")
    return wn[order], zeta[order], p[order]


def _siso(sys: LtiSystem, who: str) -> None:
    if not sys.is_siso:
        raise NotSupportedError(f"{who}: only single-input single-output systems are supported")


# ------------------------------------------------------------------------ time responses
def _final_time(sys: LtiSystem) -> float:
    p = poles(sys)
    if sys.is_discrete:
        ts = 1.0 if sys.dt == -1 else sys.dt
        mags = np.abs(p[np.abs(p) > 0])
        slow = float(np.max(mags)) if mags.size else 0.5
        if slow >= 1:
            n = 100
        else:  # until the slowest pole has decayed to 1%
            n = min(1000, max(20, int(math.ceil(math.log(0.01) / math.log(slow)))))
        return n * ts
    re = -np.real(p)
    re = re[re > 1e-9]
    osc = np.abs(np.imag(p))
    t = 7.0 / float(np.min(re)) if re.size else 10.0
    if np.any(osc > 0):
        t = max(t, 4 * 2 * math.pi / float(np.max(osc)))
    return float(min(max(t, 1e-3), 1e5))


def _times(sys: LtiSystem, t: object) -> np.ndarray:
    if t is None:
        tf_ = _final_time(sys)
    else:
        arr = _vec("t", t, allow_empty=False)
        if arr.size > 1:
            if np.any(np.diff(arr) <= 0):
                raise ValidationError("t: times must be increasing")
            return np.array(arr)
        tf_ = float(arr[0])
        if tf_ <= 0:
            raise ValidationError("t: the final time must be positive")
    if sys.is_discrete:
        ts = 1.0 if sys.dt == -1 else sys.dt
        return np.arange(0, tf_ + ts / 2, ts)
    return np.linspace(0, tf_, 1001)


def _response(kind: str, sys: LtiSystem, t: object, x0: object = None
              ) -> tuple[np.ndarray, np.ndarray]:
    _siso(sys, kind)
    ct = _ct()
    times = _times(sys, t)
    obj = sys.to_control()
    if kind == "step":
        r = ct.step_response(obj, T=times)
    elif kind == "impulse":
        r = ct.impulse_response(obj, T=times)
    else:
        if sys.form != "ss":
            raise ValidationError("initial: the system must be in state-space form")
        x = _vec("x0", x0, allow_empty=False)
        if x.size != sys.order:
            raise DimensionError(f"x0 must have {sys.order} elements")
        r = ct.initial_response(obj, T=times, X0=np.array(x))
    return np.asarray(r.time, dtype=float), np.asarray(r.outputs, dtype=float).reshape(-1)


def step(sys: LtiSystem, t: object = None) -> tuple[np.ndarray, np.ndarray]:
    """(t, y) of the unit step response."""
    return _response("step", sys, t)


def impulse(sys: LtiSystem, t: object = None) -> tuple[np.ndarray, np.ndarray]:
    return _response("impulse", sys, t)


def initial(sys: LtiSystem, x0: object, t: object = None) -> tuple[np.ndarray, np.ndarray]:
    return _response("initial", sys, t, x0)


def lsim(sys: LtiSystem, u: object, t: object, x0: object = None
         ) -> tuple[np.ndarray, np.ndarray]:
    """Response to input samples ``u`` at times ``t`` (zero-order hold between samples)."""
    _siso(sys, "lsim")
    times = _vec("t", t, allow_empty=False)
    uu = _vec("u", u, allow_empty=False)
    if uu.size != times.size:
        raise DimensionError("u and t must have the same number of samples")
    if np.any(np.diff(times) <= 0):
        raise ValidationError("t: times must be increasing")
    kw: dict[str, object] = {}
    if x0 is not None:
        kw["X0"] = np.array(_vec("x0", x0))
    r = _ct().forced_response(sys.to_control(), T=np.array(times), U=np.array(uu), **kw)
    return np.asarray(r.time, dtype=float), np.asarray(r.outputs, dtype=float).reshape(-1)


@dataclass(frozen=True)
class StepInfo:
    rise_time: float
    settling_time: float
    settling_min: float
    settling_max: float
    overshoot: float  # percent
    undershoot: float  # percent
    peak: float
    peak_time: float


def stepinfo(sys: LtiSystem, settling: float = 0.02, rise: tuple[float, float] = (0.1, 0.9)
             ) -> StepInfo:
    _siso(sys, "stepinfo")
    if not is_stable(sys):
        nan = float("nan")
        return StepInfo(nan, nan, nan, nan, nan, nan, float("inf"), float("inf"))
    t = _times(sys, _final_time(sys) * 1.5)
    if not sys.is_discrete:
        t = np.linspace(0, t[-1], 20001)
    t, y = step(sys, t)
    yf = float(dcgain(sys))
    i_pk = int(np.argmax(np.abs(y)))
    peak, t_pk = float(abs(y[i_pk])), float(t[i_pk])
    if yf == 0:
        return StepInfo(float("nan"), float("nan"), float(y.min()), float(y.max()), float("nan"),
                        float("nan"), peak, t_pk)
    sgn = math.copysign(1.0, yf)
    yn = y * sgn
    target = abs(yf)
    lo, hi = rise[0] * target, rise[1] * target
    t_lo = _cross(t, yn, lo)
    t_hi = _cross(t, yn, hi)
    outside = np.flatnonzero(np.abs(y - yf) > settling * abs(yf))
    if outside.size == 0:
        ts = 0.0
    elif outside[-1] + 1 < t.size:
        k = outside[-1]
        ts = _interp_time(t, np.abs(y - yf), k, settling * abs(yf))
    else:
        ts = float("nan")
    after = yn[t >= t_hi] if math.isfinite(t_hi) else yn
    overshoot = max(0.0, (float(np.max(yn)) - target) / target * 100)
    undershoot = max(0.0, -float(np.min(yn)) / target * 100)
    settle = after if after.size else yn
    return StepInfo(t_hi - t_lo, ts, float(np.min(settle) * sgn), float(np.max(settle) * sgn),
                    overshoot, undershoot, peak, t_pk)


def _cross(t: np.ndarray, y: np.ndarray, level: float) -> float:
    idx = np.flatnonzero(y >= level)
    if idx.size == 0:
        return float("nan")
    k = int(idx[0])
    if k == 0:
        return float(t[0])
    y0, y1 = y[k - 1], y[k]
    return float(t[k - 1] + (level - y0) * (t[k] - t[k - 1]) / (y1 - y0))


def _interp_time(t: np.ndarray, err: np.ndarray, k: int, band: float) -> float:
    e0, e1 = err[k], err[k + 1]
    if e0 == e1:
        return float(t[k + 1])
    return float(t[k] + (e0 - band) * (t[k + 1] - t[k]) / (e0 - e1))


# ------------------------------------------------------------------- frequency responses
def _freqs(sys: LtiSystem, w: object) -> np.ndarray:
    if w is not None:
        arr = _vec("w", w, allow_empty=False)
        if np.any(arr <= 0):
            raise ValidationError("w: frequencies must be positive")
        return np.array(arr)
    p = np.abs(np.concatenate([poles(sys), zeros(sys)]))
    if sys.is_discrete:
        ts = 1.0 if sys.dt == -1 else sys.dt
        return np.logspace(-3, math.log10(math.pi / ts), 500) if sys.dt > 0 else np.logspace(
            -3, math.log10(math.pi), 500)
    p = p[p > 0]
    lo = float(np.min(p)) / 100 if p.size else 0.01
    hi = float(np.max(p)) * 100 if p.size else 100.0
    return np.logspace(math.log10(lo), math.log10(hi), 500)


def bode(sys: LtiSystem, w: object = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(magnitude (absolute), phase (degrees, unwrapped), w (rad/s))."""
    _siso(sys, "bode")
    ws = _freqs(sys, w)
    h = np.asarray(_ct().frequency_response(sys.to_control(), ws).complex).reshape(-1)
    phase = np.degrees(np.unwrap(np.angle(h)))
    return np.abs(h), phase, ws


def nyquist(sys: LtiSystem, w: object = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(real part, imaginary part, w) of G(jw) for positive w."""
    _siso(sys, "nyquist")
    ws = _freqs(sys, w)
    h = np.asarray(_ct().frequency_response(sys.to_control(), ws).complex).reshape(-1)
    return h.real.copy(), h.imag.copy(), ws


def margin(sys: LtiSystem) -> tuple[float, float, float, float]:
    """(gain margin (absolute), phase margin (deg), w at phase -180, w at gain 1);
    ``inf``/``nan`` where a crossing does not exist, as MATLAB."""
    _siso(sys, "margin")
    r = _ct().stability_margins(sys.to_control())  # (gm, pm, sm, w_phase180, w_gain1, w_sm)
    gm, pm, wcg, wcp = (float(v) if v is not None else float("nan")
                        for v in (r[0], r[1], r[3], r[4]))
    if math.isinf(gm) and math.isnan(wcg):
        wcg = math.inf  # no phase crossover: MATLAB reports Gm = Inf at Wcg = Inf
    if math.isinf(pm) and math.isnan(wcp):
        wcp = math.inf
    return gm, pm, wcg, wcp


def c2d(sys: LtiSystem, ts: float, method: str = "zoh") -> LtiSystem:
    if sys.is_discrete:
        raise ValidationError("c2d: the system is already discrete")
    if not (math.isfinite(ts) and ts > 0):
        raise ValidationError("c2d: the sample time must be positive")
    methods = {"zoh": "zoh", "foh": "foh", "tustin": "bilinear", "matched": "matched",
               "impulse": "impulse"}
    if method not in methods:
        raise ValidationError(f"c2d: method must be one of {', '.join(methods)}")
    obj = _ct().sample_system(sys.to_control(), ts, method=methods[method])
    return _from_control(obj, sys.form)


def rlocus(sys: LtiSystem, gains: object = None) -> tuple[np.ndarray, np.ndarray]:
    """(closed-loop roots, one row per gain; gains) of 1 + k*G = 0."""
    _siso(sys, "rlocus")
    kw = {} if gains is None else {"gains": np.array(_vec("k", gains, allow_empty=False))}
    data = _ct().root_locus_map(sys.to_control(), **kw)
    return np.asarray(data.loci), np.asarray(data.gains, dtype=float)


# --------------------------------------------------------------------------------- PID
def pid(kp: float = 1.0, ki: float = 0.0, kd: float = 0.0, tf_: float = 0.0,
        dt: float = 0.0) -> LtiSystem:
    """Parallel PID C(s) = Kp + Ki/s + Kd s / (Tf s + 1) as a transfer function."""
    for name, v in (("Kp", kp), ("Ki", ki), ("Kd", kd), ("Tf", tf_)):
        if not math.isfinite(v):
            raise ValidationError(f"pid: {name} must be finite")
    if tf_ < 0:
        raise ValidationError("pid: Tf must be non-negative")
    if dt:
        raise NotSupportedError("pid: discrete PID controllers are not supported yet; use c2d")
    if kd and tf_:  # Kp + Ki/s + Kd s/(Tf s + 1)
        if ki:
            return tf([kp * tf_ + kd, kp + ki * tf_, ki], [tf_, 1.0, 0.0])
        return tf([kp * tf_ + kd, kp], [tf_, 1.0])
    if kd:  # ideal derivative: improper, as MATLAB's tf(pid(Kp, Ki, Kd))
        return tf([kd, kp, ki], [1.0, 0.0]) if ki else tf([kd, kp], [1.0])
    if ki:
        return tf([kp, ki], [1.0, 0.0])
    return tf([kp], [1.0])


def pidstd(kp: float = 1.0, ti: float = math.inf, td: float = 0.0, n: float = math.inf
           ) -> LtiSystem:
    """Standard form Kp (1 + 1/(Ti s) + Td s / (Td/N s + 1))."""
    if ti <= 0 or td < 0 or n <= 0:
        raise ValidationError("pidstd: need Ti > 0, Td >= 0 and N > 0")
    ki = 0.0 if math.isinf(ti) else kp / ti
    kd = kp * td
    tf_ = 0.0 if (td == 0 or math.isinf(n)) else td / n
    return pid(kp, ki, kd, tf_)


@dataclass(frozen=True)
class PidInfo:
    kind: str
    kp: float
    ki: float
    kd: float
    tf: float
    crossover: float
    phase_margin: float
    stable: bool


def pidtune(plant: LtiSystem, kind: str = "PID", wc: float | None = None,
            phase_margin: float = 60.0) -> tuple[LtiSystem, PidInfo]:
    """Tune a P, PI, PD or PID controller for ``plant`` by loop shaping: open-loop gain 1 and
    phase -180 + ``phase_margin`` at the crossover ``wc`` (searched if None)."""
    _siso(plant, "pidtune")
    if plant.is_discrete:
        raise NotSupportedError("pidtune: discrete plants are not supported yet")
    kind = kind.upper()
    if kind not in ("P", "PI", "PD", "PID"):
        raise ValidationError("pidtune: type must be 'P', 'PI', 'PD' or 'PID'")
    if not 5 <= phase_margin <= 90:
        raise ValidationError("pidtune: the phase margin must be between 5 and 90 degrees")
    candidates = [float(wc)] if wc is not None else list(np.logspace(-4, 4, 400) * _scale(plant))
    best: tuple[LtiSystem, PidInfo] | None = None
    for w in candidates:
        design = _pid_at(plant, kind, w, phase_margin)
        if design is None:
            continue
        ctrl, info = design
        loop = series(ctrl, plant)
        cl = feedback(loop, 1.0)
        if not is_stable(cl):
            continue
        gm = margin(loop)[0]
        if wc is None and math.isfinite(gm) and gm < 2.0:  # want >= 6 dB gain margin
            continue
        best = (ctrl, PidInfo(info.kind, info.kp, info.ki, info.kd, info.tf, w,
                              phase_margin, True))
    if best is None:
        raise ValidationError(
            f"pidtune: no stabilizing {kind} controller found"
            + (f" at wc = {wc:g}" if wc is not None else "") + "; try another type or wc")
    return best


_X_GRID = np.logspace(-3, 3, 3001)


def _shape(kind: str, x: np.ndarray | float) -> np.ndarray | complex:
    """C(jw)/Kp as a function of x = w Td (Ti = 4 Td for PID, filter Td/10)."""
    deriv = 1j * x / (1 + 1j * x / 10)
    if kind == "PD":
        return 1 + deriv
    return 1 + 1 / (1j * 4 * x) + deriv


def _solve_td(kind: str, need: float) -> float | None:
    """Smallest x = w Td whose controller phase equals ``need`` (within 0.25 degree)."""
    phase = np.angle(_shape(kind, _X_GRID))
    err = np.abs(phase - need)
    k = int(np.argmax(err < math.radians(0.25))) if np.any(err < math.radians(0.25)) else -1
    if k < 0:
        return None
    lo, hi = max(k - 1, 0), min(k + 1, _X_GRID.size - 1)  # refine by bisection
    a, b = float(_X_GRID[lo]), float(_X_GRID[hi])
    fa = float(np.angle(_shape(kind, a))) - need
    for _ in range(60):
        m = math.sqrt(a * b)
        fm = float(np.angle(_shape(kind, m))) - need
        if (fm > 0) == (fa > 0):
            a, fa = m, fm
        else:
            b = m
    return math.sqrt(a * b)


def _scale(plant: LtiSystem) -> float:
    p = np.abs(poles(plant))
    p = p[p > 0]
    return float(np.median(p)) if p.size else 1.0


def _pid_at(plant: LtiSystem, kind: str, w: float, pm: float
            ) -> tuple[LtiSystem, PidInfo] | None:
    g = complex(np.asarray(_ct().frequency_response(plant.to_control(), [w]).complex
                           ).reshape(-1)[0])
    if abs(g) == 0 or not np.isfinite(g):
        return None
    need = math.radians(-180.0 + pm) - math.atan2(g.imag, g.real)  # controller phase needed
    need = (need + math.pi) % (2 * math.pi) - math.pi
    kp = ki = kd = tf_ = 0.0
    if kind == "P":
        if abs(need) > math.radians(2):
            return None
        kp = 1 / abs(g)
    elif kind == "PI":  # phase -atan(1/(w Ti)) in (-90, 0)
        if not -math.pi / 2 < need < 0:
            return None
        ti = 1 / (w * math.tan(-need))
        mag = math.sqrt(1 + 1 / (w * ti) ** 2)
        kp = 1 / (abs(g) * mag)
        ki = kp / ti
    else:  # PD, or PID with Ti = 4 Td; derivative filter Tf = Td/10 included exactly
        x = _solve_td(kind, need)  # x = w * Td
        if x is None:
            return None
        td = x / w
        c1 = _shape(kind, x)  # controller with Kp = 1 at s = jw
        kp = 1 / (abs(g) * abs(c1))
        kd, tf_ = kp * td, td / 10
        ki = kp / (4 * td) if kind == "PID" else 0.0
    ctrl = pid(kp, ki, kd, tf_)
    return ctrl, PidInfo(kind, kp, ki, kd, tf_, w, pm, True)
