"""2-D finite element analysis: pin-jointed trusses, rigid-jointed frames (with element
distributed loads) and plane-stress plates meshed with bilinear Q4 elements (optionally with a
central hole) whose node grids plot straight into contourf/surf. Node and element numbers are
1-based, as in MATLAB. SI units."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "structural"


# ------------------------------------------------------------------------------ helpers
def _per_element(v: np.ndarray | float, m: int, what: str) -> np.ndarray:
    arr = np.atleast_1d(np.asarray(v, dtype=float)).ravel()
    if arr.size == 1:
        return np.full(m, arr[0])
    if arr.size != m:
        raise ValidationError(f"{what}: give one value or one per element ({m})")
    return arr


def _check_mesh(nodes: np.ndarray, elems: np.ndarray, who: str) -> np.ndarray:
    n = nodes.shape[0]
    e = np.asarray(elems)
    if np.any(e != np.round(e)) or e.min() < 1 or e.max() > n:
        raise ValidationError(f"{who}: element node numbers must be integers 1..{n}")
    e = e.astype(int) - 1
    if np.any(e[:, 0] == e[:, 1]):
        raise ValidationError(f"{who}: an element joins a node to itself")
    return e


def _node_rows(table: np.ndarray | None, n: int, cols: int, who: str, what: str
               ) -> np.ndarray:
    if table is None:
        return np.zeros((0, cols))
    t = np.atleast_2d(np.asarray(table, dtype=float))
    if t.shape[1] != cols:
        raise ValidationError(f"{who}: {what} rows must have {cols} columns")
    idx = t[:, 0]
    if np.any(idx != np.round(idx)) or np.any(idx < 1) or np.any(idx > n):
        raise ValidationError(f"{who}: {what} node numbers must be integers 1..{n}")
    return t


def _solve(K: np.ndarray, F: np.ndarray, fixed: np.ndarray, who: str) -> np.ndarray:
    free = np.setdiff1d(np.arange(K.shape[0]), fixed)
    if free.size == 0:
        return np.zeros(K.shape[0])
    Kff = K[np.ix_(free, free)]
    scale = np.max(np.abs(np.diag(Kff))) or 1.0
    if np.linalg.cond(Kff / scale) > 1e12:
        raise ValidationError(f"{who}: the structure is a mechanism (not enough supports or "
                              "members); check the supports")
    u = np.zeros(K.shape[0])
    u[free] = np.linalg.solve(Kff, F[free])
    return u


# --------------------------------------------------------------------------------- truss
@dataclass(frozen=True)
class Truss:
    u: np.ndarray  # node displacements [ux uy], one row per node
    N: np.ndarray  # member axial forces (tension +), N
    stress: np.ndarray  # member stresses, Pa
    reactions: np.ndarray  # support reactions [Rx Ry], one row per node
    length: np.ndarray  # member lengths


@tb_function("truss2d", CAT, args=[
    Arg("nodes", shape=(None, 2)), Arg("elements", shape=(None, 2)),
    Arg("E", unit="Pa", positive=True), Arg("A", positive=True),
    Arg("supports", shape=(None, 3)), Arg("loads", shape=(None, 3), optional=True)],
    returns=[Ret("result")])
def truss2d(nodes: np.ndarray, elements: np.ndarray, E: np.ndarray | float,
            A: np.ndarray | float, supports: np.ndarray, loads: np.ndarray | None = None
            ) -> Truss:
    """Pin-jointed plane truss. nodes: [x y] rows; elements: [node1 node2] rows; E, A: one value
    or one per element; supports: [node fixX fixY] rows (1 = fixed); loads: [node Fx Fy] rows."""
    xy = np.asarray(nodes, float)
    n = xy.shape[0]
    el = _check_mesh(xy, elements, "truss2d")
    m = el.shape[0]
    Ev, Av = _per_element(E, m, "truss2d: E"), _per_element(A, m, "truss2d: A")
    K = np.zeros((2 * n, 2 * n))
    L, cs = np.zeros(m), np.zeros((m, 2))
    for k, (i, j) in enumerate(el):
        d = xy[j] - xy[i]
        L[k] = math.hypot(*d)
        if L[k] == 0:
            raise ValidationError(f"truss2d: element {k + 1} has zero length")
        c, s = d / L[k]
        cs[k] = c, s
        t = np.array([c, s, -c, -s])
        dofs = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        K[np.ix_(dofs, dofs)] += Ev[k] * Av[k] / L[k] * np.outer(t, t)
    F = np.zeros(2 * n)
    for row in _node_rows(loads, n, 3, "truss2d", "load"):
        F[2 * int(row[0]) - 2: 2 * int(row[0])] += row[1:]
    sup = _node_rows(supports, n, 3, "truss2d", "support")
    fixed = np.array([2 * (int(r[0]) - 1) + d for r in sup for d in (0, 1) if r[1 + d]],
                     dtype=int)
    u = _solve(K, F, fixed, "truss2d")
    R = K @ u - F
    R[np.setdiff1d(np.arange(2 * n), fixed)] = 0.0
    N = np.array([Ev[k] * Av[k] / L[k] * (cs[k] @ (u[2 * j: 2 * j + 2] - u[2 * i: 2 * i + 2]))
                  for k, (i, j) in enumerate(el)])
    return Truss(u.reshape(n, 2), N, N / Av, R.reshape(n, 2), L)


# --------------------------------------------------------------------------------- frame
@dataclass(frozen=True)
class Frame:
    u: np.ndarray  # node displacements [ux uy rotation], one row per node
    N: np.ndarray  # member axial force (tension +)
    V: np.ndarray  # shear at [start end] of each member
    M: np.ndarray  # bending moment at [start end] (sagging +)
    reactions: np.ndarray  # [Rx Ry Mz] per node
    length: np.ndarray


@tb_function("frame2d", CAT, args=[
    Arg("nodes", shape=(None, 2)), Arg("elements", shape=(None, 2)),
    Arg("E", unit="Pa", positive=True), Arg("A", positive=True), Arg("I", positive=True),
    Arg("supports", shape=(None, 4)), Arg("loads", shape=(None, 4), optional=True),
    Arg("w", optional=True)],
    returns=[Ret("result")])
def frame2d(nodes: np.ndarray, elements: np.ndarray, E: np.ndarray | float,
            A: np.ndarray | float, I: np.ndarray | float,  # noqa: E741
            supports: np.ndarray, loads: np.ndarray | None = None,
            w: np.ndarray | float | None = None) -> Frame:
    """Rigid-jointed plane frame (Euler-Bernoulli elements). supports: [node fixX fixY fixRot]
    rows; loads: [node Fx Fy M] rows; w: uniform load per element, along the element's local y
    axis (90 degrees anticlockwise from node1 -> node2; a left-to-right beam with gravity load
    has w < 0)."""
    xy = np.asarray(nodes, float)
    n = xy.shape[0]
    el = _check_mesh(xy, elements, "frame2d")
    m = el.shape[0]
    Ev, Av, Iv = (_per_element(v, m, f"frame2d: {s}") for v, s in ((E, "E"), (A, "A"),
                                                                    (I, "I")))
    wv = np.zeros(m) if w is None else _per_element(w, m, "frame2d: w")
    K = np.zeros((3 * n, 3 * n))
    F = np.zeros(3 * n)
    store = []
    for k, (i, j) in enumerate(el):
        d = xy[j] - xy[i]
        L = math.hypot(*d)
        if L == 0:
            raise ValidationError(f"frame2d: element {k + 1} has zero length")
        c, s = d / L
        T = np.zeros((6, 6))
        T[:3, :3] = T[3:, 3:] = [[c, s, 0], [-s, c, 0], [0, 0, 1]]
        ea, ei = Ev[k] * Av[k] / L, Ev[k] * Iv[k]
        kl = np.array([
            [ea, 0, 0, -ea, 0, 0],
            [0, 12 * ei / L ** 3, 6 * ei / L ** 2, 0, -12 * ei / L ** 3, 6 * ei / L ** 2],
            [0, 6 * ei / L ** 2, 4 * ei / L, 0, -6 * ei / L ** 2, 2 * ei / L],
            [-ea, 0, 0, ea, 0, 0],
            [0, -12 * ei / L ** 3, -6 * ei / L ** 2, 0, 12 * ei / L ** 3, -6 * ei / L ** 2],
            [0, 6 * ei / L ** 2, 2 * ei / L, 0, -6 * ei / L ** 2, 4 * ei / L]])
        q = wv[k] * np.array([0, L / 2, L ** 2 / 12, 0, L / 2, -L ** 2 / 12])  # equiv. loads
        dofs = [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]
        K[np.ix_(dofs, dofs)] += T.T @ kl @ T
        F[dofs] += T.T @ q
        store.append((dofs, T, kl, q, L))
    Fn = np.zeros(3 * n)
    for row in _node_rows(loads, n, 4, "frame2d", "load"):
        Fn[3 * int(row[0]) - 3: 3 * int(row[0])] += row[1:]
    F += Fn
    sup = _node_rows(supports, n, 4, "frame2d", "support")
    fixed = np.array([3 * (int(r[0]) - 1) + d for r in sup for d in (0, 1, 2) if r[1 + d]],
                     dtype=int)
    u = _solve(K, F, fixed, "frame2d")
    R = K @ u - F
    R[np.setdiff1d(np.arange(3 * n), fixed)] = 0.0
    N, V, M, Ls = np.zeros(m), np.zeros((m, 2)), np.zeros((m, 2)), np.zeros(m)
    for k, (dofs, T, kl, q, L) in enumerate(store):
        f = kl @ (T @ u[dofs]) - q  # end forces acting on the element, local axes
        N[k], V[k], M[k], Ls[k] = f[3], (f[1], -f[4]), (-f[2], f[5]), L
    return Frame(u.reshape(n, 3), N, V, M, R.reshape(n, 3), Ls)


# --------------------------------------------------------------------------------- plate
@dataclass(frozen=True)
class Plate:
    X: np.ndarray  # node x coordinates, (ny+1)-by-(nx+1) grid
    Y: np.ndarray
    ux: np.ndarray
    uy: np.ndarray
    sx: np.ndarray  # nodal (averaged) stresses, NaN inside the hole
    sy: np.ndarray
    txy: np.ndarray
    von_mises: np.ndarray
    max_von_mises: float
    max_displacement: float


def _q4_B(xi: float, eta: float, a: float, b: float) -> np.ndarray:
    """Strain-displacement matrix of a rectangular a-by-b Q4 element (nodes ccw from bottom
    left) at natural coordinates (xi, eta)."""
    dxi = np.array([-(1 - eta), (1 - eta), (1 + eta), -(1 + eta)]) / 4
    deta = np.array([-(1 - xi), -(1 + xi), (1 + xi), (1 - xi)]) / 4
    dx, dy = dxi * 2 / a, deta * 2 / b
    B = np.zeros((3, 8))
    B[0, 0::2], B[1, 1::2] = dx, dy
    B[2, 0::2], B[2, 1::2] = dy, dx
    return B


@tb_function("plate2d", CAT, args=[
    Arg("Lx", unit="m", positive=True), Arg("Ly", unit="m", positive=True),
    Arg("t", unit="m", positive=True), Arg("E", unit="Pa", positive=True),
    Arg("nu", min=0.0, max=0.499), Arg("nx", integer=True, min=1, max=200),
    Arg("ny", integer=True, min=1, max=200),
    Arg("support", choices=("left", "left-roller", "bottom", "bottom-roller")),
    Arg("load_edge", choices=("right", "top", "left", "bottom")),
    Arg("traction", shape=(2,)), Arg("hole_radius", unit="m", nonnegative=True)],
    returns=[Ret("result")])
def plate2d(Lx: float, Ly: float, t: float, E: float, nu: float, nx: int = 20, ny: int = 10,
            support: str = "left", load_edge: str = "right",
            traction: np.ndarray | None = None, hole_radius: float = 0.0) -> Plate:
    """Plane-stress rectangular plate Lx-by-Ly (thickness t) meshed with nx-by-ny Q4 elements.
    support: 'left'/'bottom' clamps that edge; '-roller' only stops the normal direction (plus
    one corner, so the plate cannot slide). traction [tx ty] (Pa) acts on load_edge.
    hole_radius > 0 removes the elements whose centre lies inside a central circular hole.
    Plot with contourf(r.X, r.Y, r.von_mises)."""
    nx, ny = int(nx), int(ny)
    tr = np.zeros(2) if traction is None else np.asarray(traction, float).ravel()
    if support.split("-")[0] == load_edge:
        raise ValidationError("plate2d: the loaded edge cannot be the supported edge")
    a, b = Lx / nx, Ly / ny
    xs, ys = np.linspace(0, Lx, nx + 1), np.linspace(0, Ly, ny + 1)
    X, Y = np.meshgrid(xs, ys)

    def nid(i: int, j: int) -> int:  # column i (x), row j (y)
        return j * (nx + 1) + i

    elems = []
    for j in range(ny):
        for i in range(nx):
            cx, cy = (i + 0.5) * a, (j + 0.5) * b
            if hole_radius > 0 and math.hypot(cx - Lx / 2, cy - Ly / 2) < hole_radius:
                continue
            elems.append([nid(i, j), nid(i + 1, j), nid(i + 1, j + 1), nid(i, j + 1)])
    if not elems:
        raise ValidationError("plate2d: the hole removes every element")
    nn = (nx + 1) * (ny + 1)
    D = E / (1 - nu ** 2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    g = 1 / math.sqrt(3)
    gauss = [(-g, -g), (g, -g), (g, g), (-g, g)]
    ke = sum(_q4_B(xi, eta, a, b).T @ D @ _q4_B(xi, eta, a, b) for xi, eta in gauss)
    ke = ke * t * a * b / 4  # det J = ab/4, weights 1
    rows, cols, vals = [], [], []
    for e in elems:
        dofs = np.ravel([[2 * v, 2 * v + 1] for v in e])
        rows.append(np.repeat(dofs, 8))
        cols.append(np.tile(dofs, 8))
        vals.append(ke.ravel())
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve

    K = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                   shape=(2 * nn, 2 * nn)).tocsr()
    used = np.zeros(nn, dtype=bool)
    used[np.ravel(elems)] = True

    def edge(name: str) -> list[int]:
        if name == "left":
            return [nid(0, j) for j in range(ny + 1)]
        if name == "right":
            return [nid(nx, j) for j in range(ny + 1)]
        if name == "bottom":
            return [nid(i, 0) for i in range(nx + 1)]
        return [nid(i, ny) for i in range(nx + 1)]

    F = np.zeros(2 * nn)
    ln = edge(load_edge)
    h = b if load_edge in ("left", "right") else a
    for k, v in enumerate(ln):  # consistent loads: half shares at the two ends
        share = h * t * (0.5 if k in (0, len(ln) - 1) else 1.0)
        F[2 * v: 2 * v + 2] += tr * share
    side, _, roller = support.partition("-")
    fixed: set[int] = set()
    for v in edge(side):
        normal = 0 if side == "left" else 1
        fixed.add(2 * v + normal)
        if not roller:
            fixed.add(2 * v + 1 - normal)
    if roller:
        fixed.add(2 * nid(0, 0) + (1 if side == "left" else 0))
    fixed |= {2 * v + d for v in np.flatnonzero(~used) for d in (0, 1)}
    free = np.setdiff1d(np.arange(2 * nn), sorted(fixed))
    u = np.zeros(2 * nn)
    u[free] = spsolve(K[free][:, free].tocsc(), F[free])
    if not np.all(np.isfinite(u)):
        raise ValidationError("plate2d: the plate is not held (singular stiffness)")
    acc, cnt = np.zeros((nn, 3)), np.zeros(nn)
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for e in elems:
        ue = np.ravel([[u[2 * v], u[2 * v + 1]] for v in e])
        for v, (xi, eta) in zip(e, corners, strict=True):
            acc[v] += D @ (_q4_B(xi, eta, a, b) @ ue)
            cnt[v] += 1
    with np.errstate(invalid="ignore", divide="ignore"):
        st = acc / cnt[:, None]
    st[~used] = np.nan
    sx, sy, txy = (st[:, k].reshape(ny + 1, nx + 1) for k in range(3))
    vm = np.sqrt(sx ** 2 - sx * sy + sy ** 2 + 3 * txy ** 2)
    ux, uy = u[0::2].reshape(ny + 1, nx + 1), u[1::2].reshape(ny + 1, nx + 1)
    ux[~used.reshape(ny + 1, nx + 1)] = np.nan
    uy[~used.reshape(ny + 1, nx + 1)] = np.nan
    return Plate(X, Y, ux, uy, sx, sy, txy, vm, float(np.nanmax(vm)),
                 float(np.nanmax(np.hypot(ux, uy))))


FUNCTIONS = (truss2d, frame2d, plate2d)
