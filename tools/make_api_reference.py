"""Regenerate docs/project/API_REFERENCE.md from the code.

    python tools/make_api_reference.py

For every module of the ``engstudio`` package: its purpose (first paragraph of the module
docstring) and each public function/class (``__all__``, else public top-level names defined
in the module) with its signature and the first line of its docstring.
"""

from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import engstudio  # noqa: E402
from engstudio.version import __version__  # noqa: E402

OUT = ROOT / "docs" / "project" / "API_REFERENCE.md"
SKIP = {"engstudio.__main__", "engstudio.gui.__main__"}


def first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    return " ".join(doc.strip().split("\n\n")[0].split())


def first_line(doc: str | None) -> str:
    return (doc or "").strip().split("\n")[0].strip()


def signature(obj) -> str:
    try:
        sig = str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"
    return sig if len(sig) <= 140 else sig[:137] + "..."


def public_names(mod) -> list[str]:
    names = getattr(mod, "__all__", None)
    if names is not None:
        return list(names)
    return [n for n, v in vars(mod).items()
            if not n.startswith("_") and (inspect.isfunction(v) or inspect.isclass(v))
            and getattr(v, "__module__", None) == mod.__name__]


def describe(mod) -> list[str]:
    lines = [f"### `{mod.__name__}`", ""]
    purpose = first_paragraph(mod.__doc__)
    if purpose:
        lines += [purpose, ""]
    for name in public_names(mod):
        obj = getattr(mod, name, None)
        if obj is None:
            continue
        if inspect.isclass(obj):
            lines.append(f"- class `{name}{signature(obj)}`: {first_line(obj.__doc__)}")
            methods = [m for m, v in vars(obj).items() if not m.startswith("_")
                       and (inspect.isfunction(v) or isinstance(v, (classmethod, staticmethod)))]
            if methods:
                lines.append(f"  - methods: {', '.join(methods)}")
        elif callable(obj):
            spec = getattr(obj, "__tb_function__", None) or getattr(obj, "__wrapped__", None)
            target = obj if spec is None else inspect.unwrap(obj)
            lines.append(f"- `{name}{signature(target)}`: {first_line(target.__doc__)}")
        else:
            lines.append(f"- `{name}` ({type(obj).__name__})")
    lines.append("")
    return lines


def main() -> None:
    mods = []
    for info in pkgutil.walk_packages(engstudio.__path__, "engstudio."):
        if info.name in SKIP or ".docs_pages" in info.name:
            continue
        try:
            mods.append(importlib.import_module(info.name))
        except Exception as exc:  # noqa: BLE001
            print(f"skipped {info.name}: {exc}")
    out = ["# API_REFERENCE",
           f"Generated from the code by `tools/make_api_reference.py` for version {__version__}.",
           "Do not edit by hand: change the docstrings and run the script again.", "",
           "Layer rules and the design behind these modules: ARCHITECTURE.md. Error types live in",
           "`core.errors` (EngStudioError > ValidationError > DimensionError/UnitError;",
           "SingularMatrixError, ConvergenceError, NotSupportedError, PluginError).", ""]
    groups: dict[str, list] = {}
    for m in sorted(mods, key=lambda m: m.__name__):
        parts = m.__name__.split(".")
        groups.setdefault(parts[1] if len(parts) > 1 else "engstudio", []).append(m)
    for group, members in groups.items():
        out += [f"## {group}", ""]
        for m in members:
            out += describe(m)
    OUT.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(out)} lines, {len(mods)} modules)")


if __name__ == "__main__":
    main()
