"""Thermodynamics toolbox (Phase 8):
ideal gas, processes, cycles, COP, entropy."""

from __future__ import annotations

from engstudio.toolboxes.thermo.functions import FUNCTIONS

NAME = "thermo"
DISPLAY_NAME = "Thermodynamics"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
