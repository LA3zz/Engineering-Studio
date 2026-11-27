"""Record G6.2 and E1 in docs\\project after ruff, pytest and the GUI smoke test pass.
Run from the project root: python patches\\update_docs_e1.py"""
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "project"


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


rc, out = run([sys.executable, "-m", "ruff", "check", "src", "tests"])
if rc:
    raise SystemExit("ruff failed; docs not updated\n" + out)
rc, out = run([sys.executable, "-m", "pytest", "-q"])
m = re.search(r"(\d+) passed", out)
if rc or not m or "failed" in out:
    raise SystemExit("pytest failed; docs not updated\n" + out[-1500:])
n = m.group(1)
rc, out = run([sys.executable, "-m", "engstudio.gui", "--smoke"])
if rc:
    raise SystemExit("smoke test failed; docs not updated\n" + out)
today = datetime.date.today().isoformat()


def read(name):
    with open(DOCS / name, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def write(name, text):
    with open(DOCS / name, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def sub(text, old, new, label):
    if new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"ANCHOR NOT FOUND ({label}): {old[:60]!r}")
    return text.replace(old, new)


# TASKS.md
t = read("TASKS.md")
t = sub(t, "- [ ] G6.2 Documentation panel",
        f"- [x] G6.2 Documentation panel ({n} tests, verified {today})", "G6.2")
t = sub(t, "- [ ] E1 ", "- [x] E1 ", "E1")
t = sub(t, "- [x] E1 engine scaffold",
        f"- [x] E1 (verified {today}, {n} tests) engine scaffold", "E1 note")
write("TASKS.md", t)

# HANDOFF.md
h = read("HANDOFF.md")
h = re.sub(r"Last updated: .*?\.", f"Last updated: {today}, after E1.", h, count=1)
h = sub(h, "Placeholder remains: Documentation. ",
        "G6.2 done: `app.docs.DocService` + `gui.docs_panel` (Markdown pages in "
        "`app/docs_pages`, Back/Forward/Home, internal links, theme-aware). ", "state")
h = sub(h, "- Interpreter: `lang.lexer` done",
        "- Engine: `engine.validation` (as_matrix/as_vector/singular_error) and `engine.linalg` "
        "(solve, inv, det, trace, matmul, transpose, ctranspose, dot, cross, norm, rank, cond, "
        "rcond; SolveResult/InvResult) done (E1). Next: E2.\n- Interpreter: `lang.lexer` done",
        "engine")
start = h.index("## Next task")
end = h.index("## Files that matter now")
h = (h[:start] + "## Next task\n**E2** decompositions (LU, QR, Cholesky, SVD) and eigenvalues/"
     "eigenvectors in `engine.linalg` or `engine.decomp`: results checked against analytic "
     "values (reconstruction A = QR etc., known eigenpairs), typed errors, documented "
     "sign/ordering differences from MATLAB.\n\nThen E3-E12 per 'Agreed plan' in TASKS.md. "
     "Later: wire diagnostics `location_activated` to the editor, real kernel process, GUI in "
     "the PyInstaller spec (docs pages are already in `datas`), Save/Load Workspace.\n\n" + h[end:])
h = sub(h, "src/engstudio/gui/*.py,", "src/engstudio/engine/*.py, src/engstudio/gui/*.py,",
        "files")
write("HANDOFF.md", h)

# ARCHITECTURE.md
a = read("ARCHITECTURE.md")
a = sub(a, "Docs shipped as local HTML/Markdown in `resources/docs`",
        "Docs shipped as local Markdown in `engstudio/app/docs_pages` (inside a known package "
        "so the layer test accepts it)", "arch docs")
write("ARCHITECTURE.md", a)

# appended logs
for name, entry in {
    "CHANGELOG.md": f"\n## {today}\n"
                    "- G6.2 Documentation panel (app.docs, gui.docs_panel, 10 pages).\n"
                    "- E1 engine.validation and engine.linalg.\n",
    "TEST_STATUS.md": f"\n## {today}\n- pytest: {n} passed; ruff clean; GUI smoke ok.\n",
    "API_REFERENCE.md": "\n## engstudio.engine.linalg (E1)\n"
        "`solve(a, b) -> SolveResult(x, residual_norm, rcond, method, diagnostics)`; "
        "`inv(a) -> InvResult(value, rcond, diagnostics)`; `det`, `trace`, `matmul`, "
        "`transpose`, `ctranspose`, `dot` (conjugates first arg), `cross`, "
        "`norm(x, kind=2)`, `rank(a, tol=None)`, `cond(a, p=2)`, `rcond(a)`.\n"
        "rcond < eps -> SingularMatrixError; rcond < 1e-12 -> warning diagnostic ILL_CONDITIONED. "
        "Inputs are validated copies (NaN/Inf, empty, ragged, non-numeric -> ValidationError; "
        "shape problems -> DimensionError). 1-D b gives 1-D x.\n",
}.items():
    path = DOCS / name
    old = read(name) if path.exists() else f"# {name[:-3]}\n"
    write(name, old.rstrip("\n") + "\n" + entry)
print(f"docs updated ({n} tests passed)")
