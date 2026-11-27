"""Materials and Lab Data toolbox (Phase 8):
material properties, tensile-test analysis, fatigue, composites."""

from __future__ import annotations

from engstudio.toolboxes.materials.functions import FUNCTIONS

NAME = "materials"
DISPLAY_NAME = "Materials and Lab Data"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
