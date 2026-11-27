"""Heat Transfer toolbox (Phase 8):
conduction, convection, radiation, fins, heat exchangers, lumped transients."""

from __future__ import annotations

from engstudio.toolboxes.heat.functions import FUNCTIONS

NAME = "heat"
DISPLAY_NAME = "Heat Transfer"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
