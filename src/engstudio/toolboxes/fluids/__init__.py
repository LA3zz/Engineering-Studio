"""Fluid Mechanics toolbox (Phase 8):
Reynolds number, friction factors, pipe losses, Bernoulli, pumps, drag, orifices, channels."""

from __future__ import annotations

from engstudio.toolboxes.fluids.functions import FUNCTIONS

NAME = "fluids"
DISPLAY_NAME = "Fluid Mechanics"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
