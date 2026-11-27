"""Nonlinear and control blocks (Phase 7, S9-S10): Saturation, DeadZone, Relay, Switch, Fcn,
PIDController, TransportDelay.

Differences from Simulink:
- Relay switches only at accepted solver steps (no zero-crossing location); keep MaxStep small
  for sharp switching.
- Fcn evaluates a MATLAB-style expression of ``u`` (``u`` or ``u(1)``, ``u(2)``, ...) and ``t``
  with + - * / ^, parentheses and the functions sin cos tan asin acos atan exp log log10 sqrt
  abs sign sinh cosh tanh atan2 min max; it is checked when the model is compiled and never
  executes arbitrary code.
- PIDController is the parallel form P + I/s + D*N*s/(s + N) with optional output limits (no
  anti-windup, no discrete form yet).
- TransportDelay interpolates its stored input history; before the delay has elapsed it
  outputs InitialOutput. The runner keeps solver steps no longer than the delay.
"""

from __future__ import annotations

import ast
import math
import re

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, BlockType, ParamSpec, register

__all__ = ["NONLINEAR_TYPES", "compile_expression"]


def _one(n: int):
    return lambda p: n


class _Saturation(BlockImpl):
    def outputs(self, t, x, u):
        return [np.clip(u[0], self.p["LowerLimit"], self.p["UpperLimit"])]


class _DeadZone(BlockImpl):
    def outputs(self, t, x, u):
        lo, hi = self.p["Start"], self.p["End"]
        v = u[0]
        return [np.where(v > hi, v - hi, np.where(v < lo, v - lo, 0.0))]


class _Relay(BlockImpl):
    def __init__(self, p):
        super().__init__(p)
        self.on = bool(p["InitiallyOn"])

    def outputs(self, t, x, u):
        return [np.atleast_1d(self.p["OnValue"] if self.on else self.p["OffValue"]).astype(float)]

    def after_step(self, t, x, u):
        v = float(np.atleast_1d(u[0])[0])
        if not self.on and v >= self.p["OnPoint"]:
            self.on = True
        elif self.on and v <= self.p["OffPoint"]:
            self.on = False

    def memory(self):
        return self.on

    def restore(self, snapshot):
        self.on = bool(snapshot)


class _Switch(BlockImpl):
    def outputs(self, t, x, u):
        c, th = u[1], self.p["Threshold"]
        crit = self.p["Criteria"]
        if crit == "u2>=Threshold":
            first = np.all(c >= th)
        elif crit == "u2>Threshold":
            first = np.all(c > th)
        else:
            first = np.all(c != 0)
        return [u[0] if first else u[2]]


# ------------------------------------------------------------------------------------ Fcn
_FUNCS = {"sin": np.sin, "cos": np.cos, "tan": np.tan, "asin": np.arcsin, "acos": np.arccos,
          "atan": np.arctan, "exp": np.exp, "log": np.log, "log10": np.log10, "sqrt": np.sqrt,
          "abs": np.abs, "sign": np.sign, "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
          "atan2": np.arctan2, "min": np.minimum, "max": np.maximum}
_CONST = {"pi": math.pi, "e": math.e}
_OK_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
             ast.Constant, ast.Subscript, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
             ast.USub, ast.UAdd)


def compile_expression(text: str):
    """MATLAB-style expression of u and t -> function(t, u_vector) -> float."""
    src = text.strip()
    if not src:
        raise ValidationError("Fcn: the expression is empty")
    src = re.sub(r"\bu\s*\(\s*(\d+)\s*\)", lambda m: f"u[{int(m.group(1)) - 1}]", src)
    src = src.replace("^", "**").replace(".*", "*").replace("./", "/")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        raise ValidationError(f"Fcn: cannot read the expression {text!r}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _OK_NODES):
            raise ValidationError(f"Fcn: {type(node).__name__} is not allowed in {text!r}")
        if isinstance(node, ast.Name) and node.id not in {"u", "t", *_FUNCS, *_CONST}:
            raise ValidationError(f"Fcn: unknown name {node.id!r} (use u, u(1), t, pi)")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name)
                                               and node.func.id in _FUNCS):
            raise ValidationError(f"Fcn: only these functions are allowed: {', '.join(_FUNCS)}")
        if isinstance(node, ast.Subscript) and not (
                isinstance(node.value, ast.Name) and node.value.id == "u"
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int)):
            raise ValidationError(f"Fcn: only u(1), u(2), ... can be indexed in {text!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, int | float):
            raise ValidationError(f"Fcn: only numbers are allowed as constants in {text!r}")
    code = compile(tree, "<Fcn>", "eval")
    env = {"__builtins__": {}, **_FUNCS, **_CONST}

    def fn(t: float, u: np.ndarray) -> float:
        uu = np.atleast_1d(u)
        scope = {**env, "t": t, "u": uu if uu.size > 1 else float(uu[0])}
        try:
            with np.errstate(all="ignore"):
                return float(eval(code, scope))  # noqa: S307 (AST checked above)
        except IndexError:
            raise ValidationError(f"Fcn: {text!r} indexes beyond the input width "
                                  f"{uu.size}") from None
    return fn


class _Fcn(BlockImpl):
    def __init__(self, p):
        super().__init__(p)
        self.fn = compile_expression(p["Expression"])

    def outputs(self, t, x, u):
        return [np.array([self.fn(t, u[0])])]


def _check_fcn(block: str, p: dict) -> None:
    try:
        compile_expression(p["Expression"])
    except ValidationError as exc:
        raise ValidationError(f"block {block}: {exc}") from None


# ------------------------------------------------------------------------------- control
class _PID(BlockImpl):
    n_states = 2  # integral of e, derivative filter state

    def outputs(self, t, x, u):
        p = self.p
        e = float(np.atleast_1d(u[0])[0])
        y = p["P"] * e + p["I"] * x[0] + p["D"] * p["N"] * (e - x[1])
        return [np.array([min(max(y, p["LowerLimit"]), p["UpperLimit"])])]

    def derivatives(self, t, x, u):
        e = float(np.atleast_1d(u[0])[0])
        return np.array([e, self.p["N"] * (e - x[1])])


class _TransportDelay(BlockImpl):
    def __init__(self, p):
        super().__init__(p)
        self.delay = float(p["DelayTime"])
        self.hist_t: list[float] = []
        self.hist_u: list[float] = []

    def outputs(self, t, x, u):
        td = t - self.delay
        if not self.hist_t or td < self.hist_t[0]:
            return [np.array([self.p["InitialOutput"]])]
        return [np.array([np.interp(td, self.hist_t, self.hist_u)])]

    def after_step(self, t, x, u):
        if self.hist_t and t <= self.hist_t[-1]:
            return
        self.hist_t.append(t)
        self.hist_u.append(float(np.atleast_1d(u[0])[0]))

    def memory(self):
        return len(self.hist_t)

    def restore(self, snapshot):
        n = int(snapshot)  # type: ignore[arg-type]
        del self.hist_t[n:], self.hist_u[n:]


def _check_limits(lo: str, hi: str):
    def check(block: str, p: dict) -> None:
        if not p[lo] < p[hi]:
            raise ValidationError(f"block {block}: {lo} must be below {hi}")
    return check


def _check_relay(block: str, p: dict) -> None:
    if p["OffPoint"] > p["OnPoint"]:
        raise ValidationError(f"block {block}: OffPoint must not exceed OnPoint")


def _check_pid(block: str, p: dict) -> None:
    if p["N"] <= 0:
        raise ValidationError(f"block {block}: filter coefficient N must be positive")
    _check_limits("LowerLimit", "UpperLimit")(block, p)


NONLINEAR_TYPES = tuple(register(bt) for bt in (
    BlockType("Saturation", "Discontinuities", "algebraic",
              (ParamSpec("UpperLimit", 0.5), ParamSpec("LowerLimit", -0.5)),
              _one(1), _one(1), True, _Saturation, "Limits the input to [LowerLimit, UpperLimit].",
              _check_limits("LowerLimit", "UpperLimit")),
    BlockType("DeadZone", "Discontinuities", "algebraic",
              (ParamSpec("Start", -0.5), ParamSpec("End", 0.5)),
              _one(1), _one(1), True, _DeadZone, "Zero output between Start and End.",
              _check_limits("Start", "End")),
    BlockType("Relay", "Discontinuities", "algebraic",
              (ParamSpec("OnPoint", 0.0), ParamSpec("OffPoint", 0.0), ParamSpec("OnValue", 1.0),
               ParamSpec("OffValue", 0.0), ParamSpec("InitiallyOn", 0.0)),
              _one(1), _one(1), False, _Relay,
              "Switches to OnValue when the input reaches OnPoint, back at OffPoint.",
              _check_relay),
    BlockType("Switch", "Signal Routing", "algebraic",
              (ParamSpec("Threshold", 0.0),
               ParamSpec("Criteria", "u2>=Threshold", "choice",
                         ("u2>=Threshold", "u2>Threshold", "u2~=0"))),
              _one(3), _one(1), True, _Switch,
              "Passes input 1 when input 2 meets the criterion, otherwise input 3."),
    BlockType("Fcn", "User-Defined Functions", "algebraic",
              (ParamSpec("Expression", "u", "text"),), _one(1), _one(1), True, _Fcn,
              "Evaluates an expression of u (u(1), u(2), ...) and t, e.g. 'u(1)^2 + sin(t)'.",
              _check_fcn),
    BlockType("PIDController", "Continuous", "continuous",
              (ParamSpec("P", 1.0), ParamSpec("I", 0.0), ParamSpec("D", 0.0),
               ParamSpec("N", 100.0), ParamSpec("UpperLimit", math.inf),
               ParamSpec("LowerLimit", -math.inf)),
              _one(1), _one(1), True, _PID,
              "u = P e + I integral(e) + D N s/(s+N) e, with optional output limits.", _check_pid),
    BlockType("TransportDelay", "Continuous", "continuous",
              (ParamSpec("DelayTime", 1.0, positive=True), ParamSpec("InitialOutput", 0.0)),
              _one(1), _one(1), False, _TransportDelay,
              "Output = input DelayTime seconds ago (InitialOutput before that)."),
))
