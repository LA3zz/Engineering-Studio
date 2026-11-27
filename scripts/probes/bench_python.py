"""Compare Python versions on the workloads that matter for Engineering Studio.

    .venv\\Scripts\\python.exe scripts\\probes\\bench_python.py
    .venv314\\Scripts\\python.exe scripts\\probes\\bench_python.py

Prints one line per workload: best of 3 wall times in seconds.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]

t0 = time.perf_counter()
from engstudio.app.kernel.inprocess import InProcessKernelClient  # noqa: E402

t_import = time.perf_counter() - t0

LOOP = """
s = 0;
for k = 1:200000
    if mod(k, 3) == 0
        s = s + k^2;
    else
        s = s - 1;
    end
end
"""
FUNCS = """
f = @(x) x.^2 + 3*x - 2;
v = 0;
for k = 1:20000
    v = v + f(k/1000);
end
"""
ODE = """
f = @(t, y) [y(2); -(0.4*y(2) + 4*y(1)) + sin(2*t)];
[t, y] = ode45(f, [0 200], [1; 0]);
"""
NUMERIC = """
A = rand(400); B = A*A'; e = eig(B); x = B \\ ones(400, 1);
"""
SIM = "out = sim('mass_spring_damper.esmodel', 'StopTime', 200);"
FEA = ("r = plate2d(0.4, 0.2, 0.005, 200e9, 0.3, 120, 60, 'left-roller', 'right', [10e6 0], "
       "0.03);")


def timed(k: InProcessKernelClient, code: str, file: str | None = None) -> float:
    best = float("inf")
    for _ in range(3):
        t = time.perf_counter()
        k.execute(code, file)
        best = min(best, time.perf_counter() - t)
    return best


def main() -> None:
    t = time.perf_counter()
    k = InProcessKernelClient(threaded=False)
    t_start = time.perf_counter() - t
    os.chdir(ROOT / "examples" / "models")
    ff = (ROOT / "examples" / "full_feature_test.m").read_text(encoding="utf-8")
    rows = {
        "import engine (s)": t_import,
        "kernel start (s)": t_start,
        "interpreter loop 200k (s)": timed(k, LOOP),
        "anonymous fn calls 20k (s)": timed(k, FUNCS),
        "ode45 200 s oscillator (s)": timed(k, ODE),
        "numpy/scipy 400x400 (s)": timed(k, NUMERIC),
        "simulation 200 s (s)": timed(k, SIM),
        "plate2d 120x60 FEA (s)": timed(k, FEA),
        "full_feature_test.m (s)": timed(k, ff, str(ROOT / "examples" / "full_feature_test.m")),
    }
    k.shutdown()
    print(f"Python {sys.version.split()[0]}")
    for name, v in rows.items():
        print(f"  {name:30s} {v:8.3f}")


if __name__ == "__main__":
    main()
