"""Simulation commands for scripts (Phase 7, S12): ``sim`` and ``open_system``.

- ``out = sim('model.esmodel')`` runs a model file and returns a struct: ``tout`` (column),
  one field per To Workspace block (``out.<VariableName>``, one column per signal element) and
  ``yout`` (top-level Outports side by side). Name-value pairs override the model's settings:
  'StartTime', 'StopTime', 'Solver', 'RelTol', 'AbsTol', 'MaxStep', 'FixedStep'.
- ``sim(...)`` without an output stores ``out`` in the workspace (as Simulink does) and draws
  every Scope in its own figure.
- ``open_system('model.esmodel')`` asks the desktop to open the model in the editor.

Relative file names are looked up in the working folder, then next to the running script.
Stop cancels a running simulation. Lives in ``app`` because the layer rules keep ``lang`` and
``sim`` apart.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.lang.builtins_core import Builtin
from engstudio.lang.figstate import FigureManager
from engstudio.lang.interp import Cancelled, Interpreter
from engstudio.lang.values import CharArray, StructValue
from engstudio.plotting.model import SeriesSpec
from engstudio.sim import serialization
from engstudio.sim.runner import SimResult, SimulationCancelled, run

__all__ = ["sim_functions"]

_OPTIONS = {"starttime": "start_time", "stoptime": "stop_time", "solver": "solver",
            "reltol": "rel_tol", "abstol": "abs_tol", "maxstep": "max_step",
            "fixedstep": "fixed_step"}


def _text(v: object, what: str) -> str:
    if isinstance(v, CharArray) and v.data.shape[0] <= 1:
        return v.to_str()
    raise ValidationError(f"{what} must be text")


def _model_path(v: object, who: str, script_dir: Callable[[], Path | None] | None = None
                ) -> Path:
    """The model file: as given (working folder), else next to the running script."""
    path = Path(_text(v, f"{who}: the model file name"))
    if not path.suffix:
        path = path.with_suffix(".esmodel")
    if path.exists():
        return path
    base = script_dir() if script_dir is not None else None
    if base is not None and not path.is_absolute() and (base / path).exists():
        return base / path
    raise ValidationError(f"{who}: model file {path} not found")


def result_struct(res: SimResult) -> StructValue:
    fields: dict[str, object] = {"tout": res.tout.reshape(-1, 1).copy()}
    for name, values in res.workspace.items():
        fields[name] = values.copy()
    if res.outports:
        fields["yout"] = np.hstack([res.outports[k] for k in sorted(res.outports)])
    return StructValue(fields)


def sim_functions(interp: Interpreter, manager: FigureManager,
                  open_model: Callable[[str], None],
                  script_dir: Callable[[], Path | None] | None = None) -> dict[str, Builtin]:
    def stop_requested() -> bool:
        try:
            interp.check_cancel()
        except Cancelled:
            return True
        return False

    def sim(args: list, nargout: int) -> list:
        if not args:
            raise ValidationError("sim: use sim('model.esmodel').")
        model = serialization.load(_model_path(args[0], "sim", script_dir))
        rest = list(args[1:])
        if len(rest) % 2:
            raise ValidationError("sim: options must be name-value pairs.")
        changes: dict[str, object] = {}
        for key, value in zip(rest[::2], rest[1::2], strict=True):
            name = _text(key, "sim: option name").lower()
            if name not in _OPTIONS:
                raise ValidationError(f"sim: unknown option {_text(key, '')!r}; use "
                                      + ", ".join(k.title() for k in _OPTIONS) + ".")
            if name == "solver":
                changes["solver"] = _text(value, "sim: Solver")
            else:
                changes[_OPTIONS[name]] = float(np.asarray(value, dtype=float).reshape(-1)[0])
        if changes:
            model = model.with_settings(**changes)
        try:
            res = run(model, should_stop=stop_requested)
        except SimulationCancelled:
            raise Cancelled("Simulation stopped by the user.") from None
        out = result_struct(res)
        if nargout:
            return [out]
        interp.workspace["out"] = out
        _plot_scopes(manager, res)
        for block_id, value in res.displays.items():
            interp.host.write(f"{block_id}: {' '.join(f'{v:.6g}' for v in value)}\n")
        return []

    def open_system(args: list, nargout: int) -> list:
        if len(args) != 1:
            raise ValidationError("open_system: use open_system('model.esmodel').")
        open_model(str(_model_path(args[0], "open_system", script_dir).resolve()))
        return []

    return {"sim": sim, "open_system": open_system}


def _plot_scopes(manager: FigureManager, res: SimResult) -> None:
    publisher = manager.publisher
    for scope_id, data in res.scopes.items():
        number = manager.figure(name=data.title or scope_id)
        manager.clf()
        series = []
        for k, sig in enumerate(data.signals):
            for j in range(sig.shape[1]):
                label = f"in{k + 1}" + (f"({j + 1})" if sig.shape[1] > 1 else "")
                series.append(SeriesSpec("line", data.t, sig[:, j], label=label))
        many = len(series) > 1
        manager.add_lines(series, {"title": data.title or scope_id, "xlabel": "Time (s)",
                                   "grid": True, "legend": many})
        if publisher is not None:
            publisher.push(number)  # type: ignore[attr-defined]
