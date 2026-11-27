"""``.esmodel`` files (Phase 7, S1): JSON with a ``schema_version``; older versions are
migrated on load (``_MIGRATIONS``). Writes are atomic. Pure data, no numerics, no Qt."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from engstudio.core.errors import EngStudioError, ValidationError
from engstudio.sim.model import Block, Line, Model, SolverSettings

__all__ = ["SCHEMA_VERSION", "dumps", "from_dict", "load", "loads", "save", "to_dict"]

SCHEMA_VERSION = 1
FORMAT = "engstudio-model"
_MIGRATIONS: dict[int, object] = {}  # version -> function(dict) -> dict of version + 1


def _num(v: float) -> object:
    return v if math.isfinite(v) else ("inf" if v > 0 else "-inf")


def _unnum(v: object) -> object:
    return {"inf": math.inf, "-inf": -math.inf}.get(v, v) if isinstance(v, str) else v


def _param_out(v: object) -> object:
    if isinstance(v, tuple):
        return [_param_out(x) for x in v]
    if isinstance(v, float) and not math.isfinite(v):
        return {"special": "inf" if v > 0 else "-inf"}
    return v


def _param_in(v: object) -> object:
    if isinstance(v, list):
        return [_param_in(x) for x in v]
    if isinstance(v, dict) and set(v) == {"special"}:
        return math.inf if v["special"] == "inf" else -math.inf
    return v


def _block_out(b: Block) -> dict:
    d = {"id": b.id, "type": b.type, "name": b.name,
         "params": {k: _param_out(v) for k, v in b.params},
         "position": list(b.position), "size": list(b.size)}
    if b.subsystem is not None:
        d["subsystem"] = to_dict(b.subsystem)
    return d


def to_dict(model: Model) -> dict:
    s = model.settings
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "name": model.name,
        "settings": {"start_time": s.start_time, "stop_time": s.stop_time, "solver": s.solver,
                     "rel_tol": s.rel_tol, "abs_tol": s.abs_tol, "max_step": _num(s.max_step),
                     "fixed_step": s.fixed_step},
        "blocks": [_block_out(b) for b in model.blocks],
        "lines": [{"src": ln.src, "src_port": ln.src_port, "dst": ln.dst,
                   "dst_port": ln.dst_port, "points": [list(p) for p in ln.points]}
                  for ln in model.lines],
    }


def from_dict(data: dict) -> Model:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValidationError("not an Engineering Studio model file")
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise ValidationError(f"invalid schema_version {version!r}")
    if version > SCHEMA_VERSION:
        raise ValidationError(f"this model was saved by a newer version (schema {version}); "
                              "update Engineering Studio to open it")
    while version < SCHEMA_VERSION:
        data = _MIGRATIONS[version](data)  # type: ignore[operator]
        version += 1
    try:
        s = data.get("settings", {})
        settings = SolverSettings(**{k: _unnum(v) for k, v in s.items()})
        blocks = tuple(Block(id=b["id"], type=b["type"], name=b.get("name", ""),
                             params={k: _param_in(v) for k, v in b.get("params", {}).items()},
                             position=tuple(b.get("position", (0, 0))),
                             size=tuple(b.get("size", (60, 40))),
                             subsystem=from_dict(b["subsystem"]) if "subsystem" in b else None)
                       for b in data.get("blocks", []))
        lines = tuple(Line(ln["src"], int(ln["src_port"]), ln["dst"], int(ln["dst_port"]),
                           tuple(tuple(p) for p in ln.get("points", [])))
                      for ln in data.get("lines", []))
    except (KeyError, TypeError) as exc:
        raise ValidationError(f"model file is damaged: {exc}") from None
    return Model(name=str(data.get("name", "untitled")), blocks=blocks, lines=lines,
                 settings=settings)


def dumps(model: Model) -> str:
    return json.dumps(to_dict(model), indent=2)


def loads(text: str) -> Model:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"model file is not valid JSON ({exc})") from None
    return from_dict(data)


def save(model: Model, path: Path | str) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".esmodel":
        target = target.with_suffix(".esmodel")
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(dumps(model), encoding="utf-8")
        os.replace(tmp, target)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise EngStudioError(f"cannot save {target}: {exc}") from None
    return target


def load(path: Path | str) -> Model:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise EngStudioError(f"cannot open {path}: {exc}") from None
    return loads(text)
