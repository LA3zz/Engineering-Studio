"""Continuous-time blocks (Phase 7, S4): Integrator, TransferFcn, StateSpace, Derivative.

Each block owns a slice of the continuous state vector: ``initial_state()`` gives its start
values, ``derivatives(t, x, u)`` its rates and ``outputs(t, x, u)`` its outputs. Blocks whose
output does not depend on the current input (Integrator, strictly proper TransferFcn,
StateSpace with D = 0) are not direct feedthrough; that is what breaks feedback loops in the
compiler (S5).

Differences from Simulink:
- Integrator limits clamp the output and stop integration in the limiting direction (no reset
  ports or state ports yet).
- TransferFcn uses its own controllable canonical realisation (no python-control import); it
  must be proper (numerator degree <= denominator degree).
- Derivative is the filtered derivative s / (s/c + 1) with coefficient c (default 1000,
  i.e. a 1 ms time constant), which is what Simulink uses when it linearises the block; an
  exact derivative of solver trial points is not computed.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, BlockType, ParamSpec, register

__all__ = ["CONTINUOUS_TYPES", "tf_to_ss"]


def _fixed(n: int):
    return lambda p: n


def tf_to_ss(num: np.ndarray, den: np.ndarray
             ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Controllable canonical form of num(s)/den(s) (coefficients highest power first)."""
    num = np.trim_zeros(np.asarray(num, dtype=float), "f")
    den = np.trim_zeros(np.asarray(den, dtype=float), "f")
    if den.size == 0:
        raise ValidationError("TransferFcn: the denominator must not be zero")
    if num.size == 0:
        num = np.zeros(1)
    if num.size > den.size:
        raise ValidationError("TransferFcn: improper transfer function (numerator degree "
                              "higher than denominator degree)")
    num, den = num / den[0], den / den[0]
    n = den.size - 1
    b = np.concatenate([np.zeros(den.size - num.size), num])
    d = b[0]
    if n == 0:
        return np.zeros((0, 0)), np.zeros((0, 1)), np.zeros((1, 0)), np.array([[d]])
    A = np.zeros((n, n))
    A[0, :] = -den[1:]
    A[1:, :-1] = np.eye(n - 1)
    B = np.zeros((n, 1))
    B[0, 0] = 1.0
    C = (b[1:] - den[1:] * d).reshape(1, n)
    return A, B, C, np.array([[d]])


class _Integrator(BlockImpl):
    def __init__(self, p):
        super().__init__(p)
        self.x0 = np.atleast_1d(p["InitialCondition"]).astype(float)
        self.n_states = self.x0.size
        self.lo, self.hi = p["LowerLimit"], p["UpperLimit"]

    def initial_state(self):
        return np.clip(self.x0.copy(), self.lo, self.hi)

    def outputs(self, t, x, u):
        return [np.clip(x, self.lo, self.hi)]

    def derivatives(self, t, x, u):
        dx = np.broadcast_to(u[0], x.shape).astype(float).copy()
        dx[(x >= self.hi) & (dx > 0)] = 0.0  # held at a limit
        dx[(x <= self.lo) & (dx < 0)] = 0.0
        return dx


class _StateSpaceImpl(BlockImpl):
    def __init__(self, p, A, B, C, D, x0):
        super().__init__(p)
        self.A, self.B, self.C, self.D = A, B, C, D
        self.x0 = x0
        self.n_states = A.shape[0]

    def initial_state(self):
        return self.x0.copy()

    def _u(self, u):
        v = np.atleast_1d(u[0]).astype(float)
        m = self.B.shape[1]
        if v.size == 1 and m > 1:
            v = np.full(m, v[0])
        if v.size != m:
            raise ValidationError(f"state-space block expects an input of width {m}, got "
                                  f"{v.size}")
        return v

    def outputs(self, t, x, u):
        if not u:  # not direct feedthrough (D = 0): the runner passes no input here
            return [self.C @ x]
        return [self.C @ x + self.D @ self._u(u)]

    def derivatives(self, t, x, u):
        return self.A @ x + self.B @ self._u(u)


def _transfer_fcn(p):
    A, B, C, D = tf_to_ss(p["Num"], p["Den"])
    return _StateSpaceImpl(p, A, B, C, D, np.zeros(A.shape[0]))


def _state_space(p):
    A, B, C, D = p["A"], p["B"], p["C"], p["D"]
    x0 = np.atleast_1d(p["X0"]).astype(float)
    if x0.size == 1 and A.shape[0] > 1:
        x0 = np.full(A.shape[0], x0[0])
    return _StateSpaceImpl(p, A, B, C, D, x0)


def _derivative(p):
    c = p["Coefficient"]  # s/(s/c + 1) = c - c^2/(s + c)
    return _StateSpaceImpl(p, np.array([[-c]]), np.array([[1.0]]), np.array([[-c * c]]),
                           np.array([[c]]), np.zeros(1))


def _check_integrator(block: str, p: dict) -> None:
    if not p["LowerLimit"] < p["UpperLimit"]:
        raise ValidationError(f"block {block}: LowerLimit must be below UpperLimit")


def _check_tf(block: str, p: dict) -> None:
    try:
        tf_to_ss(p["Num"], p["Den"])
    except ValidationError as exc:
        raise ValidationError(f"block {block}: {exc}") from None


def _check_ss(block: str, p: dict) -> None:
    A, B, C, D = p["A"], p["B"], p["C"], p["D"]
    n = A.shape[0]
    if A.shape != (n, n):
        raise ValidationError(f"block {block}: A must be square")
    if B.shape[0] != n or C.shape[1] != n or D.shape != (C.shape[0], B.shape[1]):
        raise ValidationError(f"block {block}: B must have {n} rows, C {n} columns and D be "
                              f"{C.shape[0]}x{B.shape[1]}")
    x0 = np.atleast_1d(p["X0"])
    if x0.size not in (1, n):
        raise ValidationError(f"block {block}: X0 must have {n} elements")


def _tf_feedthrough(p: dict) -> bool:
    num = np.trim_zeros(np.asarray(p["Num"], dtype=float), "f")
    den = np.trim_zeros(np.asarray(p["Den"], dtype=float), "f")
    return num.size == den.size and num.size > 0


CONTINUOUS_TYPES = tuple(register(bt) for bt in (
    BlockType("Integrator", "Continuous", "continuous",
              (ParamSpec("InitialCondition", 0.0, "vector"),
               ParamSpec("UpperLimit", float("inf")), ParamSpec("LowerLimit", float("-inf"))),
              _fixed(1), _fixed(1), False, _Integrator,
              "Output = integral of the input + InitialCondition (optional limits).",
              _check_integrator),
    BlockType("TransferFcn", "Continuous", "continuous",
              (ParamSpec("Num", [1.0], "vector"), ParamSpec("Den", [1.0, 1.0], "vector")),
              _fixed(1), _fixed(1), _tf_feedthrough, _transfer_fcn,
              "Num(s)/Den(s), coefficients in descending powers of s.", _check_tf),
    BlockType("StateSpace", "Continuous", "continuous",
              (ParamSpec("A", [[-1.0]], "matrix"), ParamSpec("B", [[1.0]], "matrix"),
               ParamSpec("C", [[1.0]], "matrix"), ParamSpec("D", [[0.0]], "matrix"),
               ParamSpec("X0", 0.0, "vector")),
              _fixed(1), _fixed(1), lambda p: bool(np.any(p["D"] != 0)), _state_space,
              "x' = A x + B u, y = C x + D u (vector input and output).", _check_ss),
    BlockType("Derivative", "Continuous", "continuous",
              (ParamSpec("Coefficient", 1000.0, positive=True),),
              _fixed(1), _fixed(1), True, _derivative,
              "Filtered derivative s/(s/c + 1); larger c is closer to du/dt but stiffer."),
))
