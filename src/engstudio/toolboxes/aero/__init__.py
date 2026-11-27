"""Aerospace toolbox (Phase 8):
standard atmosphere, airspeed, lift and drag, range, rockets, orbits."""

from __future__ import annotations

from engstudio.toolboxes.aero.functions import FUNCTIONS

NAME = "aero"
DISPLAY_NAME = "Aerospace"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
