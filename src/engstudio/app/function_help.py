"""Help for every function: calling forms, summary, inputs, outputs and an example.

One source for the Toolbox browser details pane, the ``help name`` command, the call tips
shown while typing (``plot(x, `` shows what comes next) and the user manual.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
import typing
from dataclasses import dataclass

from engstudio.app.help_core import CORE_HELP
from engstudio.app.help_toolbox import ARG_DOCS, EXAMPLES

__all__ = ["FunctionHelp", "core_help", "toolbox_help", "split_forms"]


@dataclass(frozen=True)
class FunctionHelp:
    name: str
    signature: str  # calling forms separated by " | "
    summary: str  # one line
    text: str  # full help (plain text)
    params: tuple[str, ...] = ()  # toolbox functions: argument names in order
    param_docs: tuple[str, ...] = ()  # one line per argument (meaning, unit, limits, default)


def split_forms(signature: str) -> list[str]:
    """``"plot(y) | plot(x, y)"`` -> ``["plot(y)", "plot(x, y)"]`` (ignores ``|`` inside
    quotes, e.g. ``'a' | 'b'``)."""
    forms, depth, quote, cur = [], 0, False, ""
    i = 0
    while i < len(signature):
        c = signature[i]
        if c == "'":
            quote = not quote
        elif not quote and c in "([{":
            depth += 1
        elif not quote and c in ")]}":
            depth -= 1
        if (not quote and depth == 0 and signature.startswith(" | ", i)):
            forms.append(cur.strip())
            cur, i = "", i + 3
            continue
        cur += c
        i += 1
    if cur.strip():
        forms.append(cur.strip())
    return forms


# ------------------------------------------------------------------------- core help
def core_help(name: str) -> FunctionHelp | None:
    entry = CORE_HELP.get(name)
    if entry is None:
        return None
    signature, summary = entry
    lines = [*split_forms(signature), "", summary]
    return FunctionHelp(name, signature, summary, "\n".join(lines))


# ---------------------------------------------------------------------- toolbox help
def _fmt_default(v: object) -> str:
    if v is None:
        return "not given"
    if isinstance(v, str):
        return f"'{v}'"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _arg_line(a, default: object, desc: str) -> str:
    head = desc
    parts: list[str] = []
    if a is not None:
        if a.unit:
            head = f"{head} [{a.unit}]".strip()
        rules = []
        if a.choices and not all(str(c) in desc for c in a.choices):
            rules.append("one of " + ", ".join(f"'{c}'" for c in a.choices))
        if a.positive:
            rules.append("> 0")
        if a.nonnegative:
            rules.append(">= 0")
        if a.min is not None and a.max is not None:
            rules.append(f"{a.min:g} to {a.max:g}")
        elif a.min is not None:
            rules.append(f">= {a.min:g}")
        elif a.max is not None:
            rules.append(f"<= {a.max:g}")
        if a.integer:
            rules.append("whole number")
        if a.shape == (None,):
            rules.append("vector")
        elif a.shape is not None and len(a.shape) == 2:
            cols = a.shape[1]
            rules.append("matrix" if cols is None else f"{cols}-column matrix")
        elif a.shape is not None and len(a.shape) == 1:
            rules.append(f"{a.shape[0]} values")
        parts += rules
    if default is not inspect.Parameter.empty:
        parts.append(f"optional, default {_fmt_default(default)}")
    return "; ".join(p for p in [head, *parts] if p)


def _field_docs(cls: type) -> list[tuple[str, str]]:
    comments: dict[str, str] = {}
    try:
        src = inspect.getsource(cls)
    except (OSError, TypeError):
        src = ""
    for m in re.finditer(r"^\s+(\w+):[^#\n]*#\s*(.+)$", src, re.MULTILINE):
        comments[m.group(1)] = m.group(2).strip()
    return [(f.name, comments.get(f.name, "")) for f in dataclasses.fields(cls)]


def _result_class(func) -> type | None:
    try:
        hint = typing.get_type_hints(inspect.unwrap(func)).get("return")
    except Exception:  # unresolvable annotations: no field list
        return None
    return hint if dataclasses.is_dataclass(hint) else None


def toolbox_help(spec, toolbox_title: str = "") -> FunctionHelp:
    func = inspect.unwrap(spec.func)
    sig = inspect.signature(func)
    params = tuple(sig.parameters)
    by_name = {a.name: a for a in spec.args}
    docs = ARG_DOCS.get(spec.name, {})
    required = [p for p in params if sig.parameters[p].default is inspect.Parameter.empty]
    forms = [f"{spec.name}({', '.join(params)})"]
    if len(required) < len(params):
        forms.insert(0, f"{spec.name}({', '.join(required)})")
    outs = [r.name for r in spec.returns]
    if len(outs) > 1:
        forms = [f"[{', '.join(outs)}] = {f}" for f in forms]
    elif outs:
        forms = [f"{outs[0]} = {f}" for f in forms]
    param_docs = tuple(
        _arg_line(by_name.get(p), sig.parameters[p].default, docs.get(p, "")) for p in params)
    doc = " ".join((inspect.getdoc(func) or "").split())
    width = max((len(p) for p in params), default=0)
    lines = [*forms, "", doc, "", "Inputs:"]
    lines += [f"  {p.ljust(width)}  {d}" for p, d in zip(params, param_docs, strict=True)]
    lines += ["", "Outputs:"]
    for r in spec.returns:
        lines.append(f"  {r.name}" + (f"  [{r.unit}]" if r.unit else ""))
    cls = _result_class(spec.func)
    if cls is not None:
        fields = _field_docs(cls)
        fw = max(len(n) for n, _ in fields)
        lines += ["", f"Result fields ({outs[0] if outs else 'result'}.name):"]
        lines += [f"  {n.ljust(fw)}  {c}".rstrip() for n, c in fields]
    if spec.name in EXAMPLES:
        lines += ["", "Example:", f"  {EXAMPLES[spec.name]}"]
    if toolbox_title:
        lines += ["", f"Toolbox: {toolbox_title}"]
    summary = (inspect.getdoc(func) or "").strip().split("\n")[0]
    return FunctionHelp(spec.name, " | ".join(forms), summary, "\n".join(lines), params,
                        param_docs)
