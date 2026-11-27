import collections
import dataclasses
import importlib
import inspect
import pkgutil
import subprocess
import sys

import engstudio.engine as eng

out = []
for m in sorted(pkgutil.iter_modules(eng.__path__), key=lambda m: m.name):
    mod = importlib.import_module(f"engstudio.engine.{m.name}")
    out.append(f"## {m.name}: {(mod.__doc__ or '').strip().splitlines()[0] if mod.__doc__ else ''}")
    for n in getattr(mod, "__all__", []):
        o = getattr(mod, n)
        if dataclasses.is_dataclass(o):
            fs = ", ".join(f.name for f in dataclasses.fields(o))
            out.append(f"  class {n}({fs})")
        elif callable(o):
            out.append(f"  def {n}{inspect.signature(o)}")
        else:
            out.append(f"  {n} = {o!r}")
r = subprocess.run([sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
                   capture_output=True, text=True)
c = collections.Counter(
    line.split("::")[0] for line in r.stdout.splitlines() if "::" in line
)
out.append("## TEST COUNTS PER FILE")
out += [f"  {k}: {v}" for k, v in sorted(c.items()) if "engine" in k or "unit" in k]
out.append(f"  TOTAL collected: {sum(c.values())}")
open("scripts/api_dump.txt", "w", encoding="utf-8").write("\n".join(out))
print("written scripts/api_dump.txt")