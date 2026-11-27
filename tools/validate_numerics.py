"""Numerical validation report for Engineering Studio.

Runs MATLAB-style snippets through the real in-process kernel (the same interpreter and
builtins the app uses) and compares every result with an independent reference computed here
with NumPy / SciPy / SymPy / math. Nothing is compared against the app's own engine.

Usage (project root, venv active):
    python tools\\validate_numerics.py            full report
    python tools\\validate_numerics.py -v         also show every passing check's details
    python tools\\validate_numerics.py -k ode     only groups/checks whose name contains 'ode'
The report is also written to validation_report.txt. Exit code 1 if any check fails.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sympy as sp
from scipy import integrate, interpolate, linalg, optimize, stats

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics

RNG = np.random.default_rng(20261125)


def m(a) -> str:
    """NumPy array -> MATLAB matrix literal with full precision."""
    a = np.atleast_2d(np.asarray(a, dtype=float))
    return "[" + "; ".join(" ".join(repr(float(x)) for x in row) for row in a) + "]"


@dataclass
class Check:
    group: str
    name: str
    code: str
    var: str
    ref: object
    rtol: float = 1e-9
    atol: float = 1e-10


CHECKS: list[Check] = []


def add(group, name, code, var, ref, rtol=1e-9, atol=1e-10):
    CHECKS.append(Check(group, name, code, var, ref, rtol, atol))


# ======================================================================================
# 1. Linear algebra
# ======================================================================================
def linear_algebra() -> None:
    g = "linear algebra"
    A = RNG.normal(size=(5, 5)) + 3 * np.eye(5)
    B = RNG.normal(size=(5, 5))
    b = RNG.normal(size=(5, 1))
    v = RNG.normal(size=(1, 6))
    u3, v3 = RNG.normal(size=(1, 3)), RNG.normal(size=(1, 3))
    pre = f"A = {m(A)}; B = {m(B)}; b = {m(b)}; v = {m(v)}; "
    add(g, "A\\b", pre + r"x = A\b;", "x", np.linalg.solve(A, b), 1e-9, 1e-10)
    add(g, "A\\B (matrix RHS)", pre + r"X = A\B;", "X", np.linalg.solve(A, B))
    add(g, "b'/A (right division)", pre + "X = b'/A;", "X", np.linalg.solve(A.T, b).T)
    add(g, "inv", pre + "X = inv(A);", "X", np.linalg.inv(A))
    add(g, "det", pre + "d = det(A);", "d", np.linalg.det(A))
    add(g, "rank full", pre + "r = rank(A);", "r", 5)
    add(g, "rank deficient", "r = rank([1 2 3; 2 4 6; 1 0 1]);", "r", 2)
    add(g, "cond (2-norm)", pre + "c = cond(A);", "c", np.linalg.cond(A))
    add(g, "norm matrix 2", pre + "n = norm(A);", "n", np.linalg.norm(A, 2))
    add(g, "norm vector 2", pre + "n = norm(v);", "n", np.linalg.norm(v))
    add(g, "norm vector 1", pre + "n = norm(v, 1);", "n", np.linalg.norm(v.ravel(), 1))
    add(g, "norm vector Inf", pre + "n = norm(v, Inf);", "n", np.linalg.norm(v.ravel(), np.inf))
    add(g, "trace", pre + "t = trace(A);", "t", np.trace(A))
    add(g, "A*B", pre + "C = A*B;", "C", A @ B)
    add(g, "A.*B", pre + "C = A.*B;", "C", A * B)
    add(g, "A'", pre + "C = A';", "C", A.T)
    add(g, "A.^2", pre + "C = A.^2;", "C", A**2)
    add(g, "A^3", pre + "C = A^3;", "C", np.linalg.matrix_power(A, 3))
    add(g, "dot", pre + f"d = dot(v, {m(v)});", "d", float(np.sum(v * v)))
    add(g, "cross", f"c = cross({m(u3)}, {m(v3)});", "c", np.cross(u3, v3))
    add(g, "singular solve raises", r"ok = 0; try, x = [1 2; 2 4]\[1; 2]; catch err, ok = 1; end",
        "ok", 1)
    add(g, "nonsquare inv raises", "ok = 0; try, x = inv([1 2 3]); catch err, ok = 1; end", "ok", 1)
    add(g, "Hilbert 6x6 (cond ~ 1e7) solve",
        "n = 6; H = zeros(n); for i = 1:n, for j = 1:n, H(i,j) = 1/(i+j-1); end, end; "
        "x = H \\ (H * ones(n,1));", "x", np.ones((6, 1)), 1e-6, 1e-6)


# ======================================================================================
# 2. Decompositions and eigenproblems
# ======================================================================================
def decompositions() -> None:
    g = "decompositions"
    A = RNG.normal(size=(5, 5)) + 3 * np.eye(5)
    S = A @ A.T
    R = RNG.normal(size=(6, 4))
    T = np.array([[1.0, 2, 3], [0, 4, 5], [0, 0, 6]])
    pre = f"A = {m(A)}; S = {m(S)}; R = {m(R)}; T = {m(T)}; "
    add(g, "eig symmetric values", pre + "e = eig(S);", "e", np.linalg.eigvalsh(S))
    add(g, "eig symmetric A*V = V*D", pre + "[V, D] = eig(S); r = norm(S*V - V*D);", "r", 0, 0,
        1e-9)
    add(g, "eig symmetric V'V = I", pre + "[V, D] = eig(S); r = norm(V'*V - eye(5));", "r", 0, 0,
        1e-10)
    add(g, "eig triangular (1,4,6)", pre + "e = sort(eig(T));", "e", np.array([1.0, 4, 6]))
    add(g, "eig nonsymmetric A*V = V*D", pre + "[V, D] = eig(T); r = norm(T*V - V*D);", "r", 0,
        0, 1e-9)
    add(g, "eig complex pair (rotation)", "e = sort(imag(eig([0 -1; 1 0])));", "e",
        np.array([-1.0, 1.0]))
    add(g, "svd values", pre + "s = svd(R);", "s", np.linalg.svd(R, compute_uv=False))
    add(g, "svd U*S*V' = R", pre + "[U, S2, V] = svd(R); r = norm(U*S2*V' - R);", "r", 0, 0,
        1e-9)
    add(g, "qr Q*R = A", pre + "[Q, R2] = qr(A); r = norm(Q*R2 - A);", "r", 0, 0, 1e-9)
    add(g, "qr Q'Q = I", pre + "[Q, R2] = qr(A); r = norm(Q'*Q - eye(5));", "r", 0, 0, 1e-10)
    add(g, "lu P*A = L*U", pre + "[L, U, P] = lu(A); r = norm(P*A - L*U);", "r", 0, 0, 1e-10)
    add(g, "chol R'R = S", pre + "R3 = chol(S); r = norm(R3'*R3 - S);", "r", 0, 0, 1e-8)
    add(g, "chol of non-SPD raises",
        "ok = 0; try, chol([1 2; 2 1]); catch err, ok = 1; end", "ok", 1)


# ======================================================================================
# 3. Polynomials, constructors, elementary math, reductions, complex numbers
# ======================================================================================
def basics() -> None:
    g = "polynomials"
    xs = np.linspace(-2, 2, 9)
    p = np.array([2.0, -3, 0, 5, 1])
    add(g, "polyval", f"v = polyval({m(p)}, {m(xs)});", "v", np.polyval(p, xs))
    add(g, "roots (1,2,3)", "r = sort(roots([1 -6 11 -6]));", "r", np.array([1.0, 2, 3]))
    add(g, "roots degree 5 vs numpy", "r = sort(roots([1 -15 85 -225 274 -120]));", "r",
        np.sort(np.roots([1, -15, 85, -225, 274, -120]).real), 1e-8, 1e-8)
    add(g, "roots complex pair", "r = sort(imag(roots([1 0 1])));", "r", np.array([-1.0, 1.0]))
    add(g, "poly from roots", "c = poly([1 2 3]);", "c", np.array([[1.0, -6, 11, -6]]))
    add(g, "poly of matrix (char. polynomial)", "c = poly([2 0; 0 3]);", "c",
        np.array([[1.0, -5, 6]]))
    x = np.arange(0.0, 6)
    y = np.polyval([1.0, -2, 0.5, 3], x)
    add(g, "polyfit exact cubic", f"p = polyfit({m(x)}, {m(y)}, 3);", "p",
        np.array([[1.0, -2, 0.5, 3]]), 1e-8, 1e-8)
    xn = np.linspace(0, 3, 15)
    yn = 1 + 2 * xn - 0.5 * xn**2 + RNG.normal(scale=0.05, size=15)
    add(g, "polyfit noisy quadratic vs numpy", f"p = polyfit({m(xn)}, {m(yn)}, 2);", "p",
        np.polyfit(xn, yn, 2), 1e-8, 1e-8)

    g = "constructors"
    add(g, "linspace", "x = linspace(0, 1, 11);", "x", np.linspace(0, 1, 11))
    add(g, "logspace", "x = logspace(0, 3, 4);", "x", np.logspace(0, 3, 4))
    add(g, "eye/zeros/ones", "x = [eye(2) zeros(2,1); ones(1,3)];", "x",
        np.array([[1.0, 0, 0], [0, 1, 0], [1, 1, 1]]))
    add(g, "repmat", "x = repmat([1 2; 3 4], 2, 2);", "x", np.tile([[1.0, 2], [3, 4]], (2, 2)))
    add(g, "reshape (column-major)", "x = reshape(1:6, 3, 2);", "x",
        np.arange(1.0, 7).reshape(3, 2, order="F"))
    add(g, "diag/triu/tril", "A = [1 2 3; 4 5 6; 7 8 9]; x = [diag(A)' sum(sum(triu(A))) "
        "sum(sum(tril(A)))];", "x", np.array([[1.0, 5, 9, 26, 34]]))
    add(g, "meshgrid", "[X, Y] = meshgrid(1:3, 1:2);", "X", np.meshgrid([1.0, 2, 3], [1.0, 2])[0])
    add(g, "colon with negative step", "x = 10:-3:0;", "x", np.array([[10.0, 7, 4, 1]]))

    g = "elementary math"
    xv = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 0.0, 1.0, -1.0])
    xp = np.array([0.1, 0.5, 1.0, 2.0, 7.5, 10.0])
    pre = f"x = {m(xv)}; p = {m(xp)}; "
    for fn, ref in (("sin", np.sin), ("cos", np.cos), ("tan", np.tan), ("exp", np.exp),
                    ("atan", np.arctan), ("sinh", np.sinh), ("cosh", np.cosh),
                    ("tanh", np.tanh), ("abs", np.abs), ("sign", np.sign),
                    ("floor", np.floor), ("ceil", np.ceil), ("fix", np.trunc)):
        add(g, fn, pre + f"y = {fn}(x);", "y", ref(xv))
    add(g, "round (half away from zero)", pre + "y = round(x);", "y",
        np.sign(xv) * np.floor(np.abs(xv) + 0.5))
    for fn, ref in (("log", np.log), ("log10", np.log10), ("log2", np.log2), ("sqrt", np.sqrt)):
        add(g, fn, pre + f"y = {fn}(p);", "y", ref(xp))
    add(g, "asin/acos", "y = [asin(0.3) acos(0.3)];", "y", np.array([[math.asin(.3),
                                                                      math.acos(.3)]]))
    add(g, "atan2", "y = atan2([1 -1 1 -1], [1 1 -1 -1]);", "y",
        np.arctan2([1.0, -1, 1, -1], [1.0, 1, -1, -1]))
    add(g, "hypot", "y = hypot([3 5 8], [4 12 15]);", "y", np.array([[5.0, 13, 17]]))
    add(g, "mod (sign of divisor)", "y = mod([-7 7 -7 7], [3 3 -3 -3]);", "y",
        np.mod([-7.0, 7, -7, 7], [3.0, 3, -3, -3]))
    add(g, "rem (sign of dividend)", "y = rem([-7 7 -7 7], [3 3 -3 -3]);", "y",
        np.fmod([-7.0, 7, -7, 7], [3.0, 3, -3, -3]))

    g = "complex numbers"
    add(g, "sqrt(-4)", "z = sqrt(-4);", "z", 2j)
    add(g, "abs(3+4i)", "a = abs(3+4i);", "a", 5.0)
    add(g, "Euler identity", "e = exp(1i*pi) + 1;", "e", 0, 0, 1e-12)
    add(g, "complex multiply", "z = (1+2i)*(3-1i);", "z", 5 + 5j)
    add(g, "conj/angle/real/imag", "z = [conj(2+3i) angle(1i) real(2+3i) imag(2+3i)];", "z",
        np.array([[2 - 3j, math.pi / 2, 2, 3]]))

    g = "reductions"
    M = RNG.normal(size=(4, 3))
    w = RNG.normal(size=(1, 7))
    pre = f"M = {m(M)}; w = {m(w)}; "
    for fn, ref in (("sum", np.sum), ("prod", np.prod), ("mean", np.mean),
                    ("cumsum", lambda a: np.cumsum(a, axis=0)),
                    ("cumprod", lambda a: np.cumprod(a, axis=0)),
                    ("max", lambda a: a.max(axis=0)), ("min", lambda a: a.min(axis=0))):
        ref_m = ref(M, axis=0) if fn in ("sum", "prod", "mean") else ref(M)
        add(g, f"{fn} (matrix columns)", pre + f"y = {fn}(M);", "y", ref_m)
    add(g, "sort ascending", pre + "[s, i] = sort(w);", "s", np.sort(w))
    add(g, "sort indices", pre + "[s, i] = sort(w);", "i", np.argsort(w, kind="stable") + 1.0)
    add(g, "max with index", pre + "[v, k] = max(w);", "k", float(np.argmax(w) + 1))
    add(g, "diff", pre + "d = diff(w);", "d", np.diff(w))
    add(g, "find", pre + "k = find(w > 0);", "k", (np.flatnonzero(w[0] > 0) + 1.0).reshape(1, -1))
    add(g, "any/all", "y = [any([0 0 1]) all([1 1 0]) any([]) all([])];", "y",
        np.array([[1.0, 0, 0, 1]]))
    add(g, "logical indexing", pre + "y = w(w > 0.2);", "y", w[w > 0.2].reshape(1, -1))


# ======================================================================================
# 4. Calculus, roots, interpolation
# ======================================================================================
def calculus() -> None:
    g = "integration"
    x = np.linspace(0, 3, 13)
    y = np.sin(x) + 0.1 * x**2
    add(g, "trapz", f"v = trapz({m(x)}, {m(y)});", "v", np.trapezoid(y, x))
    add(g, "cumtrapz", f"v = cumtrapz({m(x)}, {m(y)});", "v",
        integrate.cumulative_trapezoid(y, x, initial=0))
    add(g, "integral x^2 [0,3]", "q = integral(@(x) x.^2, 0, 3);", "q", 9.0, 1e-9, 1e-9)
    add(g, "integral sin^2 [0,pi]", "q = integral(@(x) sin(x).^2, 0, pi);", "q", math.pi / 2,
        1e-8, 1e-8)
    add(g, "integral gaussian (-Inf,Inf)", "q = integral(@(x) exp(-x.^2), -Inf, Inf);", "q",
        math.sqrt(math.pi), 1e-7, 1e-7)
    add(g, "integral oscillatory", "q = integral(@(x) cos(20*x), 0, pi);", "q",
        math.sin(20 * math.pi) / 20, 1e-6, 1e-7)
    add(g, "quad sqrt singularity", "q = quad(@(x) 1./sqrt(x), 0, 1);", "q", 2.0, 1e-6, 1e-6)
    add(g, "integral2 x*y", "q = integral2(@(x, y) x.*y, 0, 1, 0, 2);", "q", 1.0, 1e-8, 1e-8)
    add(g, "integral2 exp(x+y)", "q = integral2(@(x, y) exp(x+y), 0, 1, 0, 1);", "q",
        (math.e - 1) ** 2, 1e-8, 1e-8)

    g = "root finding"
    add(g, "fzero bracket", "x = fzero(@(x) x^3 - 2*x - 5, [2 3]);", "x",
        optimize.brentq(lambda t: t**3 - 2 * t - 5, 2, 3, xtol=1e-14), 1e-10, 1e-10)
    add(g, "fzero from scalar start", "x = fzero(@cos, 1);", "x", math.pi / 2, 1e-10, 1e-10)
    add(g, "fzero exp(x)=3", "x = fzero(@(x) exp(x) - 3, [0 2]);", "x", math.log(3), 1e-10,
        1e-10)
    add(g, "fsolve circle/line", "x = fsolve(@(x) [x(1)^2 + x(2)^2 - 4; x(1) - x(2)], [1; 1]);",
        "x", np.array([[math.sqrt(2)], [math.sqrt(2)]]), 1e-8, 1e-8)
    sol = optimize.fsolve(lambda z: [z[0] ** 2 + z[1] - 7, z[0] - z[1] ** 2 + 1], [2.0, 2.0],
                          xtol=1e-13)
    add(g, "fsolve nonlinear 2x2 vs scipy",
        "x = fsolve(@(x) [x(1)^2 + x(2) - 7; x(1) - x(2)^2 + 1], [2; 2]);", "x",
        sol.reshape(2, 1), 1e-7, 1e-7)

    g = "interpolation"
    xk = np.array([0.0, 1, 2, 4, 5])
    yk = np.array([1.0, 3, 2, 5, 4])
    xq = np.array([0.4, 1.6, 3.1, 4.6])
    pre = f"x = {m(xk)}; y = {m(yk)}; q = {m(xq)}; "
    add(g, "interp1 linear", pre + "v = interp1(x, y, q);", "v", np.interp(xq, xk, yk))
    add(g, "interp1 pchip", pre + "v = interp1(x, y, q, 'pchip');", "v",
        interpolate.PchipInterpolator(xk, yk)(xq))
    add(g, "interp1 spline", pre + "v = interp1(x, y, q, 'spline');", "v",
        interpolate.CubicSpline(xk, yk)(xq))
    add(g, "interp1 nearest", pre + "v = interp1(x, y, q, 'nearest');", "v",
        yk[np.argmin(np.abs(xk[None, :] - xq[:, None]), axis=1)])
    add(g, "interp1 outside with fill value", pre + "v = interp1(x, y, [6 -1], 'linear', 0);",
        "v", np.array([[0.0, 0.0]]))
    gx, gy = np.arange(5.0), np.arange(4.0)
    Z = RNG.normal(size=(4, 5))
    pts = np.array([[0.3, 1.2], [2.7, 2.4], [3.5, 0.5]])
    rgi = interpolate.RegularGridInterpolator((gy, gx), Z)
    add(g, "interp2 bilinear vs scipy",
        f"Z = {m(Z)}; v = interp2(0:4, 0:3, Z, {m(pts[:, 0])}, {m(pts[:, 1])});", "v",
        rgi(pts[:, ::-1]).reshape(1, -1))


# ======================================================================================
# 5. ODE solvers
# ======================================================================================
def odes() -> None:
    g = "ode"

    def reference(f, t1, y0, t0=0.0):
        sol = integrate.solve_ivp(f, (t0, t1), y0, method="DOP853", rtol=1e-12, atol=1e-14)
        return sol.y[:, -1].reshape(1, -1)

    add(g, "ode45 exp decay y(1)", "[t, y] = ode45(@(t,y) -y, [0 1], 1); v = y(end);", "v",
        math.exp(-1), 1e-5, 1e-6)
    add(g, "ode45 oscillator, one period", "[t, y] = ode45(@(t,y) [y(2); -y(1)], [0 2*pi], "
        "[1; 0]); v = y(end, :);", "v", np.array([[1.0, 0.0]]), 0, 1e-4)
    add(g, "ode45 energy conservation", "[t, y] = ode45(@(t,y) [y(2); -y(1)], [0 20], [1; 0]);"
        " v = y(end,1)^2 + y(end,2)^2;", "v", 1.0, 1e-4, 1e-4)

    def vdp(_t, y):
        return [y[1], (1 - y[0] ** 2) * y[1] - y[0]]

    add(g, "ode45 Van der Pol mu=1 vs DOP853",
        "[t, y] = ode45(@(t,y) [y(2); (1-y(1)^2)*y(2) - y(1)], [0 10], [2; 0]); v = y(end,:);",
        "v", reference(vdp, 10.0, [2.0, 0.0]), 1e-4, 1e-4)

    def lv(_t, z):
        return [1.5 * z[0] - z[0] * z[1], -3.0 * z[1] + z[0] * z[1]]

    add(g, "ode45 Lotka-Volterra vs DOP853",
        "[t, y] = ode45(@(t,y) [1.5*y(1) - y(1)*y(2); -3*y(2) + y(1)*y(2)], [0 5], [10; 5]);"
        " v = y(end,:);", "v", reference(lv, 5.0, [10.0, 5.0]), 1e-4, 1e-4)
    add(g, "ode23 logistic (analytic)", "[t, y] = ode23(@(t,y) y*(1-y), [0 5], 0.1); "
        "v = y(end);", "v", 1 / (1 + 9 * math.exp(-5)), 1e-4, 1e-5)

    def stiff(t, y):
        return [-1000.0 * (y[0] - math.cos(t))]

    ref = integrate.solve_ivp(stiff, (0, 1), [0.0], method="Radau", rtol=1e-12,
                              atol=1e-14).y[:, -1]
    add(g, "ode15s stiff vs Radau",
        "[t, y] = ode15s(@(t,y) -1000*(y - cos(t)), [0 1], 0); v = y(end);", "v", ref[0], 1e-5,
        1e-6)
    tt = np.arange(0, 1.01, 0.25)
    add(g, "ode45 at requested times", "[t, y] = ode45(@(t,y) -2*y, 0:0.25:1, 3); v = y';", "v",
        3 * np.exp(-2 * tt), 1e-5, 1e-6)
    add(g, "ode45 backward in time", "[t, y] = ode45(@(t,y) -y, [1 0], exp(-1)); v = y(end);",
        "v", 1.0, 1e-5, 1e-6)


# ======================================================================================
# 6. Optimization
# ======================================================================================
def optimization() -> None:
    g = "optimization"
    add(g, "fminsearch Rosenbrock", "x = fminsearch(@(x) 100*(x(2)-x(1)^2)^2 + (1-x(1))^2, "
        "[-1.2 1]);", "x", np.array([[1.0, 1.0]]), 0, 1e-4)
    add(g, "fminsearch quadratic bowl", "x = fminsearch(@(x) (x(1)-3)^2 + 2*(x(2)+1)^2, "
        "[0 0]);", "x", np.array([[3.0, -1.0]]), 0, 1e-4)
    add(g, "fminbnd cos on [3,4]", "x = fminbnd(@cos, 3, 4);", "x", math.pi, 0, 1e-6)
    add(g, "fminbnd x*exp(-x) on [0,5]", "x = fminbnd(@(x) x*exp(-x), 0, 5);", "x", 5.0, 0, 1e-3)
    add(g, "fminunc quadratic", "x = fminunc(@(x) (x(1)-1)^2 + (x(2)+2)^2, [0; 0]);", "x",
        np.array([[1.0], [-2.0]]), 0, 1e-5)
    add(g, "fminunc Rosenbrock", "x = fminunc(@(x) 100*(x(2)-x(1)^2)^2 + (1-x(1))^2, "
        "[-1.2; 1]);", "x", np.array([[1.0], [1.0]]), 0, 1e-3)
    res = optimize.linprog([-1, -2], A_ub=[[1, 1]], b_ub=[4], bounds=[(0, 3), (0, None)],
                           method="highs")
    add(g, "linprog textbook LP vs scipy", "[x, f] = linprog([-1; -2], [1 1], 4, [], [], "
        "[0; 0], [3; Inf]);", "x", res.x.reshape(2, 1), 1e-8, 1e-8)
    add(g, "linprog objective value", "[x, f] = linprog([-1; -2], [1 1], 4, [], [], "
        "[0; 0], [3; Inf]);", "f", res.fun, 1e-8, 1e-8)
    c = np.array([3.0, 2, 4])
    Aub = np.array([[1.0, 1, 2], [2, 0, 3]])
    bub = np.array([4.0, 5])
    Aeq = np.array([[1.0, 1, 1]])
    res = optimize.linprog(-c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=[3], bounds=[(0, None)] * 3,
                           method="highs")
    add(g, "linprog with equality vs scipy",
        f"[x, f] = linprog({m(-c.reshape(-1, 1))}, {m(Aub)}, {m(bub.reshape(-1, 1))}, "
        f"{m(Aeq)}, 3, [0; 0; 0], []);", "f", res.fun, 1e-8, 1e-8)


# ======================================================================================
# 7. Statistics and FFT
# ======================================================================================
def statistics_and_fft() -> None:
    g = "statistics"
    x = RNG.normal(loc=5, scale=2, size=(1, 25))
    y = RNG.normal(loc=5.8, scale=2.5, size=(1, 18))
    X = RNG.normal(size=(8, 3))
    pre = f"x = {m(x)}; y = {m(y)}; X = {m(X)}; "
    add(g, "mean", pre + "v = mean(x);", "v", x.mean())
    add(g, "std (N-1)", pre + "v = std(x);", "v", x.std(ddof=1))
    add(g, "std (N)", pre + "v = std(x, 1);", "v", x.std(ddof=0))
    add(g, "var", pre + "v = var(x);", "v", x.var(ddof=1))
    add(g, "median", pre + "v = median(x);", "v", np.median(x))
    add(g, "rms", pre + "v = rms(x);", "v", math.sqrt(float(np.mean(x**2))))
    add(g, "zscore", pre + "v = zscore(x);", "v", stats.zscore(x[0], ddof=1).reshape(1, -1))
    add(g, "std of matrix columns", pre + "v = std(X);", "v", X.std(axis=0, ddof=1))
    xs = np.sort(x[0])
    pts = (np.arange(1, xs.size + 1) - 0.5) / xs.size
    probs = np.array([0.1, 0.25, 0.5, 0.9])
    add(g, "quantile (MATLAB rule)", pre + f"v = quantile(x, {m(probs)});", "v",
        np.interp(probs, pts, xs).reshape(1, -1))
    add(g, "prctile", pre + f"v = prctile(x, {m(probs * 100)});", "v",
        np.interp(probs, pts, xs).reshape(1, -1))
    t1 = stats.ttest_1samp(x[0], 5.0)
    add(g, "ttest p-value vs scipy", pre + "[h, p, ci, st] = ttest(x, 5);", "p", t1.pvalue,
        1e-9, 1e-12)
    add(g, "ttest tstat vs scipy", pre + "[h, p, ci, st] = ttest(x, 5); t = st.tstat;", "t",
        t1.statistic, 1e-9, 1e-12)
    ci = t1.confidence_interval(0.95)
    add(g, "ttest confidence interval", pre + "[h, p, ci] = ttest(x, 5);", "ci",
        np.array([[ci.low], [ci.high]]), 1e-9, 1e-10)
    t2 = stats.ttest_ind(x[0], y[0], equal_var=True)
    add(g, "ttest2 pooled p-value", pre + "[h, p] = ttest2(x, y);", "p", t2.pvalue, 1e-9, 1e-12)
    t2w = stats.ttest_ind(x[0], y[0], equal_var=False)
    add(g, "ttest2 Welch p-value", pre + "[h, p] = ttest2(x, y, 'Vartype', 'unequal');", "p",
        t2w.pvalue, 1e-9, 1e-12)
    ci2 = t2.confidence_interval(0.95)
    add(g, "ttest2 pooled CI", pre + "[h, p, ci] = ttest2(x, y);", "ci",
        np.array([[ci2.low], [ci2.high]]), 1e-9, 1e-10)

    g = "fft"
    sig = RNG.normal(size=(1, 16))
    sig12 = RNG.normal(size=(1, 12))
    n = np.arange(64)
    tone = np.sin(2 * np.pi * 5 * n / 64).reshape(1, -1)
    add(g, "fft vs numpy (N=16)", f"s = {m(sig)}; X = fft(s);", "X", np.fft.fft(sig))
    add(g, "fft vs numpy (N=12, not power of 2)", f"s = {m(sig12)}; X = fft(s);", "X",
        np.fft.fft(sig12))
    add(g, "ifft(fft(s)) = s", f"s = {m(sig)}; r = ifft(fft(s));", "r", sig, 1e-12, 1e-12)
    add(g, "tone appears in bin 5", f"s = {m(tone)}; X = abs(fft(s)); p = X(6);", "p", 32.0,
        1e-10, 1e-10)
    add(g, "Parseval", f"s = {m(sig)}; r = sum(abs(fft(s)).^2) / 16 - sum(s.^2);", "r", 0, 0,
        1e-10)


# ======================================================================================
# 8. Symbolic
# ======================================================================================
def symbolic() -> None:
    g = "symbolic"
    pre = "syms x s t; "
    add(g, "diff x^2 sin(x) at 1.3", pre + "v = double(subs(diff(x^2*sin(x), x), x, 1.3));", "v",
        2 * 1.3 * math.sin(1.3) + 1.3**2 * math.cos(1.3))
    add(g, "second derivative", pre + "v = double(subs(diff(x^4, x, 2), x, 2));", "v", 48.0)
    add(g, "int x*exp(x) [0,1]", pre + "v = double(int(x*exp(x), x, 0, 1));", "v", 1.0)
    add(g, "int indefinite", pre + "v = double(subs(int(x^2, x), x, 3));", "v", 9.0)
    add(g, "limit (1-cos x)/x^2", pre + "v = double(limit((1-cos(x))/x^2, x, 0));", "v", 0.5)
    add(g, "taylor sin order 6", pre + "v = double(subs(taylor(sin(x), x, 'Order', 6), x, 0.5));",
        "v", 0.5 - 0.5**3 / 6 + 0.5**5 / 120)
    add(g, "solve cubic roots", pre + "v = sort(double(solve(x^3 - 6*x^2 + 11*x - 6 == 0, x)));",
        "v", np.array([[1.0], [2.0], [3.0]]))
    add(g, "solve linear system", pre + "syms y; r = solve({x + y == 3, x - y == 1}, {x, y}); "
        "v = [double(r.x) double(r.y)];", "v", np.array([[2.0, 1.0]]))
    add(g, "laplace t^2 exp(-t) at s=2",
        pre + "v = double(subs(laplace(t^2*exp(-t), t, s), s, 2));", "v", 2 / 27)
    add(g, "ilaplace 1/(s^2+1) at t=1",
        pre + "v = double(subs(ilaplace(1/(s^2+1), s, t), t, 1));", "v", math.sin(1))
    expr = sp.simplify((sp.Symbol("x") ** 2 - 1) / (sp.Symbol("x") - 1))
    add(g, "simplify (x^2-1)/(x-1)", pre + "v = char(simplify((x^2-1)/(x-1)));", "v", str(expr))
    add(g, "expand/factor round trip", pre + "v = double(subs(expand((x+2)^3) - (x+2)^3, x, 1.7));",
        "v", 0, 0, 1e-12)


# ======================================================================================
# 9. Engineering example: torsional vibration of the MECH 322 drive
# ======================================================================================
def mech322() -> None:
    g = "MECH 322 torsional vibration"
    G = 10.6e6
    inertia = [0.28, 0.057, 0.057, 0.125, 0.64, 0.64, 0.805, 0.805]
    d = 0.755
    L12 = 37.1
    L57 = 1.05 * L12
    Z2, Z3, Z4, Z5, Z6 = 19, 19, 12, 38, 38
    J = math.pi * d**4 / 32
    kt12 = kt34 = G * J / L12
    kt57 = kt68 = G * J / L57
    i1, i2, i3, i4, i5, i6, i7, i8 = inertia
    M = np.diag([i1, i2 + i3 * (Z2 / Z3) ** 2,
                 i4 + i5 * (Z4 / Z5) ** 2 + i6 * (Z4 / Z6) ** 2, i7, i8])
    K = np.array([
        [kt12, -kt12, 0, 0, 0],
        [-kt12, kt12 + (Z2 / Z3) ** 2 * kt34, -Z2 / Z3 * kt34, 0, 0],
        [0, -Z2 / Z3 * kt34, kt34 + (Z4 / Z5) ** 2 * kt57 + (Z4 / Z6) ** 2 * kt68,
         -Z4 / Z5 * kt57, -Z4 / Z6 * kt68],
        [0, 0, -Z4 / Z5 * kt57, kt57, 0],
        [0, 0, -Z4 / Z6 * kt68, 0, kt68]])
    w2 = linalg.eigh(K, M, eigvals_only=True)
    code = ("G = 10.6e6; d = 0.755; L12 = 37.1; L57 = 1.05*L12; "
            "Z2 = 19; Z3 = 19; Z4 = 12; Z5 = 38; Z6 = 38; "
            "J = pi*d^4/32; kt12 = G*J/L12; kt34 = kt12; kt57 = G*J/L57; kt68 = kt57; "
            "MM = diag([0.28, 0.057 + 0.057*(Z2/Z3)^2, "
            "0.125 + 0.64*(Z4/Z5)^2 + 0.64*(Z4/Z6)^2, 0.805, 0.805]); "
            "KK = [kt12 -kt12 0 0 0; "
            "-kt12 kt12+(Z2/Z3)^2*kt34 -Z2/Z3*kt34 0 0; "
            "0 -Z2/Z3*kt34 kt34+(Z4/Z5)^2*kt57+(Z4/Z6)^2*kt68 -Z4/Z5*kt57 -Z4/Z6*kt68; "
            "0 0 -Z4/Z5*kt57 kt57 0; 0 0 -Z4/Z6*kt68 0 kt68]; "
            "e = sort(real(eig(inv(MM)*KK))); ")
    add(g, "stiffness kt12 [lb.in/rad]", code, "kt12", G * J / L12, 1e-12, 0)
    add(g, "natural frequencies (rad/s), elastic modes vs scipy eigh(K, M)",
        code + "w = sqrt(e(2:5));", "w", np.sqrt(w2[1:]), 1e-7, 1e-6)
    add(g, "rigid-body eigenvalue ~ 0 (relative to largest)", code + "r = abs(e(1))/e(5);", "r",
        0, 0, 1e-9)
    add(g, "K symmetric", code + "r = norm(KK - KK');", "r", 0, 0, 1e-6)
    add(g, "mode shapes satisfy (K - w^2 M) x = 0",
        code + "[V, D] = eig(inv(MM)*KK); r = norm(KK*V - MM*V*D) / norm(KK*V);", "r", 0, 0, 1e-8)


# ======================================================================================
# Runner
# ======================================================================================
class Kernel:
    def __init__(self) -> None:
        self.client = InProcessKernelClient(threaded=False)
        self.errors: list[str] = []
        self.client.subscribe(self._on_event)

    def _on_event(self, event: object) -> None:
        if isinstance(event, Diagnostics):
            self.errors.extend(d.message for d in event.items if d.severity == "error")

    def run(self, code: str) -> list[str]:
        self.errors = []
        self.client._interp.workspace.clear()
        self.client.execute(code, "validation")
        return list(self.errors)

    def get(self, name: str) -> np.ndarray:
        value = self.client._interp.workspace[name]
        if hasattr(value, "to_str"):  # char array
            return np.array(value.to_str())
        return np.asarray(value)

    def close(self) -> None:
        self.client.shutdown()


def compare(actual: np.ndarray, ref: object, rtol: float, atol: float) -> tuple[bool, float, str]:
    if isinstance(ref, str):
        got = str(actual.item()) if actual.dtype.kind == "U" else str(actual)
        return got == ref, 0.0, f"got {got!r}, expected {ref!r}"
    r = np.atleast_2d(np.asarray(ref))
    a = np.asarray(actual)
    if a.size != r.size:
        return False, math.inf, f"size {a.shape} vs reference {r.shape}"
    a, r = a.ravel(order="F"), r.ravel(order="F")
    err = float(np.max(np.abs(a - r))) if a.size else 0.0
    ok = bool(np.allclose(a, r, rtol=rtol, atol=atol))
    return ok, err, f"max abs error {err:.3g} (rtol {rtol:g}, atol {atol:g})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-k", "--filter", default="", help="only checks containing this text")
    args = parser.parse_args()

    for build in (linear_algebra, decompositions, basics, calculus, odes, optimization,
                  statistics_and_fft, symbolic, mech322):
        build()
    checks = [c for c in CHECKS if args.filter.lower() in f"{c.group} {c.name}".lower()]
    kernel = Kernel()
    lines: list[str] = []
    failures: list[str] = []
    started = time.time()
    current = ""
    for c in checks:
        if c.group != current:
            current = c.group
            lines.append(f"\n== {current} ==")
        try:
            errors = kernel.run(c.code)
            if errors:
                status, detail = "FAIL", "script error: " + errors[0].splitlines()[0]
            else:
                ok, _err, detail = compare(kernel.get(c.var), c.ref, c.rtol, c.atol)
                status = "pass" if ok else "FAIL"
        except Exception as exc:  # report, never crash the whole run
            status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
            if args.verbose:
                detail += "\n" + traceback.format_exc()
        if status == "FAIL":
            failures.append(f"{c.group} / {c.name}: {detail}")
        if status == "FAIL" or args.verbose:
            lines.append(f"  [{status}] {c.name}: {detail}")
        else:
            lines.append(f"  [pass] {c.name}")
    kernel.close()
    total = len(checks)
    summary = (f"\n{total - len(failures)} / {total} checks passed "
               f"in {time.time() - started:.1f} s")
    report = "\n".join(lines) + "\n" + summary + "\n"
    if failures:
        report += "\nFAILED:\n" + "\n".join(f"  - {f}" for f in failures) + "\n"
    print(report)
    Path("validation_report.txt").write_text(report, encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
