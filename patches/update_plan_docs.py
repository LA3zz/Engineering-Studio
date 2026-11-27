"""Record the agreed development plan in docs\\project (planning text only, no code change).
Run from the project root after update_docs_g61.py: python patches\\update_plan_docs.py"""

from __future__ import annotations

import re
import sys
from pathlib import Path

D = Path("docs/project")

PLAN = """
## Agreed plan (set 2026-11-20)
Order: G6.2 -> Phase 3 math engine -> Phase 4 scripting -> Phase 5 plotting commands ->
Phase 6 control -> Phase 7 simulation -> Phase 8 toolboxes -> Phase 9 integration/QA ->
Phase 10 packaging. Numbering follows the user's phase prompts: the earlier heading
"Phase 3 - Interpreter core" above is the user's Phase 4 (lexer T3.1 is done).
Per milestone: build, user tests on Windows, fix, then update docs. About 3-4 exchanges each.

### Phase 3 - Math engine (package engstudio.engine: pure functions, typed errors, Result
dataclasses per ARCHITECTURE section 6, every result checked against analytic values)
- [ ] E1 engine scaffold + validation helpers + linear algebra (matrix/vector ops, solve with
  rcond, inv, det, norm, rank, cond)
- [ ] E2 decompositions + eigenvalues/eigenvectors
- [ ] E3 numerical differentiation and integration
- [ ] E4 root finding and equation solving (scalar, systems, polynomials)
- [ ] E5 interpolation
- [ ] E6 regression and curve fitting
- [ ] E7 numerical optimization
- [ ] E8 statistics
- [ ] E9 ODE solvers
- [ ] E10 Fourier transforms and spectral tools
- [ ] E11 symbolic mathematics (SymExpr: diff, integrate, solve, series, Laplace/inverse)
- [ ] E12 uncertainty propagation (GUM linear + Monte Carlo) and engine API docs

### Later phases (the user pastes each phase prompt when it is reached)
- [ ] Phase 4 scripting: AST, parser, interpreter, functions, control flow, error lines,
  real kernel process, Run/F5, conformance tests
- [ ] Phase 5 plotting commands: plot/subplot/xlabel/..., 3D, histogram, contour, surface,
  animation, figure manager (FigureSpec, window and export already exist)
- [ ] Phase 6 control systems and PID
- [ ] Phase 7 simulation environment (17 incremental steps)
- [ ] Phase 8 engineering toolboxes (one at a time)
- [ ] Phase 9 integration and quality assurance
- [ ] Phase 10 packaging (GUI in the PyInstaller spec, installer, clean-PC test T2.7b)
"""
HANDOFF_PLAN = ("\nPlan: see 'Agreed plan' in TASKS.md. After G6.2 comes the math engine "
                "E1-E12 (Phase 3), then the user's Phases 4-10.")


def read(name: str) -> str:
    with open(D / name, encoding="utf-8-sig", newline="") as f:
        return f.read()


def write(name: str, text: str, nl: str) -> None:
    with open(D / name, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", nl))


for name in ("TASKS.md", "HANDOFF.md"):
    if not (D / name).exists():
        sys.exit(f"{D / name} not found; run from the project root")

raw = read("TASKS.md")
nl = "\r\n" if "\r\n" in raw else "\n"
tasks = raw.replace("\r\n", "\n")
if "## Agreed plan" in tasks:
    print("TASKS.md already has the plan")
else:
    write("TASKS.md", tasks.rstrip("\n") + "\n" + PLAN, nl)
    print("TASKS.md: plan added")

raw = read("HANDOFF.md")
nl = "\r\n" if "\r\n" in raw else "\n"
handoff = raw.replace("\r\n", "\n")
if "\nPlan: see" in handoff:
    print("HANDOFF.md already has the plan line")
elif not re.search(r"\nLater:.*", handoff):
    print("warning: HANDOFF.md has no 'Later:' line; plan line not added")
else:
    write("HANDOFF.md", re.sub(r"(\nLater:.*)", lambda m: m.group(1) + HANDOFF_PLAN, handoff,
                               count=1), nl)
    print("HANDOFF.md: plan line added")
