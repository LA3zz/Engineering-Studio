"""B2b-5 fix: cells holding symbolic values display; SymValue.shape; test comparison. Idempotent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NEW_TESTS = '''

def test_cell_of_syms_displays_and_previews():
    ws = run(SYMS + "r = solve(x^2 == 4, x);")
    out = display_text("r", ws["r"])
    assert "2x1 cell array" in out and "{[-2]}" in out and "{[2]}" in out
    assert preview_text(ws["r"])
    assert SymValue(sy.parse("x")).shape == (1, 1)
'''

DISPLAY_OLD = (
    'def display_text(name: str, value: object) -> str:\n'
    '    """Command Window text: symbolic values as ``name =`` + expression, others as before."""\n'
    '    if isinstance(value, SymValue):\n'
    '        return f"{name} =\\n{sym_text(value)}\\n\\n"\n'
    '    return format_value(name, value)\n'
)
DISPLAY_NEW = (
    'def _item_text(v: object) -> str:\n'
    '    if isinstance(v, SymValue):\n'
    '        return "{[" + sym_text(v) + "]}"\n'
    '    rows, cols = size_of(v)\n'
    '    return "{" + f"{rows}x{cols} {class_of(v)}" + "}"\n'
    '\n'
    '\n'
    'def _sym_cell_text(name: str, cell: CellArray) -> str:\n'
    '    rows, cols = cell.shape\n'
    '    lines = ["    " + "  ".join(_item_text(cell.data[i, j]) for j in range(cols))\n'
    '             for i in range(rows)]\n'
    '    return f"{name} =\\n\\n  {rows}x{cols} cell array\\n\\n" + "\\n".join(lines) + "\\n\\n"\n'
    '\n'
    '\n'
    'def display_text(name: str, value: object) -> str:\n'
    '    """Command Window text: symbolic values as ``name =`` + expression, others as before."""\n'
    '    if isinstance(value, SymValue):\n'
    '        return f"{name} =\\n{sym_text(value)}\\n\\n"\n'
    '    if isinstance(value, CellArray) and any(\n'
    '            isinstance(v, SymValue) for v in value.data.ravel()):\n'
    '        return _sym_cell_text(name, value)\n'
    '    return format_value(name, value)\n'
)
IMPORT_OLD = (
    "from engstudio.lang.values import CellArray, CharArray, StructValue, SymValue, "
    "empty_double\n"
)
IMPORT_NEW = (
    "from engstudio.lang.values import (\n    CellArray,\n    CharArray,\n    StructValue,\n"
    "    SymValue,\n    class_of,\n    empty_double,\n    size_of,\n)\n"
)
SHAPE_OLD = '    def __init__(self, expr: object) -> None:\n        self.expr = expr\n'
SHAPE_NEW = (SHAPE_OLD + '\n    @property\n    def shape(self) -> tuple[int, int]:\n'
             '        return (1, 1)\n')
TEST_OLD = (
    '    assert ws["c"].expr == sy.parse("oo").expr '
    'and ws["d"].expr == sy.parse("oo").expr\n'
)
TEST_NEW = ('    oo = sy.parse("oo").expr\n'
            '    assert ws["c"].expr.expr == oo and ws["d"].expr.expr == oo\n')


def read(path: Path) -> str:
    with open(path, newline="", encoding="utf-8") as fh:
        return fh.read()


def edit(path: Path, pairs: list, appended: str = "", marker: str = "") -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    changed = False
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"{path.name}: expected exactly one match for:\n{old}")
        text = text.replace(old, new)
        changed = True
    if appended and marker not in text:
        text = text.rstrip() + nl + appended.replace("\n", nl)
        changed = True
    if changed:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fh.write(text)
    print(("patched: " if changed else "already patched: ") + path.name)


edit(ROOT / "src/engstudio/lang/values.py", [(SHAPE_OLD, SHAPE_NEW)])
edit(ROOT / "src/engstudio/lang/builtins_sym.py",
     [(IMPORT_OLD, IMPORT_NEW), (DISPLAY_OLD, DISPLAY_NEW)])
edit(ROOT / "tests/lang/test_builtins_sym.py", [(TEST_OLD, TEST_NEW)], NEW_TESTS,
     "test_cell_of_syms_displays_and_previews")
