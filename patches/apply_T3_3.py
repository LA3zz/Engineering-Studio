"""T3.3 follow-up: ruff cleanup of two helper files + doc sync. Exact-match, idempotent.

Run from the project root.
"""
from pathlib import Path

ROOT = Path(".")
D = ROOT / "docs" / "project"

IMPORTS_OLD = (
    "import collections, dataclasses, importlib, inspect, pkgutil, subprocess, sys\n"
    "import engstudio.engine as eng"
)
IMPORTS_NEW = (
    "import collections\nimport dataclasses\nimport importlib\nimport inspect\n"
    "import pkgutil\nimport subprocess\nimport sys\n\nimport engstudio.engine as eng"
)
COUNTER_OLD = (
    'c = collections.Counter(l.split("::")[0] '
    'for l in r.stdout.splitlines() if "::" in l)'
)
COUNTER_NEW = (
    'c = collections.Counter(\n'
    '    line.split("::")[0] for line in r.stdout.splitlines() if "::" in line\n'
    ")"
)
PLAN_OLD = (
    '("TEST_STATUS.md", TESTS.format(count=count, n_new=n_new, sympy_version=_sympy_version()))]'
)
PLAN_NEW = (
    '("TEST_STATUS.md",\n'
    "             TESTS.format(count=count, n_new=n_new, sympy_version=_sympy_version()))]"
)

EDITS = {
    ROOT / "scripts" / "dump_api.py": [(IMPORTS_OLD, IMPORTS_NEW), (COUNTER_OLD, COUNTER_NEW)],
    ROOT / "patches" / "apply_docs_e11.py": [(PLAN_OLD, PLAN_NEW)],
    D / "TASKS.md": [
        ("(41 tests; pending user run)", "(verified 2026-11-21, 1034 tests)"),
        ("- [ ] T3.3 `lang.parser` (Pratt parser: tokens -> AST; not started)",
         "- [x] T3.3 `lang.parser` + tests (pending user run)\n"
         "- [ ] T3.4 interpreter core: value model, evaluator (not started; scope to agree)"),
    ],
    D / "HANDOFF.md": [
        ("Next in that series: T3.3 `lang.parser`.",
         "T3.3 `lang.parser` done: `parse(source, file) -> Program`, `ParseError` (E_PARSE, "
         "`.location`); command syntax (`hold on`), `s.(n)`, `for (i=..)` unsupported. "
         "Next in that series: T3.4 interpreter core (scope to agree)."),
    ],
}

for path, pairs in EDITS.items():
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            print(f"{path}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"{path}: patched")
        else:
            raise SystemExit(f"{path}: expected text not found: {old[:60]!r}")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
