"""Subsystems (Phase 7, S11): a ``Subsystem`` block holds an inner ``Model`` whose ``Inport``
and ``Outport`` blocks (parameter ``Port`` = 1, 2, ...) are the subsystem's ports.

``flatten(model)`` replaces every subsystem (recursively) by its contents before compiling:
inner blocks get the id ``<subsystem>__<block>`` and the name ``<subsystem>/<block>``, and
lines through Inports/Outports are joined. A top-level Inport outputs 0; a top-level Outport is a
sink (its signal is logged as an output).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, BlockType, ParamSpec, register, register_ports_hook
from engstudio.sim.model import Block, Line, Model

__all__ = ["flatten", "subsystem_ports"]


class _Zero(BlockImpl):
    def outputs(self, t, x, u):
        return [np.zeros(1)]


class _Sink(BlockImpl):
    def outputs(self, t, x, u):
        return []


def _check_port(block: str, p: dict) -> None:
    if p["Port"] != int(p["Port"]) or p["Port"] < 1:
        raise ValidationError(f"block {block}: Port must be an integer >= 1")


register(BlockType("Inport", "Ports & Subsystems", "source", (ParamSpec("Port", 1.0),),
                   lambda p: 0, lambda p: 1, False, _Zero,
                   "Subsystem input (outputs 0 at the top level).", _check_port))
register(BlockType("Outport", "Ports & Subsystems", "sink", (ParamSpec("Port", 1.0),),
                   lambda p: 1, lambda p: 0, False, _Sink,
                   "Subsystem output (logged as a model output at the top level).",
                   _check_port))
register(BlockType("Subsystem", "Ports & Subsystems", "algebraic", (),
                   lambda p: 0, lambda p: 0, False, _Sink,
                   "A group of blocks; double-click to edit its contents."))


def _ports_of(inner: Model, kind: str) -> dict[int, Block]:
    found: dict[int, Block] = {}
    for b in inner.blocks:
        if b.type == kind:
            k = int(b.param("Port", 1.0))  # type: ignore[arg-type]
            if k in found:
                raise ValidationError(f"two {kind} blocks with Port {k} ({found[k].id}, {b.id})")
            found[k] = b
    for k in range(1, len(found) + 1):
        if k not in found:
            raise ValidationError(f"{kind} ports must be numbered 1..{len(found)}; {k} is "
                                  "missing")
    return found


def subsystem_ports(block: Block) -> tuple[int, int]:
    """(inputs, outputs) of a Subsystem block from its Inport/Outport blocks."""
    inner = block.subsystem
    if inner is None:
        raise ValidationError(f"block {block.id} is not a subsystem")
    return len(_ports_of(inner, "Inport")), len(_ports_of(inner, "Outport"))


register_ports_hook("Subsystem", subsystem_ports)


def flatten(model: Model) -> Model:
    if not any(b.type == "Subsystem" for b in model.blocks):
        return model
    blocks: list[Block] = []
    lines: list[Line] = []
    sub_in: dict[tuple[str, int], list[tuple[str, int]]] = {}  # (S, port) -> inner consumers
    sub_out: dict[tuple[str, int], tuple[str, int]] = {}  # (S, port) -> inner source
    for b in model.blocks:
        if b.type != "Subsystem":
            blocks.append(b)
            continue
        inner = flatten(b.subsystem)  # type: ignore[arg-type]
        ins, outs = _ports_of(inner, "Inport"), _ports_of(inner, "Outport")
        port_ids = {x.id for x in ins.values()} | {x.id for x in outs.values()}
        rename = {x.id: f"{b.id}__{x.id}" for x in inner.blocks}
        for x in inner.blocks:
            if x.id not in port_ids:
                blocks.append(replace(x, id=rename[x.id], name=f"{b.name}/{x.name}"))
        for k, ib in ins.items():
            sub_in[(b.id, k)] = [(rename[ln.dst], ln.dst_port) for ln in inner.lines
                                 if ln.src == ib.id]
        for k, ob in outs.items():
            src = [(ln.src, ln.src_port) for ln in inner.lines if ln.dst == ob.id]
            if not src:
                raise ValidationError(f"Outport {k} of subsystem {b.id} is not connected")
            s, sp = src[0]
            if s in {x.id for x in ins.values()}:
                raise ValidationError(f"subsystem {b.id}: an Inport wired straight to an "
                                      "Outport is not supported yet")
            sub_out[(b.id, k)] = (rename[s], sp)
        for ln in inner.lines:
            if ln.src not in port_ids and ln.dst not in port_ids:
                lines.append(Line(rename[ln.src], ln.src_port, rename[ln.dst], ln.dst_port))
    for ln in model.lines:
        src, sp = sub_out.get((ln.src, ln.src_port), (ln.src, ln.src_port))
        if (ln.dst, ln.dst_port) in sub_in:
            for dst, dp in sub_in[(ln.dst, ln.dst_port)]:
                lines.append(Line(src, sp, dst, dp))
        else:
            lines.append(Line(src, sp, ln.dst, ln.dst_port))
    return Model(model.name, tuple(blocks), tuple(lines), model.settings)
