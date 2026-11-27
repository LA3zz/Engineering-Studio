"""The compiled path for anonymous functions gives exactly the interpreter's results and
falls back to the interpreter for anything it does not handle."""

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics
from engstudio.lang.fastcall import compile_anon
from engstudio.lang.parser import parse

CASES = [
    ("@(t, y) [y(2); -wn^2*y(1)]", "wn = 3;", ["0", "[1; 2]"]),
    ("@(x) x.^2 + 3*x - 2", "", ["[1 2 3]"]),
    ("@(x) sin(x) .* exp(-x/2)", "", ["linspace(0, 1, 5)"]),
    ("@(x) A*x", "A = [1 2; 3 4];", ["[1; 1]"]),
    ("@(x) x'", "", ["[1 2 3]"]),
    ("@(x) -x(2:3)", "", ["[4 5 6]"]),
    ("@(x) x(:)", "", ["[1 2; 3 4]"]),
    ("@(x) x(1:2:5)", "", ["10:20"]),
    ("@(z) abs(z) + 2i", "", ["3 + 4i"]),
    ("@(x) [x, x; 2*x, 0]", "", ["7"]),
    ("@(x) x > 2", "", ["[1 2 3 4]"]),
    ("@(x) deg2rad(x) / pi", "", ["180"]),
    ("@(x, y) hypot(x, y)", "", ["3", "4"]),
]


def run(k, code):
    events = []
    k.subscribe(events.append)
    k.execute(code, None)
    return [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]


@pytest.fixture(scope="module")
def kernel():
    k = InProcessKernelClient(threaded=False)
    yield k
    k.shutdown()


@pytest.mark.parametrize("handle, setup, args", CASES)
def test_compiled_equals_interpreted(kernel, handle, setup, args):
    interp = kernel._interp
    assert not run(kernel, f"{setup} f = {handle};")
    f = interp.workspace["f"]
    values = []
    for a in args:
        assert not run(kernel, f"tmp__ = {a};")
        values.append(interp.workspace["tmp__"])
    assert compile_anon(interp, f.params, frozenset(f.captured), f.body) is not None
    fast = interp.call(f, values, 1)[0]
    saved = interp._fast
    interp._fast = lambda h: None  # force the interpreter path
    try:
        slow = interp.call(f, values, 1)[0]
    finally:
        interp._fast = saved
    assert type(fast) is type(slow) and np.asarray(fast).dtype == np.asarray(slow).dtype
    assert np.array_equal(fast, slow) and np.asarray(fast).shape == np.asarray(slow).shape


@pytest.mark.parametrize("body", [
    "@(x) x(end)", "@(c) c{1}", "@(x) x > 0 && x < 1", "@(x) {x, 1}", "@(x) @(y) x + y",
])
def test_not_compiled_bodies_use_the_interpreter(kernel, body):
    interp = kernel._interp
    f = parse(f"f = {body};").body[0].value
    assert compile_anon(interp, f.params, frozenset(), f.body) is None


def test_errors_and_user_functions_behave_as_before(kernel, tmp_path):
    errors = run(kernel, "f = @(x) x(5); y = f([1 2]);")
    assert errors and "index" in errors[0].lower()
    script = "g = @(x) myfun(x) + 1; v = g(2);\nfunction y = myfun(x)\n  y = 10*x;\nend\n"
    assert not run(kernel, script)
    assert kernel._interp.workspace["v"].item() == 21


def test_ode45_result_unchanged(kernel):
    assert not run(kernel, "wn = 4; f = @(t, y) [y(2); -wn^2*y(1)]; "
                           "[t, y] = ode45(f, linspace(0, 1, 11), [1; 0]);")
    y = kernel._interp.workspace["y"]
    t = kernel._interp.workspace["t"]
    assert np.allclose(y[:, 0], np.cos(4 * t.ravel()), atol=1e-5)
