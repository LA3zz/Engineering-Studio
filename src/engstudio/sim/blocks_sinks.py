"""Sink blocks (Phase 7, S7): Scope, ToWorkspace, Display, Terminator.

Sinks have no outputs; the runner logs the signals arriving at them (``SimResult.scopes``,
``SimResult.workspace``, ``SimResult.displays``). Differences from Simulink: a Scope's inputs
are plotted together in one axes (one line per input and vector element); ToWorkspace always
saves a structure-free [time, values] pair (``out.<VariableName>`` and ``out.tout``).
"""

from __future__ import annotations

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, BlockType, ParamSpec, register

__all__ = ["SINK_TYPES"]


class _Sink(BlockImpl):
    def outputs(self, t, x, u):
        return []


def _check_name(block: str, p: dict) -> None:
    name = p["VariableName"]
    if not (name and (name[0].isalpha()) and name.replace("_", "a").isalnum()):
        raise ValidationError(f"block {block}: VariableName must be a valid variable name")


def _check_inputs(block: str, p: dict) -> None:
    n = p["NumInputs"]
    if n != int(n) or not 1 <= n <= 20:
        raise ValidationError(f"block {block}: NumInputs must be an integer 1..20")


SINK_TYPES = tuple(register(bt) for bt in (
    BlockType("Scope", "Sinks", "sink",
              (ParamSpec("NumInputs", 1.0), ParamSpec("Title", "", "text")),
              lambda p: int(p["NumInputs"]), lambda p: 0, False, _Sink,
              "Plots its inputs against time after the run.", _check_inputs),
    BlockType("ToWorkspace", "Sinks", "sink",
              (ParamSpec("VariableName", "simout", "text"),),
              lambda p: 1, lambda p: 0, False, _Sink,
              "Saves its input to the workspace (out.VariableName, time in out.tout).",
              _check_name),
    BlockType("Display", "Sinks", "sink", (), lambda p: 1, lambda p: 0, False, _Sink,
              "Shows the final value of its input."),
    BlockType("Terminator", "Sinks", "sink", (), lambda p: 1, lambda p: 0, False, _Sink,
              "Ends an unused signal."),
))
