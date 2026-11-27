"""Registry of toolbox functions and simulation blocks.

The registry is an explicit object (no global state). Decorated objects carry their own
metadata; the registry only collects them, rejects name clashes and answers queries.
"""

from __future__ import annotations

from dataclasses import replace
from types import ModuleType
from typing import Any

from engstudio.core.errors import PluginError
from engstudio.core.plugin import BLOCK_ATTR, FUNC_ATTR, BlockSpec, FunctionSpec


def _owner(toolbox: str | None) -> str:
    return toolbox or "<unassigned>"


class Registry:
    def __init__(self) -> None:
        self._functions: dict[str, FunctionSpec] = {}
        self._blocks: dict[str, BlockSpec] = {}

    # ---- registration
    def add_function(self, obj: Any, toolbox: str | None = None) -> FunctionSpec:
        spec = getattr(obj, FUNC_ATTR, None)
        if not isinstance(spec, FunctionSpec):
            raise PluginError(f"{obj!r} is not decorated with @tb_function")
        existing = self._functions.get(spec.name)
        if existing is not None:
            if existing.func is spec.func:
                return existing
            raise PluginError(
                f"function {spec.name!r} is already registered by {_owner(existing.toolbox)}"
            )
        if toolbox is not None:
            spec = replace(spec, toolbox=toolbox)
        self._functions[spec.name] = spec
        return spec

    def add_block(self, cls: Any, toolbox: str | None = None) -> BlockSpec:
        spec = getattr(cls, BLOCK_ATTR, None)
        if not isinstance(spec, BlockSpec):
            raise PluginError(f"{cls!r} is not decorated with @sim_block")
        existing = self._blocks.get(spec.name)
        if existing is not None:
            if existing.cls is spec.cls:
                return existing
            raise PluginError(
                f"block {spec.name!r} is already registered by {_owner(existing.toolbox)}"
            )
        if toolbox is not None:
            spec = replace(spec, toolbox=toolbox)
        self._blocks[spec.name] = spec
        return spec

    def register_module(self, module: ModuleType, toolbox: str | None = None) -> tuple[str, ...]:
        """Register every decorated function/block *defined in* ``module``; return the names."""
        names: list[str] = []
        for obj in vars(module).values():
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            if isinstance(getattr(obj, FUNC_ATTR, None), FunctionSpec):
                names.append(self.add_function(obj, toolbox).name)
            elif isinstance(obj, type) and isinstance(getattr(obj, BLOCK_ATTR, None), BlockSpec):
                names.append(self.add_block(obj, toolbox).name)
        return tuple(sorted(names))

    def remove_toolbox(self, toolbox: str) -> int:
        """Remove everything registered under ``toolbox``; return how many items were removed."""
        fkeys = [k for k, v in self._functions.items() if v.toolbox == toolbox]
        bkeys = [k for k, v in self._blocks.items() if v.toolbox == toolbox]
        for k in fkeys:
            del self._functions[k]
        for k in bkeys:
            del self._blocks[k]
        return len(fkeys) + len(bkeys)

    # ---- queries
    def __contains__(self, name: str) -> bool:
        return name in self._functions

    def find_function(self, name: str) -> FunctionSpec | None:
        return self._functions.get(name)

    def get_function(self, name: str) -> FunctionSpec:
        spec = self._functions.get(name)
        if spec is None:
            raise PluginError(f"unknown function {name!r}")
        return spec

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return self.get_function(name).func(*args, **kwargs)

    def functions(
        self, category: str | None = None, toolbox: str | None = None
    ) -> list[FunctionSpec]:
        return sorted(
            (s for s in self._functions.values()
             if (category is None or s.category == category)
             and (toolbox is None or s.toolbox == toolbox)),
            key=lambda s: s.name,
        )

    def get_block(self, name: str) -> BlockSpec:
        spec = self._blocks.get(name)
        if spec is None:
            raise PluginError(f"unknown block {name!r}")
        return spec

    def blocks(self, category: str | None = None, toolbox: str | None = None) -> list[BlockSpec]:
        return sorted(
            (s for s in self._blocks.values()
             if (category is None or s.category == category)
             and (toolbox is None or s.toolbox == toolbox)),
            key=lambda s: s.name,
        )
