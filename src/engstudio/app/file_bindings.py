"""Reading and writing lab data files (Phase 8): CSV, TXT/DAT and Excel.

- ``A = readmatrix(file)``: the numbers of a CSV/TXT/DAT/XLSX file as a matrix. Leading text
  rows (headers) are skipped; other non-numeric cells become NaN. Options: 'Sheet' (name or
  number, Excel) and 'Delimiter'.
- ``T = readtable(file)``: one struct field per column, named from the header row (made into
  valid names); numeric columns become column vectors, text columns cell columns.
  ``T.Properties`` is not provided: use ``fieldnames(T)``.
- ``writematrix(A, file)``, ``writetable(T, file)`` (a struct of equal-length columns).
- ``csvread(file, r, c)`` / ``csvwrite(file, A)`` and ``xlsread(file, sheet)`` /
  ``xlswrite(file, A)`` for older scripts (``r, c`` are zero-based offsets as in MATLAB).

Relative names are read from the working folder, then next to the running script; files are
written to the working folder.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.lang.builtins_core import Builtin
from engstudio.lang.values import CellArray, CharArray, StructValue

__all__ = ["file_functions"]

_EXCEL = {".xlsx", ".xlsm", ".xls"}
_TEXT = {".csv", ".txt", ".dat", ".tsv", ""}


def _text(v: object, what: str) -> str:
    if isinstance(v, CharArray) and v.data.shape[0] <= 1:
        return v.to_str()
    raise ValidationError(f"{what} must be text")


def _options(who: str, rest: list, allowed: tuple[str, ...]) -> dict[str, object]:
    if len(rest) % 2:
        raise ValidationError(f"{who}: options must be name-value pairs")
    out: dict[str, object] = {}
    for key, value in zip(rest[::2], rest[1::2], strict=True):
        name = _text(key, f"{who}: option name").lower()
        if name not in allowed:
            raise ValidationError(f"{who}: unknown option {name!r}; use "
                                  + ", ".join(a.title() for a in allowed))
        out[name] = value.to_str() if isinstance(value, CharArray) else value
    return out


def _sheet(value: object | None) -> str | int:
    if value is None:
        return 0
    if isinstance(value, str):
        return value
    return int(np.asarray(value, dtype=float).reshape(-1)[0]) - 1  # MATLAB sheets start at 1


def _frame(path: Path, header: bool, opts: dict[str, object]):
    import pandas as pd

    ext = path.suffix.lower()
    hdr = 0 if header else None
    if ext in _EXCEL:
        return pd.read_excel(path, header=hdr, sheet_name=_sheet(opts.get("sheet")))
    if ext not in _TEXT:
        raise ValidationError(f"unsupported file type {ext!r}: use CSV, TXT, DAT or XLSX")
    delim = opts.get("delimiter")
    if delim is None:
        delim = "\t" if ext == ".tsv" else None
    return pd.read_csv(path, header=hdr, sep=delim, engine="python", skipinitialspace=True)


def _numeric(frame) -> np.ndarray:
    import pandas as pd

    num = frame.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if num.size == 0:
        return np.empty((0, 0))
    start = 0  # skip leading header rows (no number in the row)
    while start < num.shape[0] and np.all(np.isnan(num[start])):
        start += 1
    num = num[start:]
    keep = ~np.all(np.isnan(num), axis=0) if num.size else np.array([], dtype=bool)
    return num[:, keep] if num.size else np.empty((0, 0))


def _field_name(raw: object, k: int, used: set[str]) -> str:
    name = re.sub(r"\W", "_", str(raw).strip())
    if not name or name.lower().startswith("unnamed") or not re.match(r"[A-Za-z]", name):
        name = f"Var{k + 1}" if not name or name.lower().startswith("unnamed") else f"x{name}"
    name = name[:63]
    base, n = name, 1
    while name in used:
        n += 1
        name = f"{base}_{n}"
    used.add(name)
    return name


def file_functions(script_dir: Callable[[], Path | None] | None = None) -> dict[str, Builtin]:
    def find(v: object, who: str) -> Path:
        path = Path(_text(v, f"{who}: the file name"))
        if path.exists():
            return path
        base = script_dir() if script_dir is not None else None
        if base is not None and not path.is_absolute() and (base / path).exists():
            return base / path
        raise ValidationError(f"{who}: file {path} not found")

    def target(v: object, who: str) -> Path:
        path = Path(_text(v, f"{who}: the file name"))
        if not path.suffix:
            path = path.with_suffix(".txt")
        if path.suffix.lower() not in _EXCEL | _TEXT:
            raise ValidationError(f"{who}: unsupported file type {path.suffix!r}")
        if path.suffix.lower() == ".xls":
            raise ValidationError(f"{who}: cannot write .xls; use .xlsx")
        return path

    def read_numbers(path: Path, opts: dict[str, object]) -> np.ndarray:
        try:
            return _numeric(_frame(path, False, opts))
        except ValidationError:
            raise
        except Exception as exc:  # pandas/openpyxl parse errors
            raise ValidationError(f"could not read {path.name}: {exc}") from None

    def readmatrix(args: list, nargout: int) -> list:
        if not args:
            raise ValidationError("readmatrix: use readmatrix('data.csv')")
        opts = _options("readmatrix", list(args[1:]), ("sheet", "delimiter"))
        return [read_numbers(find(args[0], "readmatrix"), opts)]

    def readtable(args: list, nargout: int) -> list:
        if not args:
            raise ValidationError("readtable: use readtable('data.csv')")
        opts = _options("readtable", list(args[1:]), ("sheet", "delimiter"))
        path = find(args[0], "readtable")
        import pandas as pd

        try:
            frame = _frame(path, True, opts)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(f"readtable: could not read {path.name}: {exc}") from None
        fields: dict[str, object] = {}
        used: set[str] = set()
        for k, col in enumerate(frame.columns):
            series = frame[col]
            num = pd.to_numeric(series, errors="coerce")
            name = _field_name(col, k, used)
            if num.notna().sum() >= series.notna().sum():  # all present values numeric
                fields[name] = num.to_numpy(dtype=float).reshape(-1, 1)
            else:
                cells = np.empty((len(series), 1), dtype=object)
                for i, item in enumerate(series):
                    cells[i, 0] = CharArray.from_str("" if pd.isna(item) else str(item))
                fields[name] = CellArray(cells)
        return [StructValue(fields)]

    def _matrix(v: object, who: str) -> np.ndarray:
        try:
            arr = np.asarray(v, dtype=float)
        except (TypeError, ValueError):
            raise ValidationError(f"{who}: the data must be numeric") from None
        return arr.reshape(1, -1) if arr.ndim < 2 else arr

    def write_frame(frame, path: Path, header: bool, sheet: object | None) -> None:
        try:
            if path.suffix.lower() in _EXCEL:
                name = sheet if isinstance(sheet, str) else "Sheet1"
                frame.to_excel(path, header=header, index=False, sheet_name=name)
            else:
                sep = "\t" if path.suffix.lower() == ".tsv" else ","
                frame.to_csv(path, header=header, index=False, sep=sep)
        except OSError as exc:
            raise ValidationError(f"could not write {path}: {exc}") from None

    def writematrix(args: list, nargout: int) -> list:
        if len(args) < 2:
            raise ValidationError("writematrix: use writematrix(A, 'data.csv')")
        import pandas as pd

        opts = _options("writematrix", list(args[2:]), ("sheet",))
        frame = pd.DataFrame(_matrix(args[0], "writematrix"))
        write_frame(frame, target(args[1], "writematrix"), False, opts.get("sheet"))
        return []

    def writetable(args: list, nargout: int) -> list:
        if len(args) < 2 or not isinstance(args[0], StructValue):
            raise ValidationError("writetable: use writetable(T, 'data.csv') with a struct of "
                                  "equal-length columns")
        import pandas as pd

        opts = _options("writetable", list(args[2:]), ("sheet",))
        cols: dict[str, object] = {}
        for name in args[0].names():
            v = args[0].get(name)
            if isinstance(v, CellArray):
                cols[name] = [x.to_str() if isinstance(x, CharArray) else str(x)
                              for x in v.data.ravel()]
            else:
                cols[name] = _matrix(v, "writetable").ravel()
        lengths = {len(c) for c in cols.values()}  # type: ignore[arg-type]
        if len(lengths) > 1:
            raise ValidationError("writetable: every field must have the same length")
        write_frame(pd.DataFrame(cols), target(args[1], "writetable"), True, opts.get("sheet"))
        return []

    def csvread(args: list, nargout: int) -> list:
        if not args:
            raise ValidationError("csvread: use csvread('data.csv')")
        data = read_numbers(find(args[0], "csvread"), {})
        r = int(np.asarray(args[1]).item()) if len(args) > 1 else 0
        c = int(np.asarray(args[2]).item()) if len(args) > 2 else 0
        return [data[r:, c:]]

    def csvwrite(args: list, nargout: int) -> list:
        if len(args) != 2:
            raise ValidationError("csvwrite: use csvwrite('data.csv', A)")
        return writematrix([args[1], args[0]], 0)

    def xlsread(args: list, nargout: int) -> list:
        if not args:
            raise ValidationError("xlsread: use xlsread('data.xlsx')")
        opts = {"sheet": args[1].to_str() if isinstance(args[1], CharArray) else args[1]} \
            if len(args) > 1 else {}
        return [read_numbers(find(args[0], "xlsread"), opts)]

    def xlswrite(args: list, nargout: int) -> list:
        if len(args) < 2:
            raise ValidationError("xlswrite: use xlswrite('data.xlsx', A)")
        return writematrix([args[1], args[0]], 0)

    return {"readmatrix": readmatrix, "readtable": readtable, "writematrix": writematrix,
            "writetable": writetable, "csvread": csvread, "csvwrite": csvwrite,
            "xlsread": xlsread, "xlswrite": xlswrite}
