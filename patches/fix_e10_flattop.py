"""Fix test tolerance for the flattop window peak (idempotent, exact match)."""

from pathlib import Path

P = Path(__file__).resolve().parent.parent / "tests" / "engine" / "test_transforms.py"
OLD = """def test_all_windows_have_requested_length_and_peak_one(name):
    w = window(name, 64)
    assert w.shape == (64,) and np.max(w) == pytest.approx(1.0, abs=1e-12)
"""
NEW = """def test_all_windows_have_requested_length_and_peak_one(name):
    # flattop: SciPy's published coefficients are rounded to 9 digits and sum to 1.000000003
    w = window(name, 64)
    assert w.shape == (64,) and np.max(w) == pytest.approx(1.0, abs=1e-8)
"""
with open(P, encoding="utf-8", newline="") as fh:
    text = fh.read()
nl = "\r\n" if "\r\n" in text else "\n"
old, new = OLD.replace("\n", nl), NEW.replace("\n", nl)
if new in text:
    print("already patched")
elif old in text:
    with open(P, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new, 1))
    print("patched")
else:
    raise SystemExit("expected text not found; nothing changed")
