"""Structures and FEA toolbox (Phase 8):
2-D trusses, frames and plane-stress plates."""

from __future__ import annotations

from engstudio.toolboxes.structures.functions import FUNCTIONS

NAME = "structures"
DISPLAY_NAME = "Structures and FEA"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
