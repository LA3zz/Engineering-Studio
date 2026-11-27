"""Electrical and Electronics toolbox (Phase 8):
circuits, AC power, three-phase, op-amps, filters, diodes, 555 timer."""

from __future__ import annotations

from engstudio.toolboxes.electrical.functions import FUNCTIONS

NAME = "electrical"
DISPLAY_NAME = "Electrical and Electronics"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
