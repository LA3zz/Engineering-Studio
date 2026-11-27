"""B2b-2: wire builtins_data into the in-process kernel (exact-match, idempotent).

Run from the project root:  python patches\apply_b2b2.py
"""
import sys

PATH = "src/engstudio/app/kernel/inprocess.py"

EDITS = [
    ("from engstudio.lang.builtins_decomp import install_decomp\n",
     "from engstudio.lang.builtins_data import install_data\n"
     "from engstudio.lang.builtins_decomp import install_decomp\n"),
    ("        install_poly(self._interp)\n",
     "        install_poly(self._interp)\n        install_data(self._interp)\n"),
    ('    "polynomials": ("Polynomials", ("poly", "roots", "polyval", "polyfit")),\n',
     '    "numerics": ("Numerical analysis", ("trapz", "cumtrapz", "interp1")),\n'
     '    "statistics": ("Statistics", ("std", "var", "median", "rms", "zscore")),\n'
     '    "signal": ("Signal processing", ("fft", "ifft")),\n'
     '    "polynomials": ("Polynomials", ("poly", "roots", "polyval", "polyfit")),\n'),
]

with open(PATH, newline="") as fh:
    raw = fh.read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
for old, new in EDITS:
    if new in text:
        continue
    if text.count(old) != 1:
        sys.exit(f"patch failed: expected exactly one match for:\n{old}")
    text = text.replace(old, new)
with open(PATH, "w", newline="") as fh:
    fh.write(text.replace("\n", "\r\n") if crlf else text)
print("inprocess.py patched (B2b-2)")
