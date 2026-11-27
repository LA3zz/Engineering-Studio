"""Plugin API: toolbox function decorator with input validation, block metadata, manifests.

``@tb_function`` wraps a pure function so that every call validates the arguments declared
with ``Arg`` (numeric type, shape, finiteness, ranges, integers, choices). Validated numeric
values are passed on normalised: scalars as ``float`` (``int`` if ``integer=True``), arrays as
``float64`` ndarrays. Invalid input raises ``ValidationError``/``DimensionError``; it is never
silently accepted. Mistakes in a plugin definition raise ``PluginError`` at import time.
"""

from __future__ import annotations

import functools
import inspect
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import DimensionError, PluginError, UnitError, ValidationError
from engstudio.core.units import dimension_of

PLUGIN_API_VERSION = 1

CATEGORIES = (
    "mathematics", "mechanical", "aerospace", "control", "electrical", "electronics",
    "signals", "robotics", "thermodynamics", "fluids", "heat_transfer", "materials",
    "structural", "optimization", "data_analysis",
)

FUNC_ATTR = "__engstudio_function__"
BLOCK_ATTR = "__engstudio_block__"

_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")


def _check_unit_tag(owner: str, unit: str | None) -> None:
    if unit is None:
        return
    try:
        dimension_of(unit)
    except UnitError as exc:
        raise PluginError(f"{owner}: invalid unit tag {unit!r}: {exc}") from exc


@dataclass(frozen=True)
class Arg:
    """Declaration and validation rules for one function argument."""

    name: str
    unit: str | None = None            # documentation tag: the argument is expected in this unit
    shape: tuple[int | None, ...] | None = None   # None=any, ()=scalar, (None,)=any vector
    positive: bool = False             # value > 0
    nonnegative: bool = False          # value >= 0
    min: float | None = None           # value >= min
    max: float | None = None           # value <= max
    integer: bool = False
    finite: bool = True                # reject NaN/Inf
    optional: bool = False             # None is accepted and passed through
    choices: tuple[Any, ...] | None = None   # for string/enumerated arguments
    complex_ok: bool = False
    doc: str = ""

    def __post_init__(self) -> None:
        if not _IDENT.match(self.name):
            raise PluginError(f"invalid argument name {self.name!r}")
        _check_unit_tag(f"argument {self.name!r}", self.unit)
        if self.shape is not None:
            object.__setattr__(self, "shape", tuple(self.shape))
        if self.choices is not None:
            object.__setattr__(self, "choices", tuple(self.choices))
        ranged = self.positive or self.nonnegative or self.min is not None or self.max is not None
        if self.positive and self.nonnegative:
            raise PluginError(f"argument {self.name!r}: positive and nonnegative are redundant")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise PluginError(f"argument {self.name!r}: min > max")
        if self.choices is not None and (ranged or self.integer or self.shape is not None):
            raise PluginError(f"argument {self.name!r}: choices cannot combine with numeric rules")
        if self.complex_ok and (ranged or self.integer):
            raise PluginError(f"argument {self.name!r}: complex values cannot have range rules")
        if self.integer and not self.finite:
            raise PluginError(f"argument {self.name!r}: integer arguments must be finite")


@dataclass(frozen=True)
class Ret:
    """Documentation of one return value."""

    name: str
    unit: str | None = None
    doc: str = ""

    def __post_init__(self) -> None:
        _check_unit_tag(f"return {self.name!r}", self.unit)


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    category: str
    args: tuple[Arg, ...]
    returns: tuple[Ret, ...]
    doc: str
    summary: str
    func: Callable[..., Any]
    toolbox: str | None = None


@dataclass(frozen=True)
class BlockSpec:
    """Minimal block metadata; ports and parameters are defined with the simulation engine."""

    name: str
    category: str
    cls: type
    doc: str = ""
    toolbox: str | None = None


def _fmt_shape(shape: tuple[int | None, ...]) -> str:
    if not shape:
        return "scalar"
    inner = ", ".join("*" if s is None else str(s) for s in shape)
    return f"({inner},)" if len(shape) == 1 else f"({inner})"


def _fail_values(label: str, rule: str, arr: np.ndarray, ok: np.ndarray) -> ValidationError:
    if arr.ndim == 0:
        return ValidationError(f"{label} must be {rule}, got {arr.item()!r}")
    bad = ~ok
    first = arr[bad].flat[0].item()
    return ValidationError(
        f"{label} must be {rule}; {int(bad.sum())} of {arr.size} elements violate it "
        f"(first: {first!r})"
    )


def _check_arg(fname: str, a: Arg, value: Any) -> Any:
    label = f"{fname}: argument '{a.name}'"
    if value is None:
        if a.optional:
            return None
        raise ValidationError(f"{label} is required (got None)")
    if a.choices is not None:
        if value not in a.choices:
            raise ValidationError(f"{label} must be one of {list(a.choices)}, got {value!r}")
        return value
    try:
        arr = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be numeric: {exc}") from exc
    allowed = "iuf" + ("c" if a.complex_ok else "")
    if arr.dtype.kind not in allowed:
        raise ValidationError(f"{label} must be numeric, got {type(value).__name__}")
    if a.shape is not None:
        mismatch = arr.ndim != len(a.shape) or any(
            want is not None and want != got
            for want, got in zip(a.shape, arr.shape, strict=True)
        )
        if mismatch:
            raise DimensionError(
                f"{label} must have shape {_fmt_shape(a.shape)}, got "
                f"{_fmt_shape(tuple(arr.shape)) if arr.ndim else 'scalar'}"
            )
    arr = arr.astype(complex if arr.dtype.kind == "c" else float)
    if a.finite and not np.all(np.isfinite(arr)):
        n = int((~np.isfinite(arr)).sum())
        raise ValidationError(f"{label} contains NaN or Inf ({n} element(s))")
    if a.integer:
        ok = arr == np.rint(arr)
        if not np.all(ok):
            raise _fail_values(label, "integer-valued", arr, ok)
    rules: list[tuple[str, np.ndarray]] = []
    if a.positive:
        rules.append(("> 0", arr > 0))
    if a.nonnegative:
        rules.append((">= 0", arr >= 0))
    if a.min is not None:
        rules.append((f">= {a.min}", arr >= a.min))
    if a.max is not None:
        rules.append((f"<= {a.max}", arr <= a.max))
    for rule, ok in rules:
        if not np.all(ok):
            raise _fail_values(label, rule, arr, ok)
    if a.integer:
        return int(arr.item()) if arr.ndim == 0 else np.rint(arr).astype(np.int64)
    return arr.item() if arr.ndim == 0 else arr


def tb_function(
    name: str,
    category: str,
    args: tuple[Arg, ...] | list[Arg] = (),
    returns: tuple[Ret, ...] | list[Ret] = (),
    doc: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare a toolbox function (see module docstring)."""
    if not _IDENT.match(name):
        raise PluginError(f"invalid function name {name!r}")
    if category not in CATEGORIES:
        raise PluginError(f"{name}: unknown category {category!r}; expected one of {CATEGORIES}")
    arg_specs, ret_specs = tuple(args), tuple(returns)
    names = [a.name for a in arg_specs]
    if len(set(names)) != len(names):
        raise PluginError(f"{name}: duplicate Arg names")

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(fn)
        for a in arg_specs:
            param = sig.parameters.get(a.name)
            if param is None:
                raise PluginError(f"{name}: Arg {a.name!r} is not a parameter of {fn.__name__}")
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                raise PluginError(f"{name}: Arg {a.name!r} cannot describe *args/**kwargs")

        @functools.wraps(fn)
        def wrapper(*call_args: Any, **call_kwargs: Any) -> Any:
            try:
                bound = sig.bind(*call_args, **call_kwargs)
            except TypeError as exc:
                raise ValidationError(f"{name}: {exc}") from exc
            bound.apply_defaults()
            for spec_arg in arg_specs:
                bound.arguments[spec_arg.name] = _check_arg(
                    name, spec_arg, bound.arguments[spec_arg.name]
                )
            return fn(*bound.args, **bound.kwargs)

        summary = (inspect.getdoc(fn) or "").strip().split("\n")[0]
        spec = FunctionSpec(name, category, arg_specs, ret_specs, doc, summary, wrapper)
        setattr(wrapper, FUNC_ATTR, spec)
        return wrapper

    return decorator


def sim_block(name: str, category: str, doc: str = "") -> Callable[[type], type]:
    """Declare a simulation block class (metadata only until the simulation engine exists)."""
    if not _IDENT.match(name):
        raise PluginError(f"invalid block name {name!r}")
    if category not in CATEGORIES and category != "simulation":
        raise PluginError(f"{name}: unknown category {category!r}")

    def decorator(cls: type) -> type:
        if not isinstance(cls, type):
            raise PluginError(f"{name}: @sim_block must decorate a class")
        setattr(cls, BLOCK_ATTR, BlockSpec(name, category, cls, doc))
        return cls

    return decorator


@dataclass(frozen=True)
class ToolboxManifest:
    name: str
    display_name: str
    version: str
    api_version: int
    category: str

    def compatibility_diagnostic(self) -> Diagnostic | None:
        """None if loadable; otherwise an error diagnostic (toolbox must be disabled)."""
        if self.api_version != PLUGIN_API_VERSION:
            return Diagnostic(
                "error", "E_PLUGIN_API",
                f"toolbox {self.name!r} needs plugin API {self.api_version}, "
                f"this application provides {PLUGIN_API_VERSION}",
            )
        return None


def parse_manifest(text: str, source: str = "<string>") -> ToolboxManifest:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PluginError(f"{source}: invalid TOML: {exc}") from exc
    table = data.get("toolbox")
    if not isinstance(table, dict):
        raise PluginError(f"{source}: missing [toolbox] table")
    for key in ("name", "version", "api_version", "category"):
        if key not in table:
            raise PluginError(f"{source}: missing required key {key!r} in [toolbox]")
    name, version = table["name"], table["version"]
    api_version, category = table["api_version"], table["category"]
    if not isinstance(name, str) or not _IDENT.match(name):
        raise PluginError(f"{source}: invalid toolbox name {name!r}")
    if not isinstance(version, str) or not _SEMVER.match(version):
        raise PluginError(f"{source}: version must look like 1.2.3, got {version!r}")
    if not isinstance(api_version, int) or isinstance(api_version, bool) or api_version < 1:
        raise PluginError(f"{source}: api_version must be a positive integer")
    if category not in CATEGORIES:
        raise PluginError(f"{source}: unknown category {category!r}")
    display = table.get("display_name", name)
    if not isinstance(display, str) or not display.strip():
        raise PluginError(f"{source}: display_name must be a non-empty string")
    return ToolboxManifest(name, display, version, api_version, category)


def load_manifest(path: str | Path) -> ToolboxManifest:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise PluginError(f"cannot read manifest {p}: {exc}") from exc
    return parse_manifest(text, str(p))
