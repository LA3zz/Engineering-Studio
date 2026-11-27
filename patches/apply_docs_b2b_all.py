"""Docs sync after B2b-1 and B2b-2: TASKS, HANDOFF, CHANGELOG, TEST_STATUS.

Exact-match and idempotent; safe to run even if apply_docs_b2b.py was run before.
Run from the project root:  python patches\apply_docs_b2b_all.py
"""
import os
import sys

DOCS = os.path.join("docs", "project")


def load(path):
    with open(path, newline="") as fh:
        raw = fh.read()
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def save(path, text, crlf):
    with open(path, "w", newline="") as fh:
        fh.write(text.replace("\n", "\r\n") if crlf else text)
    print("patched", path)


def patch(name, edits, append=None):
    path = os.path.join(DOCS, name)
    text, crlf = load(path)
    for old, new in edits:
        if new in text:
            continue
        if text.count(old) != 1:
            sys.exit(f"{path}: expected exactly one match for:\n{old}")
        text = text.replace(old, new)
    if append and append[0] not in text:
        text = text.rstrip("\n") + "\n\n" + append[0] + "\n" + append[1]
    save(path, text, crlf)


patch("TASKS.md", [(
    "- [ ] B2b remaining engine bindings (trapz, polyfit, interp1, fzero, ode45, fft, std, ...); "
    "attach engine calculus/roots/regression/interp/stats/ode/transforms .py\n",
    "- [~] B2b remaining engine bindings (split into slices)\n"
    "  - [x] B2b-1 `lang.builtins_poly`: poly, roots, polyval, polyfit; `close` (no-op until "
    "Phase 5) and `format short g` accepted (verified 2026-11-24)\n"
    "  - [x] B2b-2 `lang.builtins_data`: trapz, cumtrapz, interp1, std, var, median, rms, zscore, "
    "fft, ifft (verified 2026-11-24, 1837 tests, ruff clean)\n"
    "  - [ ] B2b-3 handle-based: fzero, integral/quad, ode45, fminsearch, fsolve\n"
    "  - [ ] B2b-4 leftovers: interp2, fminbnd/fminunc, linprog, quantile/prctile, ttest, "
    "symbolic bindings\n")])

NOTES = (
    "## B2b status and notes for the next chat (2026-11-24)\n"
    "- B2b-1 `lang.builtins_poly` (poly, roots, polyval, polyfit) and B2b-2 `lang.builtins_data` "
    "(trapz, cumtrapz, interp1, std, var, median, rms, zscore, fft, ifft) are done and verified "
    "by the user: 1837 tests passed, ruff clean, probes ran correctly. Both are installed in "
    "`InProcessKernelClient` after `install_extra` (`install_poly`, `install_data`) and listed in "
    "new toolbox categories (numerics, statistics, signal, polynomials).\n"
    "- Binding pattern: `xxx_functions(interp) -> dict[name, fn(args, nargout) -> list]` plus "
    "`install_xxx(interp)`; helpers imported from `lang.builtins_core` (`_arith`, `_real`, `_int`, "
    "`_need`, `_text`, `Builtin`); engine diagnostics go to `interp.host.diagnostic(d)`; vectors "
    "keep orientation, matrices are processed per column (`_apply` in builtins_data); every "
    "function name must be in exactly one `_CATEGORIES` entry in inprocess.py. Tests build "
    "`Interpreter()`, `install_core`, `install_xxx`, `execute(code, None)` and read "
    "`interp.workspace[name]`.\n"
    "- Calling a handle from a builtin (as cellfun/feval do): `interp.call(func, args, nargout)` "
    "returns a list of values; `func` is a `FunctionHandle` (or `FunctionHandle(name=text)` for a "
    "name string). Let `Cancelled` propagate; engine errors are `EngStudioError` subclasses.\n"
    "- Next: B2b-3 handle-based functions (fzero via engine.roots.brentq/bisect, integral/quad via "
    "engine.calculus.quad, ode45/ode23/ode15s via engine.ode.solve_ode, fminsearch via "
    "engine.optimize.minimize Nelder-Mead, fsolve via engine.roots.fsolve). Attach roots.py, "
    "calculus.py, optimize.py, ode.py, inprocess.py, builtins_data.py. Then B2b-4 leftovers.\n"
    "- Plotting stays Phase 5. `close` is a no-op and `format short g` displays as short until "
    "then. The user's MECH 322 script (Code.m): `hold on` (command syntax) is a parse error, so "
    "F5 on the whole file fails; its numeric part runs with F9 on a selection.\n\n"
)
patch("HANDOFF.md", [
    ("Last updated: 2026-11-21, after G7 (docs synced).\n",
     "Last updated: 2026-11-24, after B2b-2 (1837 tests passed, ruff clean).\n"),
    ("## Waiting on the user\n", NOTES + "## Waiting on the user\n"),
])

patch("CHANGELOG.md", [(
    "## [Unreleased]\n",
    "## 2026-11-24 - B2b-1, B2b-2\n"
    "- `lang.builtins_poly`: poly, roots, polyval, polyfit. `lang.builtins_data`: trapz, cumtrapz, "
    "interp1 (extrap / fill value, `cubic` = pchip), std, var, median, rms, zscore, fft, ifft "
    "(vectors keep orientation, matrices per column). Documented differences from MATLAB: "
    "errors instead of NaN outside the data range, polyfit has one output, no `dim` argument.\n"
    "- Kernel: `close` command (no-op until Phase 5), `format short g` accepted with an info "
    "diagnostic, new toolbox categories.\n\n"
    "## [Unreleased]\n")])

patch("TEST_STATUS.md", [], (
    "<!-- docs B2b-1/2 -->",
    "## 2026-11-24 - B2b-1, B2b-2 (Windows 10, Python 3.11.9, user-run)\n"
    "- tests/lang/test_builtins_poly.py, tests/lang/test_builtins_data.py, "
    "tests/app/test_kernel_b2b1.py added.\n"
    "- Full suite: `python -m pytest -q` 1837 passed in 190.99 s; `ruff check src tests` clean. "
    "The usual `QThreadStorage ... destroyed` line prints at exit (known Qt teardown issue).\n"
    "- Manual probes in the GUI (probe_b2b1.m, probe_b2b2.m): output as expected.\n"
    "- Not yet verified: Code.m (MECH 322) numeric section; frozen build with the GUI."))
