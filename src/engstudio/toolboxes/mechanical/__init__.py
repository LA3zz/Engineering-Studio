"""Mechanical Engineering toolbox (Phase 8): mechanics of materials (sections, stress, Mohr's
circle, von Mises, buckling, beams), vibrations (SDOF, forced response, transmissibility,
logarithmic decrement, MDOF modes) and machine elements (springs, gears, shafts, four-bar
linkages). Every function validates its arguments through ``@tb_function``."""

from __future__ import annotations

from engstudio.toolboxes.mechanical.machines import (
    fourbar,
    gear_pair,
    shaft_diameter,
    shaft_power,
    spring_helical,
)
from engstudio.toolboxes.mechanical.solids import (
    beam,
    buckling_euler,
    mohr,
    safety_factor,
    section_circle,
    section_ibeam,
    section_rect,
    section_tube,
    stress_axial,
    stress_bending,
    stress_torsion,
    von_mises,
)
from engstudio.toolboxes.mechanical.vibrations import (
    log_decrement,
    modes,
    sdof,
    sdof_forced,
    sdof_free,
    transmissibility,
)

NAME = "mechanical"
DISPLAY_NAME = "Mechanical Engineering"

FUNCTIONS = (
    section_rect, section_circle, section_tube, section_ibeam,
    stress_axial, stress_bending, stress_torsion, mohr, von_mises, safety_factor,
    buckling_euler, beam,
    sdof, sdof_free, sdof_forced, transmissibility, log_decrement, modes,
    spring_helical, gear_pair, shaft_power, shaft_diameter, fourbar,
)

__all__ = ["DISPLAY_NAME", "FUNCTIONS", "NAME", "register"]


def register(registry) -> None:
    """Add every function of this toolbox to a ``core.registry.Registry``."""
    for fn in FUNCTIONS:
        registry.add_function(fn, toolbox=NAME)
