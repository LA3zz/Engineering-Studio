"""Make toolbox functions callable from scripts (Phase 8).

``toolbox_builtins()`` loads the built-in toolboxes and wraps every ``@tb_function`` as an
interpreter builtin ``fn(args, nargout) -> list``:

- arguments are matched by position; numbers become floats, vectors 1-D arrays, matrices 2-D
  arrays and character vectors text, following each ``Arg``'s declared shape;
- a dataclass result becomes a struct (its fields converted the same way), a tuple becomes
  several outputs (``[x, v] = sdof_free(...)``), 1-D arrays become row vectors.

Lives in ``app`` because the layer rules keep ``lang`` and ``toolboxes`` apart.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
from collections.abc import Callable

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.core.plugin import FUNC_ATTR, FunctionSpec
from engstudio.lang.values import CharArray, StructValue
from engstudio.toolboxes import BUILTIN

__all__ = ["load_toolboxes", "to_value", "toolbox_builtins"]

Builtin = Callable[[list, int], list]


def load_toolboxes() -> list[tuple[str, str, tuple[FunctionSpec, ...]]]:
    """[(name, display name, function specs)] for every built-in toolbox."""
    out = []
    for name in BUILTIN:
        module = importlib.import_module(f"engstudio.toolboxes.{name}")
        specs = tuple(getattr(fn, FUNC_ATTR) for fn in module.FUNCTIONS)
        out.append((module.NAME, module.DISPLAY_NAME, specs))
    return out


def _arg_in(spec_arg, value: object, fname: str) -> object:
    if isinstance(value, CharArray):
        return value.to_str()
    if not isinstance(value, np.ndarray):
        raise ValidationError(f"{fname}: argument '{spec_arg.name}' must be numeric or text.")
    arr = value.astype(float) if value.dtype == np.bool_ else value
    if arr.size == 0:  # [] means 'not given' (optional argument / unknown)
        return None
    shape = spec_arg.shape
    if shape == (None,) or (shape is not None and len(shape) == 1):
        return arr.reshape(-1, order="F")
    if shape is not None and len(shape) == 2:
        return arr
    if arr.size == 1:
        return arr.reshape(-1)[0].item()
    return arr.reshape(-1, order="F") if 1 in arr.shape else arr


def to_value(x: object) -> object:
    """Python result -> interpreter value."""
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return StructValue({f.name: to_value(getattr(x, f.name)) for f in dataclasses.fields(x)})
    if isinstance(x, str):
        return CharArray.from_str(x)
    if isinstance(x, bool | np.bool_):
        return np.array([[bool(x)]])
    if isinstance(x, int | float | np.integer | np.floating):
        return np.array([[float(x)]])
    if isinstance(x, complex | np.complexfloating):
        return np.array([[complex(x)]])
    if isinstance(x, np.ndarray):
        if x.ndim == 0:
            return to_value(x.item())
        if x.ndim == 1:
            return np.array(x, dtype=complex if x.dtype.kind == "c" else float).reshape(1, -1)
        return np.array(x, dtype=complex if x.dtype.kind == "c" else float)
    if isinstance(x, dict):
        return StructValue({str(k): to_value(v) for k, v in x.items()})
    raise ValidationError(f"cannot return a {type(x).__name__} to a script")


def _wrap(spec: FunctionSpec) -> Builtin:
    params = list(inspect.signature(spec.func).parameters)
    by_name = {a.name: a for a in spec.args}

    def run(args: list, nargout: int) -> list:
        if len(args) > len(params):
            raise ValidationError(f"{spec.name}: Too many input arguments "
                                  f"(at most {len(params)}: {', '.join(params)}).")
        values = []
        for pname, value in zip(params, args, strict=False):
            a = by_name.get(pname)
            values.append(_arg_in(a, value, spec.name) if a is not None else value)
        try:
            result = spec.func(*values)
        except TypeError as exc:  # missing required arguments
            raise ValidationError(f"{spec.name}: {exc}. Arguments: {', '.join(params)}.") \
                from None
        if isinstance(result, tuple) and not dataclasses.is_dataclass(result):
            return [to_value(r) for r in result][:max(1, nargout)]
        return [to_value(result)]

    run.__doc__ = spec.summary
    return run


def toolbox_builtins() -> tuple[dict[str, Builtin], dict[str, tuple[str, tuple[str, ...]]]]:
    """(builtins by name, toolbox categories {key: (display name, function names)})."""
    builtins: dict[str, Builtin] = {}
    categories: dict[str, tuple[str, tuple[str, ...]]] = {}
    for name, display, specs in load_toolboxes():
        for spec in specs:
            builtins[spec.name] = _wrap(spec)
        categories[f"tb_{name}"] = (display, tuple(s.name for s in specs))
    return builtins, categories


def toolbox_help_table() -> dict[str, object]:
    """``FunctionHelp`` for every toolbox function, by name."""
    from engstudio.app.function_help import toolbox_help

    return {spec.name: toolbox_help(spec, display)
            for _name, display, specs in load_toolboxes() for spec in specs}
