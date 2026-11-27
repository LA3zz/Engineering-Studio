"""Built-in self-test: proves that the installed or frozen application is healthy.

This module is the bundle probe used by ``EngineeringStudio.exe --selftest``. It deliberately
touches every bundled third-party library (and a spawned child process) so that missing
DLLs, data files or hidden imports show up as a FAIL line instead of a crash later. It is
exempt from the third-party placement rules in tests/architecture (see ARCHITECTURE.md).
"""

from __future__ import annotations

import io
import math
import multiprocessing
import os
import platform
import sqlite3
import sys
import time
from collections.abc import Callable

from engstudio.version import APP_NAME, __version__

Check = tuple[str, Callable[[], None]]


def check_units() -> None:
    from engstudio.core.units import convert

    value = convert(1, "psi", "Pa")
    assert math.isclose(value, 6894.757293168, rel_tol=1e-12), value


def check_numpy() -> None:
    import numpy as np

    x = np.linalg.solve([[3.0, 1.0], [1.0, 2.0]], [9.0, 8.0])
    assert np.allclose(x, [2.0, 3.0], rtol=1e-12), x


def check_scipy() -> None:
    import numpy as np
    from scipy import integrate, linalg, optimize

    value, _ = integrate.quad(np.sin, 0.0, np.pi)
    assert abs(value - 2.0) < 1e-10, value
    sol = integrate.solve_ivp(lambda t, y: -y, (0.0, 1.0), [1.0], rtol=1e-10, atol=1e-12)
    assert sol.success and abs(sol.y[0, -1] - math.exp(-1.0)) < 1e-8, sol.y[0, -1]
    assert np.allclose(linalg.eigvalsh([[2.0, 0.0], [0.0, 3.0]]), [2.0, 3.0])
    root = optimize.brentq(lambda x: x * x - 2.0, 0.0, 2.0, xtol=1e-14)
    assert abs(root - math.sqrt(2.0)) < 1e-12, root


def check_sympy() -> None:
    import sympy as sp

    x = sp.symbols("x")
    assert sp.diff(sp.sin(x), x) == sp.cos(x)
    assert sp.integrate(x**2, x) == x**3 / 3


def check_pandas_openpyxl() -> None:
    import openpyxl
    import pandas as pd

    assert int(pd.DataFrame({"a": [1, 2, 3]})["a"].sum()) == 6
    wb = openpyxl.Workbook()
    wb.active["A1"] = 42
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    assert openpyxl.load_workbook(buf).active["A1"].value == 42


def check_matplotlib() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.set_title("self-test")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    assert buf.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"


def check_control() -> None:
    import control

    system = control.tf([1.0], [1.0, 1.0])
    assert math.isclose(float(control.dcgain(system)), 1.0, rel_tol=1e-12)


def check_sqlite() -> None:
    con = sqlite3.connect(":memory:")
    try:
        con.execute("create table t (k text, v real)")
        con.execute("insert into t values ('a', 1.5)")
        assert con.execute("select v from t where k = 'a'").fetchone() == (1.5,)
    finally:
        con.close()


def check_qt_importable() -> None:
    import pyqtgraph
    import PySide6
    import PySide6.QtCore
    import PySide6.QtGui
    import PySide6.QtWidgets

    assert PySide6.__version__ and pyqtgraph.__version__


def _child_square_sum(conn) -> None:
    import numpy as np

    data = conn.recv()
    conn.send((os.getpid(), float(np.sum(np.square(data)))))
    conn.close()


def _child_sleeper(conn) -> None:
    conn.send("ready")
    time.sleep(120)


def check_process_roundtrip() -> None:
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_child_square_sum, args=(child,))
    proc.start()
    child.close()
    try:
        parent.send([1.0, 2.0, 3.0])
        assert parent.poll(60), "child process did not answer within 60 s"
        pid, value = parent.recv()
        assert value == 14.0, value
        assert pid != os.getpid()
    finally:
        proc.join(10)
        if proc.is_alive():
            proc.terminate()
            proc.join(10)
    assert proc.exitcode == 0, proc.exitcode


def check_process_terminate() -> None:
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_child_sleeper, args=(child,))
    proc.start()
    child.close()
    try:
        assert parent.poll(60) and parent.recv() == "ready", "sleeper child did not start"
        proc.terminate()
        proc.join(10)
        assert not proc.is_alive(), "terminate() did not stop the child process"
        assert proc.exitcode not in (None, 0), proc.exitcode
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(10)


CHECKS: list[Check] = [
    ("units", check_units),
    ("numpy", check_numpy),
    ("scipy", check_scipy),
    ("sympy", check_sympy),
    ("pandas+openpyxl", check_pandas_openpyxl),
    ("matplotlib (Agg, fonts)", check_matplotlib),
    ("python-control", check_control),
    ("sqlite3", check_sqlite),
    ("Qt + pyqtgraph importable", check_qt_importable),
    ("child process round-trip (spawn)", check_process_roundtrip),
    ("child process terminate (Stop)", check_process_terminate),
]


def run_checks(checks: list[Check], out: Callable[[str], None] = print) -> bool:
    all_ok = True
    for name, fn in checks:
        start = time.perf_counter()
        try:
            fn()
            status, detail = "PASS", ""
        except Exception as exc:
            status, detail = "FAIL", f" - {type(exc).__name__}: {exc}"
            all_ok = False
        out(f"{status} {name} ({time.perf_counter() - start:.2f}s){detail}")
    return all_ok


def run_selftest(checks: list[Check] | None = None, out: Callable[[str], None] = print) -> int:
    start = time.perf_counter()
    checks = CHECKS if checks is None else checks
    out(f"{APP_NAME} {__version__} self-test")
    out(
        f"frozen={getattr(sys, 'frozen', False)} python={platform.python_version()} "
        f"platform={platform.platform()}"
    )
    ok = run_checks(checks, out)
    verdict = "ALL PASSED" if ok else "FAILURES"
    out(f"RESULT: {verdict} ({len(checks)} checks, {time.perf_counter() - start:.1f}s)")
    return 0 if ok else 1


def run_gui_check() -> int:
    """Open a window for half a second on the real display, then close it."""
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QLabel

        app = QApplication.instance() or QApplication(sys.argv[:1])
        label = QLabel(f"{APP_NAME} {__version__} - GUI check (closes automatically)")
        label.resize(460, 80)
        label.show()
        QTimer.singleShot(500, app.quit)
        app.exec()
    except Exception as exc:
        print(f"FAIL gui window - {type(exc).__name__}: {exc}")
        return 1
    print("PASS gui window opened and closed")
    return 0
