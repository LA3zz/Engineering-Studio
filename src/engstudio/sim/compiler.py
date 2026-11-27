"""Model compiler (Phase 7, S5): turns a ``Model`` into something the runner can execute.

Steps: flatten subsystems (S11), resolve and check every block's parameters, check the wiring
(port numbers in range, every input connected), order the blocks so that each direct-
feedthrough block comes after the blocks feeding it (topological sort), report algebraic loops
(feedback paths made only of direct-feedthrough blocks) by name, and lay out the continuous
state vector (each block gets a slice). Errors name the block and port so the user can fix
the diagram.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engstudio.core.errors import ValidationError
from engstudio.sim.blocks import BlockImpl, block_type, resolve
from engstudio.sim.model import Model

__all__ = ["CompiledBlock", "CompiledModel", "compile_model", "load_library"]


def load_library() -> None:
    """Import every block module so all block types are registered."""
    import engstudio.sim.blocks_continuous  # noqa: F401
    import engstudio.sim.blocks_discrete  # noqa: F401
    import engstudio.sim.blocks_nonlinear  # noqa: F401
    import engstudio.sim.blocks_sinks  # noqa: F401
    import engstudio.sim.blocks_sources  # noqa: F401
    import engstudio.sim.subsystems  # noqa: F401


@dataclass
class CompiledBlock:
    id: str
    type: str
    name: str
    impl: BlockImpl
    n_in: int
    n_out: int
    inputs: list[tuple[int, int]]  # per input port: (index of source block in order, out port)
    state: slice  # this block's continuous states in the state vector
    feedthrough: bool
    params: dict


@dataclass
class CompiledModel:
    model: Model
    blocks: list[CompiledBlock]  # evaluation order
    n_states: int
    x0: np.ndarray

    def index(self, block_id: str) -> int:
        for i, b in enumerate(self.blocks):
            if b.id == block_id:
                return i
        raise ValidationError(f"no block {block_id!r}")

    def breakpoints(self, t0: float, t1: float) -> list[float]:
        pts: set[float] = set()
        for b in self.blocks:
            pts.update(b.impl.breakpoints(t0, t1))
        return sorted(pts)

    def sample_times(self) -> list[float]:
        return sorted({b.impl.sample_time for b in self.blocks if b.impl.sample_time})


def compile_model(model: Model) -> CompiledModel:
    load_library()
    from engstudio.sim.subsystems import flatten  # S11; local import keeps modules separate

    model = flatten(model)
    if not model.blocks:
        raise ValidationError("the model has no blocks")
    info = {}
    for b in model.blocks:
        bt = block_type(b.type)
        p = resolve(b)
        ft = bt.feedthrough(p) if callable(bt.feedthrough) else bt.feedthrough
        info[b.id] = (bt, p, bt.n_inputs(p), bt.n_outputs(p), bool(ft))
    src_of: dict[tuple[str, int], tuple[str, int]] = {}
    for ln in model.lines:
        n_out = info[ln.src][3]
        n_in = info[ln.dst][2]
        if ln.src_port > n_out:
            raise ValidationError(f"block {ln.src} has {n_out} output(s); a line starts at "
                                  f"output {ln.src_port}")
        if ln.dst_port > n_in:
            raise ValidationError(f"block {ln.dst} has {n_in} input(s); a line ends at "
                                  f"input {ln.dst_port}")
        src_of[(ln.dst, ln.dst_port)] = (ln.src, ln.src_port)
    for b in model.blocks:
        for port in range(1, info[b.id][2] + 1):
            if (b.id, port) not in src_of:
                raise ValidationError(f"input {port} of block {b.id} ({b.type}) is not "
                                      "connected")
    order = _sort(model, info, src_of)
    position = {bid: i for i, bid in enumerate(order)}
    compiled: list[CompiledBlock] = []
    offset = 0
    x0_parts = []
    for bid in order:
        b = model.block(bid)
        bt, p, n_in, n_out, ft = info[bid]
        impl = bt.impl(p)
        n = impl.n_states
        x0_parts.append(np.asarray(impl.initial_state(), dtype=float).reshape(-1))
        inputs = [(position[src_of[(bid, k)][0]], src_of[(bid, k)][1] - 1)
                  for k in range(1, n_in + 1)]
        compiled.append(CompiledBlock(bid, b.type, b.name, impl, n_in, n_out, inputs,
                                      slice(offset, offset + n), ft, p))
        offset += n
    x0 = np.concatenate(x0_parts) if x0_parts else np.zeros(0)
    return CompiledModel(model, compiled, offset, x0)


def _sort(model: Model, info: dict, src_of: dict) -> list[str]:
    """Kahn's algorithm on 'source -> feedthrough destination' edges."""
    ids = [b.id for b in model.blocks]
    deps: dict[str, set[str]] = {i: set() for i in ids}
    for (dst, _port), (src, _sp) in src_of.items():
        if info[dst][4]:  # dst needs src's output at the same instant
            deps[dst].add(src)
    order: list[str] = []
    ready = [i for i in ids if not deps[i]]
    remaining = {i: set(d) for i, d in deps.items() if d}
    while ready:
        node = ready.pop(0)
        order.append(node)
        for other in list(remaining):
            remaining[other].discard(node)
            if not remaining[other]:
                del remaining[other]
                ready.append(other)
    if remaining:
        cycle = _find_cycle(remaining)
        raise ValidationError(
            "algebraic loop: " + " -> ".join(cycle)
            + ". Every feedback loop needs a block with state, e.g. an Integrator, Transfer "
              "Fcn with more poles than zeros, Unit Delay or Memory.")
    return order


def _find_cycle(deps: dict[str, set[str]]) -> list[str]:
    start = sorted(deps)[0]
    path, seen = [start], {start}
    node = start
    while True:
        nxt = sorted(d for d in deps.get(node, ()) if d in deps)[0]
        if nxt in seen:
            return [*path[path.index(nxt):], nxt][::-1]
        path.append(nxt)
        seen.add(nxt)
        node = nxt

