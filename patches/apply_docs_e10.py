"""Docs update for E10 (idempotent). Run: python patches\\apply_docs_e10.py

ruff, full pytest, the E10 test file and the GUI smoke must pass first, else nothing is edited.
Backs up the 6 docs it touches, appends entries (marker-guarded) and applies exact-match
edits to HANDOFF.md and TASKS.md. Nothing is deleted.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "project"
MARKER = "<!-- docs E10 -->"

CHANGELOG = """
## 2026-11-20 - E10
- `engine.transforms`: fft, ifft, rfft, irfft, fftfreq, rfftfreq (NumPy FFT, validated),
  window (rect/boxcar, hann, hamming, blackman, bartlett, flattop; periodic or symmetric),
  amplitude_spectrum (single-sided, window-gain corrected), psd (one-sided periodogram),
  convolve (full/same/valid), butter_filter (low/high/band/bandstop, zero-phase option),
  `SpectrumResult`, `WINDOWS`.
"""

API = """
## engstudio.engine.transforms (E10)
```python
SpectrumResult(freq, values, kind, window, fs, diagnostics)   # kind: "amplitude" | "psd"
fft(x, n=None); ifft(X, n=None); rfft(x, n=None); irfft(X, n=None)
fftfreq(n, d=1.0); rfftfreq(n, d=1.0)
window(name, n, *, periodic=True)          # WINDOWS = rect, boxcar, hann, hamming, ...
amplitude_spectrum(x, fs, *, window="rect", n=None)   # n may only zero-pad
psd(x, fs, *, window="hann", detrend=True)             # units x^2/Hz
convolve(a, b, mode="full")                # "full" | "same" | "valid"
butter_filter(x, fs, cutoff, *, btype="low", order=4, zero_phase=True)
```
- Forward FFT is unnormalised, inverse is 1/N (NumPy/MATLAB convention). Inputs are validated
  1-D copies. A bin-centred sine of amplitude A shows A in `amplitude_spectrum` (DC and even-N
  Nyquist not doubled). Cutoffs in Hz within (0, fs/2); `band`/`bandstop` take (low, high).
- Errors: `ValidationError` (bad values, window name, cutoff, short signal), `DimensionError`
  (matrix input). Uniform sampling is assumed and cannot be checked.
"""

FILES = """
## Added in E10 (2026-11-20)
- src/engstudio/engine/transforms.py
- tests/engine/test_transforms.py
"""

TESTS = """
## 2026-11-20 - E10
- tests/engine/test_transforms.py: {n_new} tests (DFT definition, known pairs, Parseval,
  round trips, window values, bin-centred amplitude, PSD integral, hand-computed convolution,
  Butterworth -3 dB at cutoff, validation).
- Full suite: {count} passed, ruff clean, GUI smoke ok.
"""


def _run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 1800):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                          env=env)


def _passed(r: subprocess.CompletedProcess, label: str) -> int:
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    m = re.search(r"(\d+) passed", tail)
    print(f"{label}: exit {r.returncode}: {tail}")
    if r.returncode != 0 or not m or re.search(r"\d+ (failed|error)", tail):
        sys.exit(f"{label} failed, no docs edited:\n{r.stdout[-3000:]}{r.stderr[-1000:]}")
    return int(m.group(1))


def run_checks() -> tuple[int, int]:
    r = _run([sys.executable, "-m", "ruff", "check", "src", "tests"])
    print(f"ruff: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"ruff failed, no docs edited:\n{r.stdout}{r.stderr}")
    n_new = _passed(_run([sys.executable, "-m", "pytest", "tests/engine/test_transforms.py", "-q"]),
                    "test_ode")
    count = _passed(_run([sys.executable, "-m", "pytest", "-q"]), "pytest")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = _run([sys.executable, "-m", "engstudio.gui", "--smoke"], env=env, timeout=180)
    print(f"gui smoke: exit {r.returncode}")
    if r.returncode != 0:
        sys.exit(f"GUI smoke failed, no docs edited:\n{r.stdout}{r.stderr}")
    return count, n_new


def _read(p: Path) -> str:
    with open(p, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(p: Path, text: str) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, p)


def _append(path: Path, block: str) -> str:
    text = _read(path)
    if MARKER in text:
        return "already present, skipped"
    nl = "\r\n" if "\r\n" in text else "\n"
    body = (MARKER + "\n" + block.strip("\n") + "\n").replace("\n", nl)
    sep = "" if text.endswith(nl) else nl
    _write(path, text + sep + nl + body)
    return "appended"


def _edit_line(text: str, prefix: str, new: str) -> tuple[str, bool]:
    """Replace the whole line starting with ``prefix`` (first match). Keeps line ending."""
    m = re.search(r"^" + re.escape(prefix) + r"[^\r\n]*", text, flags=re.M)
    if not m:
        return text, False
    return text[:m.start()] + new + text[m.end():], True


def _edit_handoff(count: int) -> None:
    p = DOCS / "HANDOFF.md"
    text = _read(p)
    done = []
    text, ok = _edit_line(text, "Last updated: 2026-11-20, after E9",
                          "Last updated: 2026-11-20, after E10 (docs synced).")
    done.append(("last updated", ok))
    old = "max_nfev) done. Next: E10."
    new = ("max_nfev) done; `engine.transforms` (E10: fft/ifft/rfft/irfft, window, "
           "amplitude_spectrum, psd, convolve, butter_filter; SpectrumResult) done. Next: E11.")
    ok = old in text
    text = text.replace(old, new, 1) if ok else text
    done.append(("engine state", ok))
    text, ok = _edit_line(text, "**E10** Fourier transforms and spectral tools",
                          "**E11** Symbolic mathematics in `engine.symbolic` over SymPy: "
                          "`SymExpr` wrapper (parse, simplify, substitute, to-numeric via "
                          "lambdify), diff, integrate (definite/indefinite), solve, series, "
                          "limit, Laplace and inverse Laplace; unsupported or unevaluated "
                          "results are typed errors, never silent; parsing must not use eval "
                          "on raw text; results checked against known identities. "
                          "BEFORE building, list `src\\engstudio\\engine` to see what exists.")
    done.append(("next task", ok))
    old = "Then E11-E12 per"
    ok = old in text
    text = text.replace(old, "Then E12 per", 1) if ok else text
    done.append(("then line", ok))
    text, n = re.subn(r"(`python -m pytest -q` )\d+( passed, ruff clean, GUI smoke ok \()E1-E9\)",
                      rf"\g<1>{count}\g<2>E1-E10)", text)
    done.append(("verified line", n > 0))
    _write(p, text)
    for name, ok in done:
        print(f"HANDOFF.md {name}: {'edited' if ok else 'not found, skipped'}")


def _edit_tasks(count: int) -> None:
    p = DOCS / "TASKS.md"
    text = _read(p)
    old = "- [ ] E10 Fourier transforms and spectral tools"
    if old in text:
        done = f"- [x] E10 (verified 2026-11-20, {count} tests) Fourier transforms/spectral tools"
        text = text.replace(old, done, 1)
        _write(p, text)
        print("TASKS.md: E10 ticked")
    else:
        print("TASKS.md: E10 line not found, skipped")


def main() -> int:
    names = ["CHANGELOG.md", "TEST_STATUS.md", "API_REFERENCE.md", "FILE_STRUCTURE.md",
             "HANDOFF.md", "TASKS.md"]
    missing = [n for n in names if not (DOCS / n).is_file()]
    if missing:
        sys.exit(f"missing in {DOCS}: {missing}. Nothing changed.")
    count, n_new = run_checks()
    backup = ROOT / "patches" / f"backup_docs_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(DOCS / n, backup / n)
    print(f"backup: {backup}")
    plan = [("CHANGELOG.md", CHANGELOG), ("API_REFERENCE.md", API), ("FILE_STRUCTURE.md", FILES),
            ("TEST_STATUS.md", TESTS.format(count=count, n_new=n_new))]
    for n, block in plan:
        print(f"{n}: {_append(DOCS / n, block)}")
    _edit_handoff(count)
    _edit_tasks(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
