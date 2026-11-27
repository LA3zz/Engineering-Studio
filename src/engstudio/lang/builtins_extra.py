"""More builtins (B1b): structs, cells, ``cellfun``/``arrayfun``, sets, operator functions,
random numbers and timing; ``install_extra`` also registers the string functions.

Structs: struct, fieldnames, isfield, rmfield, numfields, getfield, setfield.
Cells: cell, iscellstr, cell2mat, num2cell, deal.
Functional: cellfun, arrayfun (options ``UniformOutput`` and ``ErrorHandler``), feval,
func2str, str2func.
Sets: unique (one output), ismember (``[tf, loc]``), nnz.
Operator functions: plus, minus, times, rdivide, ldivide, power, mtimes, mrdivide, mldivide,
mpower, eq, ne, lt, le, gt, ge, and, or, not, uminus, uplus, transpose, ctranspose, colon.
Random: rand, randn, randi, randperm, rng. Timing: tic, toc.

Differences from MATLAB: struct arrays do not exist, so ``struct('a', {1, 2})`` raises
``NotSupportedError``; random numbers come from NumPy's generator (not MATLAB's streams, so
``rng(1)`` gives reproducible but different numbers); ``tic`` returns the start time as a
double; ``unique`` returns only the sorted values; ``cellfun``/``arrayfun`` require all
uniform outputs to have the same class (as MATLAB does).
"""

from __future__ import annotations

import time

import numpy as np

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import EngStudioError, NotSupportedError, ValidationError
from engstudio.lang import ops
from engstudio.lang.builtins_core import (
    Builtin,
    _arith,
    _dims,
    _int,
    _need,
    _real,
    _scalar,
    _text,
)
from engstudio.lang.builtins_text import text_functions
from engstudio.lang.display import handle_text
from engstudio.lang.interp import Cancelled, Interpreter
from engstudio.lang.parser import parse
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
    empty_double,
    size_of,
)


def _items(c: CellArray) -> list[object]:
    return list(c.data.ravel(order="F"))


def _make_cell(items: list[object], shape: tuple[int, int]) -> CellArray:
    arr = np.empty(shape, dtype=object)
    for k, item in enumerate(items):
        arr[k % shape[0], k // shape[0]] = item
    return CellArray(arr)


def _is_text(v: object) -> bool:
    return isinstance(v, CharArray) and v.shape[0] <= 1


def _strings(v: CellArray, name: str) -> list[str]:
    out = []
    for item in _items(v):
        if not _is_text(item):
            raise ValidationError(f"{name}: expected a cell array of strings.")
        out.append(item.to_str())  # type: ignore[attr-defined]
    return out


def _bool_array(values: list[bool], shape: tuple[int, int]) -> np.ndarray:
    return np.array(values, dtype=bool).reshape(shape, order="F")


# -------------------------------------------------------------- struct and cell
def _struct(args: list, nargout: int) -> list:
    if len(args) % 2:
        raise ValidationError("struct: arguments must be field/value pairs.")
    fields: dict[str, object] = {}
    for k in range(0, len(args), 2):
        value = args[k + 1]
        if isinstance(value, CellArray):
            if value.shape != (1, 1):
                raise NotSupportedError("struct arrays are not supported yet")
            value = value.data[0, 0]
        fields[_text(args[k], "struct")] = value
    return [StructValue(fields)]


def _need_struct(v: object, name: str) -> StructValue:
    if not isinstance(v, StructValue):
        raise ValidationError(f"{name}: the first argument must be a struct.")
    return v


def _fieldnames(args: list, nargout: int) -> list:
    _need("fieldnames", args, 1)
    names = _need_struct(args[0], "fieldnames").names()
    if not names:
        return [CellArray.empty(0, 1)]
    return [_make_cell([CharArray.from_str(n) for n in names], (len(names), 1))]


def _isfield(args: list, nargout: int) -> list:
    _need("isfield", args, 2)
    s, names = args
    if isinstance(names, CellArray):
        flags = [isinstance(s, StructValue) and _is_text(n) and s.has(n.to_str())
                 for n in _items(names)]
        return [_bool_array(flags, names.shape)]
    return [np.array([[isinstance(s, StructValue) and _is_text(names) and s.has(names.to_str())]])]


def _rmfield(args: list, nargout: int) -> list:
    _need("rmfield", args, 2)
    s, name = _need_struct(args[0], "rmfield"), _text(args[1], "rmfield")
    if not s.has(name):
        raise ValidationError(f"rmfield: field '{name}' does not exist.")
    return [StructValue({k: v for k, v in s.items() if k != name})]


def _numfields(args: list, nargout: int) -> list:
    _need("numfields", args, 1)
    return [_scalar(float(len(args[0])) if isinstance(args[0], StructValue) else 0.0)]


def _getfield(args: list, nargout: int) -> list:
    _need("getfield", args, 2)
    return [_need_struct(args[0], "getfield").get(_text(args[1], "getfield"))]


def _setfield(args: list, nargout: int) -> list:
    _need("setfield", args, 3)
    return [_need_struct(args[0], "setfield").with_field(_text(args[1], "setfield"), args[2])]


def _cell(args: list, nargout: int) -> list:
    r, c = _dims("cell", args)
    return [CellArray.empty(r, c)]


def _iscellstr(args: list, nargout: int) -> list:
    _need("iscellstr", args, 1)
    v = args[0]
    return [np.array([[isinstance(v, CellArray) and all(_is_text(x) for x in _items(v))]])]


def _cell2mat(args: list, nargout: int) -> list:
    _need("cell2mat", args, 1)
    c = args[0]
    if not isinstance(c, CellArray):
        raise ValidationError("cell2mat: the argument must be a cell array.")
    if c.data.size == 0:
        return [empty_double()]
    rows = [[c.data[i, j] for j in range(c.shape[1])] for i in range(c.shape[0])]
    return [ops.build_matrix(rows)]


def _views(v: object) -> list[object]:
    """Elements of ``v`` as 1-by-1 values in column-major order (what ``arrayfun`` visits)."""
    if isinstance(v, np.ndarray):
        r, c = v.shape
        return [v[i:i + 1, j:j + 1].copy() for j in range(c) for i in range(r)]
    if isinstance(v, CharArray):
        r, c = v.shape
        return [CharArray(v.data[i:i + 1, j:j + 1].copy()) for j in range(c) for i in range(r)]
    if isinstance(v, CellArray):
        r, c = v.shape
        return [CellArray(v.data[i:i + 1, j:j + 1].copy()) for j in range(c) for i in range(r)]
    return [v]


def _num2cell(args: list, nargout: int) -> list:
    _need("num2cell", args, 1)
    v = args[0]
    if isinstance(v, CellArray):
        raise NotSupportedError("num2cell: cell array input is not supported")
    return [_make_cell(_views(v), size_of(v))]


def _deal(args: list, nargout: int) -> list:
    count = max(nargout, 1)
    if len(args) == 1:
        return [args[0]] * count
    if len(args) != count:
        raise ValidationError("deal: The number of outputs should match the number of inputs.")
    return list(args)


# --------------------------------------------------------------- sets and counts
def _unique(args: list, nargout: int) -> list:
    _need("unique", args, 1)
    if nargout > 1:
        raise ValidationError("unique: only one output is supported yet.")
    v = args[0]
    if isinstance(v, CellArray):
        names = sorted(set(_strings(v, "unique")))
        if not names:
            return [CellArray.empty(0, 1)]
        return [_make_cell([CharArray.from_str(n) for n in names], (len(names), 1))]
    x = _real(v, "unique")
    if x.size == 0:
        return [empty_double()]
    flat = x.ravel(order="F")
    nan = np.isnan(flat)
    values = np.concatenate([np.unique(flat[~nan]), np.full(int(nan.sum()), np.nan)])
    return [values.reshape(1, -1) if x.shape[0] == 1 else values.reshape(-1, 1)]


def _ismember(args: list, nargout: int) -> list:
    _need("ismember", args, 2)
    x, s = args
    if isinstance(s, CellArray):
        pool = _strings(s, "ismember")
        probes = _items(x) if isinstance(x, CellArray) else [x]
        found = [pool.index(p.to_str()) + 1 if _is_text(p) and p.to_str() in pool else 0
                 for p in probes]
        shape = x.shape if isinstance(x, CellArray) else (1, 1)
    else:
        xv, sv = _arith(x, "ismember"), _arith(s, "ismember")
        first: dict[float, int] = {}
        for k, val in enumerate(sv.ravel(order="F").tolist()):
            first.setdefault(val, k + 1)
        found = [first.get(val, 0) for val in xv.ravel(order="F").tolist()]
        shape = xv.shape
    tf = _bool_array([k > 0 for k in found], shape)
    loc = np.array(found, dtype=np.float64).reshape(shape, order="F")
    return [tf, loc][: max(nargout, 1)]


def _nnz(args: list, nargout: int) -> list:
    _need("nnz", args, 1)
    return [_scalar(float(np.count_nonzero(_arith(args[0], "nnz"))))]


# ------------------------------------------------------------- operator functions
_BINARY_OPS = {
    "plus": "+", "minus": "-", "times": ".*", "rdivide": "./", "ldivide": ".\\", "power": ".^",
    "mtimes": "*", "mrdivide": "/", "mldivide": "\\", "mpower": "^", "eq": "==", "ne": "~=",
    "lt": "<", "le": "<=", "gt": ">", "ge": ">=", "and": "&", "or": "|",
}
_FOLDING = {"plus", "times", "and", "or", "mtimes"}


def _operator_functions(interp: Interpreter) -> dict[str, Builtin]:
    host = interp.host
    table: dict[str, Builtin] = {}

    def binary(name: str, symbol: str) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 2, 1000 if name in _FOLDING else 2)
            diags: list[Diagnostic] = []
            result = args[0]
            for other in args[1:]:
                result = ops.binary_op(symbol, result, other, diags)
            for d in diags:
                host.diagnostic(d)
            return [result]

        return call

    def unary(name: str, fn) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 1)
            return [fn(args[0])]

        return call

    def colon(args: list, nargout: int) -> list:
        _need("colon", args, 2, 3)
        step = args[1] if len(args) == 3 else None
        return [ops.colon_range(args[0], step, args[-1])]

    for name, symbol in _BINARY_OPS.items():
        table[name] = binary(name, symbol)
    table.update({
        "not": unary("not", lambda v: ops.unary_op("~", v)),
        "uminus": unary("uminus", lambda v: ops.unary_op("-", v)),
        "uplus": unary("uplus", lambda v: ops.unary_op("+", v)),
        "transpose": unary("transpose", lambda v: ops.transpose(v, False)),
        "ctranspose": unary("ctranspose", lambda v: ops.transpose(v, True)),
        "colon": colon,
    })
    return table


# ----------------------------------------------------------------- cellfun etc.
def _uniform(name: str, values: list, shape: tuple[int, int]) -> object:
    if not values:
        return np.zeros(shape)
    for v in values:
        scalar = (isinstance(v, np.ndarray) and v.size == 1) or (
            isinstance(v, CharArray) and v.data.size == 1)
        if not scalar:
            raise ValidationError(
                f"{name}: Non-scalar in Uniform output; set 'UniformOutput' to false.")
    if len({class_of(v) for v in values}) > 1:
        raise ValidationError(f"{name}: the function returned values of different classes.")
    if isinstance(values[0], CharArray):
        chars = np.array([v.data[0, 0] for v in values], dtype="<U1")
        return CharArray(chars.reshape(shape, order="F"))
    flat = [v[0, 0] for v in values]
    if any(v.dtype.kind == "c" for v in values):
        dtype = np.complex128
    else:
        dtype = np.bool_ if values[0].dtype == np.bool_ else np.float64
    return np.array(flat, dtype=dtype).reshape(shape, order="F")


def _apply(interp: Interpreter, name: str, args: list, nargout: int, over_cells: bool) -> list:
    rest = list(args)
    uniform, handler = True, None
    while len(rest) >= 3 and _is_text(rest[-2]) and rest[-2].to_str().lower() in (
            "uniformoutput", "errorhandler"):
        key, value = rest[-2].to_str().lower(), rest[-1]
        rest = rest[:-2]
        if key == "uniformoutput":
            uniform = bool(_real(value, name).any())
        else:
            handler = value
    if len(rest) < 2:
        raise ValidationError(f"{name}: Not enough input arguments.")
    func = FunctionHandle(name=rest[0].to_str()) if _is_text(rest[0]) else rest[0]
    if not isinstance(func, FunctionHandle):
        raise ValidationError(f"{name}: the first argument must be a function handle or name.")
    inputs = rest[1:]
    if over_cells:
        for a in inputs:
            if not isinstance(a, CellArray):
                raise ValidationError(f"{name}: the arguments after the function must be cells.")
        columns = [_items(a) for a in inputs]
    else:
        columns = [_views(a) for a in inputs]
    shape = size_of(inputs[0])
    if any(size_of(a) != shape for a in inputs[1:]):
        raise ValidationError(f"{name}: All of the input arguments must be of the same size "
                              "and shape.")
    wanted = max(nargout, 1)
    results: list[list] = []
    for k in range(len(columns[0])):
        call_args = [col[k] for col in columns]
        try:
            outs = interp.call(func, call_args, wanted)
        except Cancelled:
            raise
        except EngStudioError as exc:
            if handler is None:
                raise
            ident = getattr(exc.__cause__, "identifier", None) or getattr(exc, "code", "") or ""
            info = StructValue({"message": str(exc), "identifier": ident, "index": float(k + 1)})
            outs = interp.call(handler, [info, *call_args], wanted)
        results.append(outs)
    if nargout == 0 and all(not outs for outs in results):
        return []
    if any(len(outs) < wanted for outs in results):
        raise ValidationError(f"{name}: the function returned fewer outputs than requested.")
    built = []
    for j in range(wanted):
        column = [outs[j] for outs in results]
        built.append(_uniform(name, column, shape) if uniform
                     else (_make_cell(column, shape) if column else CellArray.empty(*shape)))
    return built


# ---------------------------------------------------------------------- bound
def extra_functions(interp: Interpreter) -> dict[str, Builtin]:
    """All B1b builtins (including the string functions) bound to ``interp``."""
    host = interp.host
    table: dict[str, Builtin] = dict(text_functions())
    table.update({
        "struct": _struct, "fieldnames": _fieldnames, "isfield": _isfield, "rmfield": _rmfield,
        "numfields": _numfields, "getfield": _getfield, "setfield": _setfield, "cell": _cell,
        "iscellstr": _iscellstr, "cell2mat": _cell2mat, "num2cell": _num2cell, "deal": _deal,
        "unique": _unique, "ismember": _ismember, "nnz": _nnz,
    })
    table.update(_operator_functions(interp))

    def cellfun(args: list, nargout: int) -> list:
        return _apply(interp, "cellfun", args, nargout, True)

    def arrayfun(args: list, nargout: int) -> list:
        return _apply(interp, "arrayfun", args, nargout, False)

    def feval(args: list, nargout: int) -> list:
        _need("feval", args, 1, 1000)
        return interp.call(_text(args[0], "feval") if _is_text(args[0]) else args[0],
                           args[1:], nargout)

    def func2str(args: list, nargout: int) -> list:
        _need("func2str", args, 1)
        h = args[0]
        if not isinstance(h, FunctionHandle):
            raise ValidationError("func2str: the argument must be a function handle.")
        return [CharArray.from_str(handle_text(h) if h.is_anonymous else str(h.name))]

    def str2func(args: list, nargout: int) -> list:
        _need("str2func", args, 1)
        text = _text(args[0], "str2func").strip()
        if not text.startswith("@"):
            return [FunctionHandle(name=text)]
        program = parse(text)
        if len(program.body) != 1 or not hasattr(program.body[0], "expr"):
            raise ValidationError("str2func: the text must be one function handle expression.")
        return [interp.one(program.body[0].expr, interp.workspace)]  # type: ignore[attr-defined]

    state = {"rng": np.random.default_rng(), "tic": None}

    def sizes(name: str, args: list) -> tuple[int, int]:
        return _dims(name, args)

    def rand(args: list, nargout: int) -> list:
        return [state["rng"].random(sizes("rand", args))]

    def randn(args: list, nargout: int) -> list:
        return [state["rng"].standard_normal(sizes("randn", args))]

    def randi(args: list, nargout: int) -> list:
        _need("randi", args, 1, 1000)
        limits = _real(args[0], "randi").ravel(order="F")
        if limits.size == 1:
            low, high = 1, int(limits[0])
        elif limits.size == 2:
            low, high = int(limits[0]), int(limits[1])
        else:
            raise ValidationError("randi: the limit must be a scalar or [min max].")
        if high < low or (limits.size == 1 and high < 1):
            raise ValidationError("randi: the upper limit must be a positive integer.")
        shape = sizes("randi", args[1:])
        return [state["rng"].integers(low, high + 1, size=shape).astype(np.float64)]

    def randperm(args: list, nargout: int) -> list:
        _need("randperm", args, 1, 2)
        n = _int(args[0], "randperm")
        k = _int(args[1], "randperm") if len(args) == 2 else n
        if n < 0 or not 0 <= k <= n:
            raise ValidationError("randperm: N must be non-negative and K at most N.")
        return [(state["rng"].permutation(n)[:k] + 1.0).reshape(1, -1)]

    def rng(args: list, nargout: int) -> list:
        _need("rng", args, 1)
        if _is_text(args[0]):
            mode = args[0].to_str()
            if mode == "default":
                state["rng"] = np.random.default_rng(0)
            elif mode == "shuffle":
                state["rng"] = np.random.default_rng()
            else:
                raise ValidationError("rng: use a non-negative integer seed, 'default' or "
                                      "'shuffle'.")
            return []
        seed = _int(args[0], "rng")
        if seed < 0:
            raise ValidationError("rng: the seed must be a non-negative integer.")
        state["rng"] = np.random.default_rng(seed)
        return []

    def tic(args: list, nargout: int) -> list:
        now = time.perf_counter()
        state["tic"] = now
        return [_scalar(now)] if nargout >= 1 else []

    def toc(args: list, nargout: int) -> list:
        _need("toc", args, 0, 1)
        start = float(_real(args[0], "toc")[0, 0]) if args else state["tic"]
        if start is None:
            raise ValidationError("toc: Call TIC before TOC.")
        elapsed = time.perf_counter() - start
        if nargout >= 1:
            return [_scalar(elapsed)]
        host.write(f"Elapsed time is {elapsed:.6f} seconds.\n")
        return []

    table.update({
        "cellfun": cellfun, "arrayfun": arrayfun, "feval": feval, "func2str": func2str,
        "str2func": str2func, "rand": rand, "randn": randn, "randi": randi,
        "randperm": randperm, "rng": rng, "tic": tic, "toc": toc,
    })
    return table


def install_extra(interp: Interpreter) -> None:
    """Register the B1b builtins (strings, structs, cells, functional, random, timing)."""
    interp.functions.update(extra_functions(interp))
