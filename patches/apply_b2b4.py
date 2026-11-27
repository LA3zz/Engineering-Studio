"""Apply B2b-4: engine.stats.t_quantile, register builtins_analysis, update docs. Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "docs" / "project"

T_QUANTILE = '''

def t_quantile(p: float, dof: float) -> float:
    """Student-t quantile (inverse CDF) for probability ``p`` in (0, 1) and ``dof`` > 0."""
    pv = np.asarray(p)
    dv = np.asarray(dof)
    if pv.size != 1 or pv.dtype.kind not in "biuf" or not 0.0 < float(pv) < 1.0:
        raise ValidationError("p must be a number in (0, 1)")
    if dv.size != 1 or dv.dtype.kind not in "biuf" or not float(dv) > 0.0:
        raise ValidationError("dof must be a positive number")
    return float(_st.t.ppf(float(pv), float(dv)))
'''


def read(path: Path) -> str:
    with open(path, newline="", encoding="utf-8") as fh:
        return fh.read()


def write(path: Path, text: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)


def edit(path: Path, pairs: list, marker: str) -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    if marker in text:
        print(f"already patched: {path.name}")
        return
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if text.count(old) != 1:
            raise SystemExit(f"{path.name}: expected exactly one match for:\n{old}")
        text = text.replace(old, new)
    write(path, text)
    print(f"patched: {path.name}")


def append(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    if marker in text:
        print(f"already patched: {path.name}")
        return
    nl = "\r\n" if "\r\n" in text else "\n"
    write(path, text.rstrip() + nl + nl + block.replace("\n", nl) + nl)
    print(f"patched: {path.name}")


stats_path = ROOT / "src/engstudio/engine/stats.py"
edit(stats_path, [
    ('    "summary", "ttest_1samp", "ttest_ind", "ttest_paired", "var", "zscore",\n]',
     '    "summary", "t_quantile", "ttest_1samp", "ttest_ind", "ttest_paired", "var",\n'
     '    "zscore",\n]'),
], "def t_quantile")
if stats_path.exists() and "def t_quantile" not in read(stats_path):
    text = read(stats_path)
    nl = "\r\n" if "\r\n" in text else "\n"
    write(stats_path, text.rstrip() + nl + T_QUANTILE.replace("\n", nl))
    print("added t_quantile to stats.py")

edit(ROOT / "src/engstudio/app/kernel/inprocess.py", [
    ("from engstudio.lang.builtins_core import install_core\n",
     "from engstudio.lang.builtins_analysis import install_analysis\n"
     "from engstudio.lang.builtins_core import install_core\n"),
    ("        install_funcs(self._interp)\n",
     "        install_funcs(self._interp)\n        install_analysis(self._interp)\n"),
    ('("trapz", "cumtrapz", "interp1")',
     '("trapz", "cumtrapz", "interp1", "interp2")'),
    ('("std", "var", "median", "rms", "zscore")',
     '("std", "var", "median", "rms", "zscore", "quantile",\n'
     '                                              "prctile", "ttest", "ttest2")'),
    ('("fzero", "fsolve", "fminsearch")',
     '("fzero", "fsolve", "fminsearch", "fminbnd",\n'
     '                                                        "fminunc", "linprog")'),
], "install_analysis")

append(D / "CHANGELOG.md",
       "## B2b-4 (2026-11-25)\n- Added `lang.builtins_analysis` (interp2, fminbnd, fminunc, "
       "linprog, quantile, prctile, ttest, ttest2) and `engine.stats.t_quantile`. Symbolic "
       "bindings deferred (value-model decision).", "B2b-4 (2026-11-25)")
append(D / "TEST_STATUS.md",
       "## B2b-4 (2026-11-25)\n- tests/lang/test_builtins_analysis.py (10 tests), "
       "tests/engine/test_stats_tquantile.py (7 tests): PENDING user run.",
       "B2b-4 (2026-11-25)")
append(D / "HANDOFF.md",
       "## B2b-4 (2026-11-25)\n- `lang.builtins_analysis` (`install_analysis`) installed after "
       "`install_funcs`; `engine.stats.t_quantile` added. Pending user run. Symbolic bindings "
       "(B2b-5) wait for a value-model decision. Next: K3 design options.",
       "B2b-4 (2026-11-25)")
edit(D / "TASKS.md", [
    ("  - [ ] B2b-4 leftovers: interp2, fminbnd/fminunc, linprog, quantile/prctile, ttest, "
     "symbolic bindings",
     "  - [x] B2b-4 `lang.builtins_analysis`: interp2, fminbnd/fminunc, linprog, quantile/"
     "prctile, ttest/ttest2 (pending user run)\n"
     "  - [ ] B2b-5 symbolic bindings (needs a value-model decision)"),
], "B2b-5")
