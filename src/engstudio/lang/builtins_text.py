"""String builtins (B1b): comparison, case, trimming, search, splitting, conversion.

``text_functions()`` returns ``{name: fn}`` (pure: no interpreter needed). Strings are char
row vectors (``CharArray``); where MATLAB accepts a cell array of strings the functions that
list it below do too and return a cell or logical array of the same shape.

Functions: strcmp, strcmpi, strncmp, strncmpi, upper, lower, strtrim, strrep, strcat,
strsplit, strjoin, strfind, contains, startsWith, endsWith, str2double, int2str, blanks,
isspace, isletter, isdigit, mat2str.

Differences from MATLAB: multi-row char arrays are not supported (``NotSupportedError``);
``strcat`` takes char arguments only and drops their trailing white space as MATLAB does;
``str2double`` accepts ``Inf``/``NaN``/``1e3``/``1,200`` and ``1+2i``; there is no regular
expression support yet.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.builtins_core import Builtin, _int, _need, _num2str, _real, _round_half_away
from engstudio.lang.values import CellArray, CharArray, class_of

_WHITESPACE = " \t\n\v\f\r\x00"


def _is_text(v: object) -> bool:
    return isinstance(v, CharArray) and v.shape[0] <= 1


def _str(v: object, name: str) -> str:
    if isinstance(v, CharArray):
        if v.shape[0] > 1:
            raise NotSupportedError(f"{name}: multi-row char arrays are not supported")
        return v.to_str()
    raise ValidationError(f"{name}: argument must be a character vector, not {class_of(v)}.")


def _bool_array(values: list[bool], shape: tuple[int, int]) -> np.ndarray:
    return np.array(values, dtype=bool).reshape(shape, order="F")


def _cell_items(c: CellArray) -> list[object]:
    return list(c.data.ravel(order="F"))


def _make_cell(items: list[object], shape: tuple[int, int]) -> CellArray:
    arr = np.empty(shape, dtype=object)
    for k, item in enumerate(items):
        arr[k % shape[0], k // shape[0]] = item
    return CellArray(arr)


def _on_text(name: str, v: object, fn: Callable[[str], str]) -> object:
    """Apply ``fn`` to a string or to every string of a cell array."""
    if isinstance(v, CellArray):
        return _make_cell([CharArray.from_str(fn(_str(x, name))) for x in _cell_items(v)], v.shape)
    return CharArray.from_str(fn(_str(v, name)))


def _options(name: str, rest: list, allowed: dict[str, object]) -> dict[str, object]:
    """Parse trailing ``'Name', value`` pairs."""
    if len(rest) % 2:
        raise ValidationError(f"{name}: options must be name/value pairs.")
    out = dict(allowed)
    for k in range(0, len(rest), 2):
        key = _str(rest[k], name)
        match = [a for a in allowed if a.lower() == key.lower()]
        if not match:
            raise ValidationError(f"{name}: unknown option {key!r}.")
        out[match[0]] = bool(_real(rest[k + 1], name).any())
    return out


# ------------------------------------------------------------------- comparison
def _make_compare(name: str, fold: bool, counted: bool) -> None:
    def compare(args: list, nargout: int) -> list:
        _need(name, args, 3 if counted else 2)
        limit = _int(args[2], name) if counted else None

        def same(x: object, y: object) -> bool:
            if not (_is_text(x) and _is_text(y)):
                return False
            s, t = x.to_str(), y.to_str()  # type: ignore[attr-defined]
            if limit is not None:
                if len(s) < limit or len(t) < limit:
                    return False
                s, t = s[:limit], t[:limit]
            return s.lower() == t.lower() if fold else s == t

        a, b = args[0], args[1]
        if isinstance(a, CellArray) and isinstance(b, CellArray):
            if a.shape != b.shape:
                raise ValidationError(f"{name}: cell arrays must have the same size.")
            result = [same(x, y) for x, y in zip(_cell_items(a), _cell_items(b), strict=True)]
            return [_bool_array(result, a.shape)]
        if isinstance(a, CellArray) or isinstance(b, CellArray):
            cell, other = (a, b) if isinstance(a, CellArray) else (b, a)
            return [_bool_array([same(x, other) for x in _cell_items(cell)], cell.shape)]
        return [np.array([[same(a, b)]])]

    _TEXT[name] = compare


_TEXT: dict[str, Builtin] = {}
_make_compare("strcmp", False, False)
_make_compare("strcmpi", True, False)
_make_compare("strncmp", False, True)
_make_compare("strncmpi", True, True)


def _make_mapper(name: str, fn: Callable[[str], str]) -> None:
    def mapper(args: list, nargout: int) -> list:
        _need(name, args, 1)
        return [_on_text(name, args[0], fn)]

    _TEXT[name] = mapper


_make_mapper("upper", str.upper)
_make_mapper("lower", str.lower)
_make_mapper("strtrim", lambda s: s.strip(_WHITESPACE))


def _replace_overlapping(text: str, old: str, new: str) -> str:
    """MATLAB ``strrep``: every (also overlapping) occurrence yields ``new``."""
    if not old:
        return text
    out: list[str] = []
    covered_until = 0  # characters before this index belong to an earlier match
    for i, ch in enumerate(text):
        if text.startswith(old, i):
            out.append(new)
            covered_until = i + len(old)
        elif i >= covered_until:
            out.append(ch)
    return "".join(out)


def _strrep(args: list, nargout: int) -> list:
    _need("strrep", args, 3)
    old, new = _str(args[1], "strrep"), _str(args[2], "strrep")
    return [_on_text("strrep", args[0], lambda s: _replace_overlapping(s, old, new))]


def _strcat(args: list, nargout: int) -> list:
    _need("strcat", args, 1, 1000)
    parts = []
    for a in args:
        if isinstance(a, CellArray):
            raise NotSupportedError("strcat: cell array arguments are not supported yet")
        parts.append(_str(a, "strcat").rstrip(_WHITESPACE))
    return [CharArray.from_str("".join(parts))]


# ------------------------------------------------------------- split and search
def _strsplit(args: list, nargout: int) -> list:
    _need("strsplit", args, 1, 4)
    text = _str(args[0], "strsplit")
    rest = list(args[1:])
    delims = [" "]
    if rest and not (isinstance(rest[0], CharArray) and _str(rest[0], "strsplit").lower()
                     == "collapsedelimiters"):
        d = rest.pop(0)
        items = _cell_items(d) if isinstance(d, CellArray) else [d]
        delims = [_str(x, "strsplit").replace("\\t", "\t").replace("\\n", "\n") for x in items]
    collapse = bool(_options("strsplit", rest, {"CollapseDelimiters": True})["CollapseDelimiters"])
    body = "|".join(re.escape(d) for d in sorted(delims, key=len, reverse=True) if d)
    if not body:
        return [_make_cell([CharArray.from_str(text)], (1, 1))]
    pieces = re.split(f"(?:{body})+" if collapse else f"(?:{body})", text)
    return [_make_cell([CharArray.from_str(p) for p in pieces], (1, len(pieces)))]


def _strjoin(args: list, nargout: int) -> list:
    _need("strjoin", args, 1, 2)
    if not isinstance(args[0], CellArray):
        raise ValidationError("strjoin: the first argument must be a cell array of strings.")
    delim = _str(args[1], "strjoin") if len(args) == 2 else " "
    delim = delim.replace("\\n", "\n").replace("\\t", "\t")
    return [CharArray.from_str(delim.join(_str(x, "strjoin") for x in _cell_items(args[0])))]


def _strfind(args: list, nargout: int) -> list:
    _need("strfind", args, 2)
    text, pattern = _str(args[0], "strfind"), _str(args[1], "strfind")
    found = []
    if pattern:
        start = text.find(pattern)
        while start != -1:
            found.append(start + 1.0)
            start = text.find(pattern, start + 1)
    return [np.array([found]) if found else np.zeros((0, 0))]


def _make_contains(name: str, test: Callable[[str, str], bool]) -> None:
    def contains(args: list, nargout: int) -> list:
        _need(name, args, 2, 4)
        ignore = bool(_options(name, list(args[2:]), {"IgnoreCase": False})["IgnoreCase"])
        pats = _cell_items(args[1]) if isinstance(args[1], CellArray) else [args[1]]
        patterns = [_str(p, name) for p in pats]

        def one(s: object) -> bool:
            text = _str(s, name)
            if ignore:
                text = text.lower()
            return any(test(text, p.lower() if ignore else p) for p in patterns)

        if isinstance(args[0], CellArray):
            return [_bool_array([one(s) for s in _cell_items(args[0])], args[0].shape)]
        return [np.array([[one(args[0])]])]

    _TEXT[name] = contains


_make_contains("contains", lambda s, p: p in s)
_make_contains("startsWith", str.startswith)
_make_contains("endsWith", str.endswith)


# ------------------------------------------------------------------ conversion
def _parse_number(text: str) -> complex | float:
    s = text.strip().replace(",", "")
    if not s or "_" in s:
        return float("nan")
    try:
        return float(s)
    except ValueError:
        pass
    try:
        value = complex(re.sub(r"\s*([+-])\s*", r"\1", s).replace("i", "j"))
    except ValueError:
        return float("nan")
    return value if value.imag else value.real


def _str2double(args: list, nargout: int) -> list:
    _need("str2double", args, 1)
    v = args[0]
    if isinstance(v, CellArray):
        values = [_parse_number(_str(x, "str2double")) if _is_text(x) else float("nan")
                  for x in _cell_items(v)]
        shape = v.shape
    elif _is_text(v):
        values, shape = [_parse_number(v.to_str())], (1, 1)  # type: ignore[attr-defined]
    else:
        return [np.array([[float("nan")]])]
    dtype = np.complex128 if any(isinstance(x, complex) for x in values) else np.float64
    return [np.array(values, dtype=dtype).reshape(shape, order="F")]


def _int2str(args: list, nargout: int) -> list:
    _need("int2str", args, 1)
    x = _real(args[0], "int2str")
    return _num2str([_round_half_away(x)], 1)


def _blanks(args: list, nargout: int) -> list:
    _need("blanks", args, 1)
    n = _int(args[0], "blanks")
    if n < 0:
        raise ValidationError("blanks: N must be a non-negative integer.")
    return [CharArray(np.full((1, n), " ", dtype="<U1"))] if n else [CharArray.from_str("")]


def _make_char_test(name: str, test: Callable[[str], bool]) -> None:
    def char_test(args: list, nargout: int) -> list:
        _need(name, args, 1)
        v = args[0]
        if isinstance(v, CharArray):
            flat = [test(c) for c in v.data.ravel(order="F")]
            return [np.array(flat, dtype=bool).reshape(v.shape, order="F")]
        shape = v.shape if hasattr(v, "shape") else (1, 1)
        return [np.zeros(shape, dtype=bool)]

    _TEXT[name] = char_test


_make_char_test("isspace", lambda c: c in " \t\n\v\f\r")
_make_char_test("isletter", str.isalpha)
_make_char_test("isdigit", lambda c: c in "0123456789")


def _mat2str(args: list, nargout: int) -> list:
    _need("mat2str", args, 1, 2)
    precision = _int(args[1], "mat2str") if len(args) == 2 else 15
    v = args[0]
    if isinstance(v, CharArray):
        text = "'" + _str(v, "mat2str").replace("'", "''") + "'"
        return [CharArray.from_str(text)]
    if not isinstance(v, np.ndarray):
        raise ValidationError(f"mat2str: unsupported argument of class {class_of(v)}.")
    if v.size == 0:
        return [CharArray.from_str(f"zeros({v.shape[0]},{v.shape[1]})")]

    def one(x: object) -> str:
        if v.dtype == np.bool_:
            return "true" if x else "false"
        if isinstance(x, complex | np.complexfloating):
            sign = "-" if x.imag < 0 else "+"
            return f"{x.real:.{precision}g}{sign}{abs(x.imag):.{precision}g}i"
        return f"{float(x):.{precision}g}"  # type: ignore[arg-type]

    rows = [" ".join(one(x) for x in row) for row in v]
    text = rows[0] if v.size == 1 else "[" + ";".join(rows) + "]"
    return [CharArray.from_str(text)]


_TEXT.update({
    "strrep": _strrep, "strcat": _strcat, "strsplit": _strsplit, "strjoin": _strjoin,
    "strfind": _strfind, "str2double": _str2double, "int2str": _int2str, "blanks": _blanks,
    "mat2str": _mat2str,
})


def text_functions() -> dict[str, Builtin]:
    """The string builtins (a fresh dictionary)."""
    return dict(_TEXT)
