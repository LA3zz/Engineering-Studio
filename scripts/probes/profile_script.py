"""Time a user's .m script in the kernel and show where the time goes.

    python scripts/probes/profile_script.py path\\to\\script.m
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from engstudio.app.kernel.inprocess import InProcessKernelClient  # noqa: E402
from engstudio.app.kernel.protocol import Diagnostics, FigureUpdate  # noqa: E402

path = Path(sys.argv[1])
k = InProcessKernelClient(threaded=False)
events: list = []
k.subscribe(events.append)
prof = cProfile.Profile()
t0 = time.perf_counter()
prof.enable()
k.execute(path.read_text(encoding="utf-8"), str(path))
prof.disable()
total = time.perf_counter() - t0
errors = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
print(f"total {total:.2f} s, figure updates {sum(isinstance(e, FigureUpdate) for e in events)}, "
      f"errors {errors[:2]}")
out = io.StringIO()
pstats.Stats(prof, stream=out).sort_stats("cumulative").print_stats(28)
print(out.getvalue())
k.shutdown()
