"""Save and load workspace variables in MATLAB's ``.mat`` format (``save``, ``load``).

- ``save`` writes every variable to ``matlab.mat`` in the working folder; ``save file`` /
  ``save('file.mat')`` to that file; ``save file x y`` / ``save('file', 'x', 'y')`` only those.
- ``load`` reads ``matlab.mat``; ``load file`` / ``load('file')`` puts its variables in the
  workspace; ``load file x`` only ``x``; ``S = load('file')`` returns them as a struct instead.
- Files are interchangeable with MATLAB (version 5 MAT-files): numbers (also complex), text,
  cell arrays and structs. Integer arrays from MATLAB files load as doubles.

Differences from MATLAB: logical arrays are saved as numbers (they load back as 0/1 doubles);
function handles, symbolic values and control systems cannot be saved (they are skipped with
a warning); struct arrays from MATLAB files load as cell arrays of structs; options such as
``-ascii`` and ``-append`` are not supported. Relative names use the working folder; ``load``
also looks next to the running script.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from engstudio.core.diagnostics import warning
from engstudio.core.errors import ValidationError
from engstudio.lang.builtins_core import Builtin
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CellArray, CharArray, StructValue

__all__ = ["workspace_file_functions"]

DEFAULT = "matlab.mat"


class _Unsupported(Exception):
    pass


def _text(v: object, what: str) -> str:
    if isinstance(v, CharArray) and v.data.shape[0] <= 1:
        return v.to_str()
    raise ValidationError(f"{what} must be text")


def _with_suffix(name: str) -> Path:
    p = Path(name).expanduser()
    return p if p.suffix else p.with_suffix(".mat")


# ------------------------------------------------------------------ value conversion
def _to_mat(v: object) -> object:
    if isinstance(v, np.ndarray):
        if v.dtype == np.bool_:
            return v.astype(np.uint8)
        return v
    if isinstance(v, CharArray):
        rows = ["".join(c or " " for c in row) for row in v.data] if v.data.size else [""]
        return rows[0] if len(rows) == 1 else np.array(rows)
    if isinstance(v, CellArray):
        out = np.empty(v.data.shape, dtype=object)
        for idx, item in np.ndenumerate(v.data):
            out[idx] = _to_mat(item)
        return out
    if isinstance(v, StructValue):
        return {name: _to_mat(v.get(name)) for name in v.names()}
    raise _Unsupported(type(v).__name__)


def _from_mat(v: object) -> object:
    if isinstance(v, str):
        return CharArray.from_str(v)
    if hasattr(v, "_fieldnames"):  # scipy mat_struct
        return StructValue({f: _from_mat(getattr(v, f)) for f in v._fieldnames})
    if not isinstance(v, np.ndarray):
        return np.array([[float(v)]])
    if v.dtype.kind == "U":
        rows = [str(s) for s in v.ravel()]
        if len(rows) == 1:
            return CharArray.from_str(rows[0])
        width = max(len(r) for r in rows)
        return _char_rows(rows, width)
    if v.dtype == object:
        if v.size == 1 and hasattr(v.flat[0], "_fieldnames"):
            return _from_mat(v.flat[0])  # 1x1 struct
        arr = v.reshape(v.shape if v.ndim == 2 else (1, v.size))
        cells = np.empty(arr.shape, dtype=object)
        for idx, item in np.ndenumerate(arr):
            cells[idx] = _from_mat(item)
        return CellArray(cells)
    if v.dtype.kind in "iub":
        v = v.astype(float)
    if v.ndim != 2:
        v = v.reshape((1, v.size)) if v.ndim < 2 else v.reshape(v.shape[0], -1)
    return np.array(v, dtype=complex if v.dtype.kind == "c" else float)


def _char_rows(rows: list[str], width: int) -> CharArray:
    data = np.array([list(r.ljust(width)) for r in rows], dtype="<U1")
    return CharArray(data)


# ---------------------------------------------------------------------------- commands
def workspace_file_functions(interp: Interpreter, write: Callable[[str], None],
                             script_dir: Callable[[], Path | None] | None = None
                             ) -> dict[str, Builtin]:
    def save(args: list, nargout: int) -> list:
        from scipy.io import savemat

        texts = [_text(a, "save: arguments") for a in args]
        options = [t for t in texts if t.startswith("-")]
        if options:
            raise ValidationError(f"save: option {options[0]} is not supported; use "
                                  "save(file) or save(file, 'x', 'y')")
        path = _with_suffix(texts[0] if texts else DEFAULT)
        names = texts[1:] or sorted(interp.workspace.names())
        missing = [n for n in names if n not in interp.workspace]
        if missing:
            raise ValidationError(f"save: variable '{missing[0]}' not found")
        data, skipped = {}, []
        for n in names:
            try:
                data[n] = _to_mat(interp.workspace[n])
            except _Unsupported as kind:
                skipped.append(f"{n} ({kind})")
        if skipped:
            interp.host.diagnostic(warning(
                "save.skipped", "save: these cannot be stored in a .mat file and were skipped: "
                + ", ".join(skipped)))
        try:
            savemat(path, data, do_compression=True, oned_as="row")
        except OSError as exc:
            raise ValidationError(f"save: could not write {path}: {exc}") from None
        return []

    def find(path: Path) -> Path:
        if path.exists():
            return path
        base = script_dir() if script_dir is not None else None
        if base is not None and not path.is_absolute() and (base / path).exists():
            return base / path
        raise ValidationError(f"load: file {path} not found")

    def load(args: list, nargout: int) -> list:
        from scipy.io import loadmat

        texts = [_text(a, "load: arguments") for a in args]
        path = find(_with_suffix(texts[0] if texts else DEFAULT))
        if path.suffix.lower() != ".mat":
            raise ValidationError("load: only .mat files are supported; use readmatrix for "
                                  "text and Excel files")
        try:
            raw = loadmat(path, squeeze_me=False, struct_as_record=False,
                          chars_as_strings=True)
        except Exception as exc:  # scipy raises several types for bad files
            raise ValidationError(f"load: could not read {path.name}: {exc}") from None
        wanted = texts[1:]
        values = {k: v for k, v in raw.items() if not k.startswith("__")}
        missing = [w for w in wanted if w not in values]
        if missing:
            raise ValidationError(f"load: variable '{missing[0]}' not found in {path.name}")
        names = wanted or sorted(values)
        loaded = {n: _from_mat(values[n]) for n in names}
        if nargout:
            return [StructValue(loaded)]
        for n, v in loaded.items():
            interp.workspace[n] = v
        return []

    return {"save": save, "load": load}
