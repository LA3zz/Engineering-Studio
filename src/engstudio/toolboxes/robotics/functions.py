"""Robotics: rotation matrices and homogeneous transforms, Denavit-Hartenberg forward
kinematics (with joint positions for plotting), planar-arm Jacobian, two-link inverse
kinematics and joint trajectories (cubic, quintic, trapezoidal velocity). Angles in radians
unless the argument says degrees."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import Arg, Ret, tb_function

CAT = "robotics"


def _rot(axis: str, t: float) -> np.ndarray:
    c, s = math.cos(t), math.sin(t)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


@tb_function("rotx", CAT, args=[Arg("theta", unit="deg")], returns=[Ret("R")])
def rotx(theta: float) -> np.ndarray:
    """3-by-3 rotation about x by theta degrees (as MATLAB's rotx)."""
    return _rot("x", math.radians(theta))


@tb_function("roty", CAT, args=[Arg("theta", unit="deg")], returns=[Ret("R")])
def roty(theta: float) -> np.ndarray:
    """3-by-3 rotation about y by theta degrees."""
    return _rot("y", math.radians(theta))


@tb_function("rotz", CAT, args=[Arg("theta", unit="deg")], returns=[Ret("R")])
def rotz(theta: float) -> np.ndarray:
    """3-by-3 rotation about z by theta degrees."""
    return _rot("z", math.radians(theta))


@tb_function("transform", CAT, args=[Arg("R", shape=(3, 3)), Arg("p", shape=(3,))],
             returns=[Ret("T")])
def transform(R: np.ndarray, p: np.ndarray) -> np.ndarray:
    """4-by-4 homogeneous transform from a rotation R and a translation p."""
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, np.asarray(p, float).ravel()
    return T


@tb_function("dh", CAT, args=[Arg("a"), Arg("alpha"), Arg("d"), Arg("theta")],
             returns=[Ret("T")])
def dh(a: float, alpha: float, d: float, theta: float) -> np.ndarray:
    """Standard Denavit-Hartenberg link transform Rz(theta) Tz(d) Tx(a) Rx(alpha) (radians)."""
    ct, st, ca, sa = math.cos(theta), math.sin(theta), math.cos(alpha), math.sin(alpha)
    return np.array([[ct, -st * ca, st * sa, a * ct], [st, ct * ca, -ct * sa, a * st],
                     [0, sa, ca, d], [0, 0, 0, 1]])


@dataclass(frozen=True)
class Fk:
    T: np.ndarray  # base -> end-effector transform
    position: np.ndarray  # end-effector [x y z]
    joints: np.ndarray  # joint origins, one row per frame (base first): plot3 / plot
    euler_zyx: np.ndarray  # yaw, pitch, roll of the end effector, degrees


@tb_function("fkine", CAT, args=[Arg("dh_table", shape=(None, 4)), Arg("q", shape=(None,)),
                                  Arg("prismatic", shape=(None,), optional=True)],
             returns=[Ret("result")])
def fkine(dh_table: np.ndarray, q: np.ndarray, prismatic: np.ndarray | None = None) -> Fk:
    """Forward kinematics of a serial arm. dh_table rows [a alpha d theta_offset]; q the joint
    variables; prismatic: 0/1 per joint (1: q adds to d, else q adds to theta; default all
    revolute)."""
    tab = np.asarray(dh_table, float)
    qv = np.asarray(q, float).ravel()
    n = tab.shape[0]
    if qv.size != n:
        raise ValidationError(f"fkine: q needs {n} values, one per DH row")
    flags = np.zeros(n) if prismatic is None else np.asarray(prismatic, float).ravel()
    if flags.size != n:
        raise ValidationError(f"fkine: prismatic needs {n} flags (0 or 1)")
    kinds = ["P" if p else "R" for p in flags]
    T = np.eye(4)
    pts = [T[:3, 3].copy()]
    for (a, alpha, d, th), qi, kind in zip(tab, qv, kinds, strict=True):
        T = T @ (dh(a, alpha, d, th + qi) if kind == "R" else dh(a, alpha, d + qi, th))
        pts.append(T[:3, 3].copy())
    R = T[:3, :3]
    pitch = math.atan2(-R[2, 0], math.hypot(R[0, 0], R[1, 0]))
    eul = np.degrees([math.atan2(R[1, 0], R[0, 0]), pitch, math.atan2(R[2, 1], R[2, 2])])
    return Fk(T, T[:3, 3].copy(), np.array(pts), eul)


@tb_function("planar_arm", CAT, args=[Arg("L", shape=(None,), positive=True),
                                       Arg("q", shape=(None,))],
             returns=[Ret("x"), Ret("y"), Ret("J")])
def planar_arm(L: np.ndarray, q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Planar serial arm with revolute joints: joint x, y coordinates (base first, so
    plot(x, y, '-o') draws the arm) and the 2-by-n end-effector Jacobian (radians)."""
    Lv, qv = np.asarray(L, float).ravel(), np.asarray(q, float).ravel()
    if Lv.size != qv.size:
        raise ValidationError("planar_arm: give one joint angle per link")
    ang = np.cumsum(qv)
    x = np.r_[0.0, np.cumsum(Lv * np.cos(ang))]
    y = np.r_[0.0, np.cumsum(Lv * np.sin(ang))]
    J = np.zeros((2, qv.size))
    for i in range(qv.size):
        J[0, i] = -(y[-1] - y[i])
        J[1, i] = x[-1] - x[i]
    return x, y, J


@tb_function("ik_2link", CAT, args=[Arg("L1", positive=True), Arg("L2", positive=True),
                                     Arg("x"), Arg("y"),
                                     Arg("elbow", choices=("up", "down"))],
             returns=[Ret("q1"), Ret("q2")])
def ik_2link(L1: float, L2: float, x: float, y: float, elbow: str = "down"
             ) -> tuple[float, float]:
    """Inverse kinematics of a planar two-link arm (radians)."""
    c2 = (x * x + y * y - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    if abs(c2) > 1 + 1e-12:
        raise ValidationError("ik_2link: the point is out of reach")
    c2 = max(-1.0, min(1.0, c2))
    s2 = math.sqrt(1 - c2 * c2) * (1 if elbow == "down" else -1)
    q2 = math.atan2(s2, c2)
    q1 = math.atan2(y, x) - math.atan2(L2 * s2, L1 + L2 * c2)
    return q1, q2


@tb_function("trajectory", CAT, args=[
    Arg("q0"), Arg("qf"), Arg("tf", positive=True), Arg("t", shape=(None,)),
    Arg("kind", choices=("cubic", "quintic", "trapezoid")),
    Arg("v_max", positive=True, optional=True)],
    returns=[Ret("q"), Ret("qd"), Ret("qdd")])
def trajectory(q0: float, qf: float, tf: float, t: np.ndarray, kind: str = "quintic",
               v_max: float | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Point-to-point joint trajectory from q0 to qf in tf seconds, at rest at both ends:
    cubic, quintic (zero end accelerations too) or trapezoidal velocity (cruise speed v_max,
    default 1.5 times the average speed)."""
    tt = np.clip(np.asarray(t, float).ravel(), 0, tf)
    dq = qf - q0
    if kind in ("cubic", "quintic"):
        s = tt / tf
        if kind == "cubic":
            p, v, a = 3 * s ** 2 - 2 * s ** 3, 6 * s - 6 * s ** 2, 6 - 12 * s
        else:
            p = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5
            v, a = 30 * s ** 2 - 60 * s ** 3 + 30 * s ** 4, 60 * s - 180 * s ** 2 + 120 * s ** 3
        return q0 + dq * p, dq * v / tf, dq * a / tf ** 2
    vm = 1.5 * abs(dq) / tf if v_max is None else v_max
    if dq == 0:
        z = np.zeros_like(tt)
        return z + q0, z, z
    if not abs(dq) / tf < vm <= 2 * abs(dq) / tf:
        raise ValidationError("trajectory: v_max must lie between |qf-q0|/tf and 2|qf-q0|/tf")
    tb = tf - abs(dq) / vm
    acc = vm / tb
    sg = math.copysign(1.0, dq)
    q, qd, qdd = (np.empty_like(tt) for _ in range(3))
    for k, ti in enumerate(tt):
        if ti < tb:
            q[k], qd[k], qdd[k] = q0 + sg * acc * ti ** 2 / 2, sg * acc * ti, sg * acc
        elif ti <= tf - tb:
            q[k], qd[k], qdd[k] = q0 + sg * vm * (ti - tb / 2), sg * vm, 0.0
        else:
            r = tf - ti
            q[k], qd[k], qdd[k] = qf - sg * acc * r ** 2 / 2, sg * acc * r, -sg * acc
    return q, qd, qdd


FUNCTIONS = (rotx, roty, rotz, transform, dh, fkine, planar_arm, ik_2link, trajectory)
