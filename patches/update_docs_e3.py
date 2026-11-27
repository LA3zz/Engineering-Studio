"""Record E2 and E3 in docs\\project after ruff, pytest and the GUI smoke test pass.
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
t = sub(t, "- [ ] E2 ", "- [x] E2 ", "E2")
t = sub(t, "- [ ] E3 ", "- [x] E3 ", "E3")
t = sub(t, "- [x] E3 numerical", f"- [x] E3 (verified {today}, {n} tests) numerical", "E3 note")
write("TASKS.md", t)

# HANDOFF.md
h = read("HANDOFF.md")
h = re.sub(r"Last updated: .*?\.", f"Last updated: {today}, after E3.", h, count=1)
h = sub(h, "(E1). Next: E2.",
        "(E1); `engine.decomp` lu/qr/cholesky/svd/eig/eigh (E2); `engine.calculus` derivative, "
        "gradient, jacobian, derivative_data, quad, dblquad, trapz, simpson, cumtrapz (E3). "
        "Next: E4.", "engine")
start = h.index("## Next task")
end = h.index("## Files that matter now")
h = (h[:start] + "## Next task\n**E4** root finding and equation solving in `engine.roots`: scalar "
     "roots (bracketing brentq/bisect, Newton with derivative or numeric derivative), systems "
     "(fsolve-style with Jacobian), polynomial roots; `RootResult(root, converged, iterations, "
     "residual, diagnostics)`; explicit tolerances; typed errors; tests vs analytic roots.\n\n"
     "Then E5-E12 per 'Agreed plan' in TASKS.md. Test-writing note: real pytest `approx` "
     "rejects nested lists; wrap in np.array.\n\n" + h[end:])
write("HANDOFF.md", h)

for name, entry in {
    "CHANGELOG.md": f"\n## {today}\n- E2 engine.decomp (lu, qr, cholesky, svd, eig, eigh).\n"
                    "- E3 engine.calculus (finite differences, quad/dblquad, trapz/simpson).\n",
    "TEST_STATUS.md": f"\n## {today}\n- pytest: {n} passed; ruff clean; GUI smoke ok.\n",
    "API_REFERENCE.md": "\n## engstudio.engine.decomp (E2)\n"
        "`lu -> LuResult(P, L, U)` with `P@A = L@U`; `qr(a, mode) -> QrResult`; "
        "`cholesky(a, lower=False) -> CholResult`; `svd(a, full=False) -> SvdResult(U, s, V)`; "
        "`eig`/`eigh -> EigResult(values, vectors, residual, vector_rcond, diagnostics)`. "
        "eig sorts by real part; signs/phases are LAPACK's.\n"
        "\n## engstudio.engine.calculus (E3)\n"
        "`derivative(f, x, order=1|2, h=None, method='central'|'forward'|'backward')`, "
        "`gradient(f, x)`, `jacobian(f, x)`, `derivative_data(x, y)`; "
        "`quad(f, a, b, rtol, atol, limit)` and `dblquad(f, x0, x1, y0, y1)` return "
        "`IntegrateResult(value, error_estimate, nfev, converged, diagnostics)`; "
        "`trapz`, `simpson`, `cumtrapz` for samples. Real finite scalar functions only.\n",
}.items():
    path = DOCS / name
    old = read(name) if path.exists() else f"# {name[:-3]}\n"
    write(name, old.rstrip("\n") + "\n" + entry)
print(f"docs updated ({n} tests passed)")
