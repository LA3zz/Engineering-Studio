"""Robotics toolbox (Phase 8):
transforms, DH kinematics, planar arms, inverse kinematics, trajectories."""

from __future__ import annotations

from engstudio.toolboxes.robotics.functions import FUNCTIONS

NAME = "robotics"
DISPLAY_NAME = "Robotics"

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a `core.registry.Registry`."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
