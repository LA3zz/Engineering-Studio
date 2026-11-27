"""Command Window text for values (T3.4d): ``format_value``, ``format_disp``, ``unparse``.

The output imitates MATLAB's ``format short``; it is an approximation, not a copy:

* real scalars: integers print as integers (below 1e9); other numbers print with five
  significant digits in fixed notation for 1e-3 <= |x| < 1e5, else as ``1.2346e+05``;
* real matrices: integer matrices use width max(6, digits + 3); other matrices use four
  decimals in width 10 and a common ``1.0e+03 *`` scale factor when the largest entry is >= 1e3
  or < 1e-3; a huge dynamic range falls back to exponent notation so no entry prints as 0.0000;
* wide matrices are split into ``Columns a through b`` chunks of at most 80 characters;
* complex numbers print as ``3.0000 + 4.0000i`` (``3 + 4i`` when both parts are integers);
* empty arrays print as ``[]`` (0x0) or ``1x0 empty double``; sizes use ASCII ``x``;
* cells show one ``{...}`` entry per element, structs one ``name: value`` line per field,
  function handles their source text (``unparse``).

``unparse`` turns an expression AST back into source text with the fewest parentheses that
keep the tree unchanged (``parse(unparse(e))`` equals ``e``); spaces surround binary
operators except ``^``, ``.^`` and ranges.
"""

from __future__ import annotations

import math

import numpy as np

from engstudio.lang import ast as A
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
)

_LINE_WIDTH = 80

# ------------------------------------------------------------------- unparse
_PREC = {
    "||": 1, "&&": 2, "|": 3, "&": 4,
    "==": 5, "~=": 5, "<": 5, "<=": 5, ">": 5, ">=": 5,
    "+": 7, "-": 7,
    "*": 8, "/": 8, "\\": 8, ".*": 8, "./": 8, ".\\": 8,
    "^": 10, ".^": 10,
}
_RANGE, _UNARY, _POSTFIX, _ATOM = 6, 9, 11, 12


def _prec(node: A.Node) -> int:
    if isinstance(node, A.Binary):
        return _PREC[node.op]
    if isinstance(node, A.Range):
        return _RANGE
    if isinstance(node, A.Unary):
        return _UNARY
    if isinstance(node, (A.Postfix, A.Index, A.CellIndex, A.Field)):
        return _POSTFIX
    if isinstance(node, A.AnonFunc):
        return 0
    return _ATOM


def _number(x: float) -> str:
    if math.isfinite(x) and x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return repr(float(x))


def unparse(node: A.Node) -> str:
    """Source text of an expression node."""

    def child(n: A.Node, minimum: int) -> str:
        text = unparse(n)
        return f"({text})" if _prec(n) < minimum else text

    def items(nodes) -> str:
        return ", ".join(unparse(n) for n in nodes)

    if isinstance(node, A.Number):
        return _number(node.value)
    if isinstance(node, A.Imag):
        return _number(node.value.imag) + "i"
    if isinstance(node, A.String):
        q = '"' if node.double_quoted else "'"
        return q + node.value.replace(q, q + q) + q
    if isinstance(node, A.Ident):
        return node.name
    if isinstance(node, A.Colon):
        return ":"
    if isinstance(node, A.End):
        return "end"
    if isinstance(node, A.Unary):
        return node.op + child(node.operand, _UNARY)
    if isinstance(node, A.Postfix):
        return child(node.operand, _POSTFIX) + node.op
    if isinstance(node, A.Binary):
        p = _PREC[node.op]
        left, right = child(node.left, p), child(node.right, p + 1)
        sep = "" if node.op in ("^", ".^") else " "
        return f"{left}{sep}{node.op}{sep}{right}"
    if isinstance(node, A.Range):
        parts = [node.start] + ([node.step] if node.step is not None else []) + [node.stop]
        return ":".join(child(n, _RANGE + 1) for n in parts)
    if isinstance(node, A.Index):
        return f"{child(node.target, _POSTFIX)}({items(node.args)})"
    if isinstance(node, A.CellIndex):
        return f"{child(node.target, _POSTFIX)}{{{items(node.args)}}}"
    if isinstance(node, A.Field):
        return f"{child(node.target, _POSTFIX)}.{node.name}"
    if isinstance(node, A.Matrix):
        return "[" + "; ".join(items(row) for row in node.rows) + "]"
    if isinstance(node, A.CellLiteral):
        return "{" + "; ".join(items(row) for row in node.rows) + "}"
    if isinstance(node, A.FuncHandle):
        return "@" + node.name
    if isinstance(node, A.AnonFunc):
        return f"@({', '.join(node.params)}) {unparse(node.body)}"
    raise ValueError(f"cannot unparse {type(node).__name__}")


def handle_text(h: FunctionHandle) -> str:
    """``@sin`` or ``@(x) x.^2 + 1``."""
    if h.is_anonymous:
        return f"@({', '.join(h.params)}) {unparse(h.body)}"  # type: ignore[arg-type]
    return f"@{h.name}"


# ------------------------------------------------------------------- numbers
def _special(x: float) -> str | None:
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    return None


def _is_int(x: float) -> bool:
    return math.isfinite(x) and x == round(x) and abs(x) < 1e9


def _decimals(a: float) -> int | None:
    """Decimals for fixed notation of magnitude ``a`` (None: use exponent notation)."""
    if a == 0:
        return 0
    if not (1e-3 <= a < 1e5):
        return None
    if a < 10:
        return 4
    return max(0, 4 - int(math.floor(math.log10(a))))


def _real_text(x: float, decimals: int | None = None, force: bool = False) -> str:
    """One real number; ``force`` skips the integer shortcut (used inside complex parts)."""
    special = _special(x)
    if special:
        return special
    if _is_int(x) and not force:
        return str(int(x))
    d = _decimals(abs(x)) if decimals is None else decimals
    if d is None:
        return f"{x:.4e}"
    return f"{x:.{d}f}"


def _complex_text(z: complex) -> str:
    re, im = z.real, z.imag
    if _is_int(re) and _is_int(im):
        re_s, im_s = str(int(re)), str(int(abs(im)))
    else:
        top = max((abs(p) for p in (re, im) if math.isfinite(p)), default=0.0)
        d = _decimals(top)
        re_s = _real_text(re, d, force=True)
        im_s = _real_text(abs(im), d, force=True)
    sign = "-" if (im < 0 or (im == 0 and math.copysign(1.0, im) < 0)) else "+"
    return f"{re_s} {sign} {im_s}i"


def _scalar_text(v) -> str:
    x = v.item()
    if isinstance(x, (bool, np.bool_)):
        return "1" if x else "0"
    if isinstance(x, complex):
        return _complex_text(x)
    return _real_text(float(x))


def _pad_rows(cells: list[list[str]], width: int) -> list[str]:
    return ["".join(c.rjust(width) for c in row) for row in cells]


def _chunked(cells: list[list[str]], width: int) -> list[str]:
    ncols = len(cells[0])
    per = max(1, _LINE_WIDTH // width)
    if ncols <= per:
        return _pad_rows(cells, width)
    lines: list[str] = []
    for start in range(0, ncols, per):
        stop = min(start + per, ncols)
        label = (
            f"Column {start + 1}" if stop - start == 1 else f"Columns {start + 1} through {stop}"
        )
        lines += [f"  {label}", ""]
        lines += _pad_rows([row[start:stop] for row in cells], width)
        lines.append("")
    return lines[:-1]


def _matrix_lines(arr: np.ndarray) -> list[str]:
    """Lines of a numeric/logical matrix with more than one element."""
    if arr.dtype.kind == "c":
        cells = [[_complex_text(complex(z)) for z in row] for row in arr]
        width = max(len(c) for row in cells for c in row) + 3
        return _chunked(cells, width)
    data = arr.astype(np.float64)
    finite = np.isfinite(data)
    if arr.dtype == np.bool_ or all(_is_int(float(x)) or not math.isfinite(float(x))
                                    for x in data.ravel()):
        cells = [[_real_text(float(x)) for x in row] for row in data]
        width = max(6, max(len(c) for row in cells for c in row) + 3)
        return _chunked(cells, width)
    nonzero = np.abs(data[finite & (data != 0)])
    top = float(nonzero.max()) if nonzero.size else 0.0
    low = float(nonzero.min()) if nonzero.size else 0.0
    header: list[str] = []
    if nonzero.size and low / top < 1e-5:
        cells = [[_special(float(x)) or f"{x:.4e}" for x in row] for row in data]
        width = max(len(c) for row in cells for c in row) + 3
        return _chunked(cells, width)
    if top >= 1e3 or 0 < top < 1e-3:
        exp = int(math.floor(math.log10(top)))
        data = data / 10.0 ** exp
        header = [f"   1.0e{exp:+03d} *", ""]
    cells = [[_special(float(x)) or f"{x:.4f}" for x in row] for row in data]
    width = max(10, max(len(c) for row in cells for c in row) + 2)
    return header + _chunked(cells, width)


# -------------------------------------------------------------- summaries
def _dims(v) -> str:
    r, c = v.shape
    return f"{r}x{c}"


def _empty_text(v) -> str:
    if v.shape == (0, 0):
        return "[]"
    return f"{_dims(v)} empty {class_of(v)}"


def _char_quoted(v: CharArray) -> str | None:
    return "'" + v.to_str().replace("'", "''") + "'" if v.shape[0] <= 1 else None


def _cell_element(v) -> str:
    if isinstance(v, np.ndarray):
        if v.size == 1:
            return f"[{_scalar_text(v)}]"
        return "[]" if v.shape == (0, 0) else f"{_dims(v)} {class_of(v)}"
    if isinstance(v, CharArray):
        return _char_quoted(v) or f"{_dims(v)} char"
    if isinstance(v, FunctionHandle):
        return handle_text(v)
    return f"{_dims(v) if not isinstance(v, StructValue) else '1x1'} {class_of(v)}"


def _field_text(v) -> str:
    if isinstance(v, np.ndarray):
        if v.size == 1:
            return _scalar_text(v)
        return "[]" if v.shape == (0, 0) else f"[{_dims(v)} {class_of(v)}]"
    if isinstance(v, CharArray):
        return _char_quoted(v) or f"[{_dims(v)} char]"
    if isinstance(v, CellArray):
        return f"{{{_dims(v)} cell}}"
    if isinstance(v, StructValue):
        return "[1x1 struct]"
    return handle_text(v)


def _cell_lines(c: CellArray) -> list[str]:
    rows, cols = c.shape
    texts = [["{" + _cell_element(c.data[i, j]) + "}" for j in range(cols)] for i in range(rows)]
    widths = [max(len(texts[i][j]) for i in range(rows)) for j in range(cols)]
    lines = [f"  {rows}x{cols} cell array", ""]
    for row in texts:
        cells = (t.ljust(w) for t, w in zip(row, widths, strict=True))
        lines.append("    " + "    ".join(cells).rstrip())
    return lines


def _struct_lines(s: StructValue) -> list[str]:
    lines = ["  struct with fields:", ""]
    lines += [f"    {name}: {_field_text(val)}" for name, val in s.items()]
    return lines


# ------------------------------------------------------------------- public
def format_value(name: str, value: object) -> str:
    """Text MATLAB would print for the statement ``name = value`` (ends with a newline)."""
    class_of(value)  # validates
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return f"{name} = {_empty_text(value)}\n"
        if value.size == 1:
            return f"{name} = {_scalar_text(value)}\n"
        body = _matrix_lines(value)
    elif isinstance(value, CharArray):
        if value.data.size == 0:
            return f"{name} = ''\n"
        if value.shape[0] <= 1:
            return f"{name} = {value.to_str()}\n"
        body = ["".join(row) for row in value.data]
    elif isinstance(value, CellArray):
        if value.shape == (0, 0):
            return f"{name} = {{}}\n"
        if value.data.size == 0:
            return f"{name} = {_dims(value)} empty cell array\n"
        body = _cell_lines(value)
    elif isinstance(value, StructValue):
        body = _struct_lines(value)
    else:
        text = handle_text(value)  # type: ignore[arg-type]
        body = ["  function_handle with value:", "", "    " + text]
    return "\n".join([f"{name} =", "", *body, ""]) + "\n"


def format_disp(value: object) -> str:
    """Text of ``disp(value)`` (ends with a newline; empty arrays print nothing)."""
    class_of(value)
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return ""
        if value.size == 1:
            return _scalar_text(value) + "\n"
        return "\n".join(_matrix_lines(value)) + "\n"
    if isinstance(value, CharArray):
        if value.data.size == 0:
            return "\n"
        return "\n".join("".join(row) for row in value.data) + "\n"
    if isinstance(value, CellArray):
        return "{}\n" if value.shape == (0, 0) else "\n".join(_cell_lines(value)) + "\n"
    if isinstance(value, StructValue):
        return "\n".join(_struct_lines(value)) + "\n"
    return handle_text(value) + "\n"  # type: ignore[arg-type]


def short_text(value: object, limit: int = 40) -> str:
    """One-line preview for the Workspace browser (scalars show their value)."""
    class_of(value)  # validates
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return _scalar_text(value)
        return "[]" if value.shape == (0, 0) else f"{_dims(value)} {class_of(value)}"
    if isinstance(value, CharArray):
        quoted = _char_quoted(value)
        if quoted is None:
            return f"{_dims(value)} char"
        return quoted if len(quoted) <= limit else quoted[: limit - 4] + "...'"
    if isinstance(value, FunctionHandle):
        text = handle_text(value)
        return text if len(text) <= limit else text[: limit - 3] + "..."
    if isinstance(value, StructValue):
        return "1x1 struct"
    return f"{_dims(value)} cell"
