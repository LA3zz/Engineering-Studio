"""Every built-in toolbox loads, binds into the interpreter without colliding with a core
builtin, and is callable from a script."""

import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics
from engstudio.app.toolbox_bindings import toolbox_builtins


@pytest.fixture(scope="module")
def kernel():
    k = InProcessKernelClient(threaded=False)
    yield k
    k.shutdown()


def run(k, code):
    events = []
    unsub = k.subscribe(events.append)
    k.execute(code, None)
    if callable(unsub):
        unsub()
    errors = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
    assert not errors, errors
    return k._interp.workspace


def test_no_toolbox_function_is_hidden_by_a_core_builtin(kernel):
    builtins, _ = toolbox_builtins()
    funcs = kernel._interp.functions
    hidden = [n for n in builtins
              if getattr(funcs.get(n), "__module__", "") != "engstudio.app.toolbox_bindings"]
    assert not hidden, f"toolbox names taken by core builtins: {hidden}"


def test_toolbox_functions_run_from_scripts(kernel):
    ws = run(kernel, "eta = cycle_efficiency('carnot', 800, 300); e = eta.efficiency;"
                     " f = friction_factor(1000); R = conduction_resistance('plane', 0.5, 0.1, 2);"
                     " Req = resistors([100 100], 'parallel'); g = opamp_gain('follower');"
                     " p = ideal_gas([], 1, 1, 300);")
    assert ws["e"].item() == pytest.approx(0.625)
    assert ws["f"].item() == pytest.approx(0.064)
    assert ws["R"].item() == pytest.approx(0.1)
    assert ws["Req"].item() == pytest.approx(50) and ws["g"].item() == 1
    assert ws["p"].item() == pytest.approx(287 * 300)
