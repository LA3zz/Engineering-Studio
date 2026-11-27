"""Function help: complete for every command, accurate examples, ``help name``."""

import inspect

import pytest

from engstudio.app.function_help import core_help, split_forms, toolbox_help
from engstudio.app.help_core import CORE_HELP
from engstudio.app.help_toolbox import ARG_DOCS, EXAMPLES
from engstudio.app.kernel.inprocess import _CATEGORIES, InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics, Stdout, ToolboxList
from engstudio.app.toolbox_bindings import load_toolboxes

SPECS = [(display, s) for _n, display, specs in load_toolboxes() for s in specs]


def test_every_core_command_has_help():
    names = {n for _key, (_title, ns) in _CATEGORIES.items() for n in ns}
    missing = sorted(names - set(CORE_HELP))
    assert not missing, f"core commands without help: {missing}"
    for name, (signature, summary) in CORE_HELP.items():
        assert signature and summary, name


def test_every_toolbox_input_is_described_and_has_an_example():
    for _display, spec in SPECS:
        params = inspect.signature(inspect.unwrap(spec.func)).parameters
        docs = ARG_DOCS.get(spec.name, {})
        missing = [p for p in params if not docs.get(p)]
        assert not missing, f"{spec.name}: inputs without a description: {missing}"
        assert set(docs) <= set(params), f"{spec.name}: documents unknown inputs"
        assert spec.name in EXAMPLES, f"{spec.name}: no example"


@pytest.fixture(scope="module")
def kernel():
    k = InProcessKernelClient(threaded=False)
    yield k
    k.shutdown()


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_examples_run(kernel, name):
    events = []
    kernel.subscribe(events.append)
    kernel.execute(EXAMPLES[name], None)
    errors = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
    assert not errors, f"{name}: {errors}"


def test_toolbox_help_text():
    spec = next(s for _d, s in SPECS if s.name == "conduction_resistance")
    h = toolbox_help(spec, "Heat Transfer")
    assert split_forms(h.signature) == ["R = conduction_resistance(geometry, k, a, b)",
                                        "R = conduction_resistance(geometry, k, a, b, L)"]
    assert h.params == ("geometry", "k", "a", "b", "L")
    assert "inner radius [m]; > 0" in h.param_docs[2]
    assert "optional, default 1" in h.param_docs[4]
    assert "Example:" in h.text and "Toolbox: Heat Transfer" in h.text
    sd = toolbox_help(next(s for _d, s in SPECS if s.name == "sdof"))
    assert "Result fields" in sd.text and "zeta" in sd.text


def test_split_forms_and_core_help():
    assert split_forms("plot(y) | plot(x, y)") == ["plot(y)", "plot(x, y)"]
    assert split_forms("x = f('a | b') | f(c)") == ["x = f('a | b')", "f(c)"]
    h = core_help("plot")
    assert h is not None and "plot(x, y)" in h.text and core_help("nonexistent") is None


def test_help_command_and_listing(kernel):
    events = []
    kernel.subscribe(events.append)
    kernel.execute("help pipe_loss\nhelp linspace\nhelp\nhelp nosuchthing\ns = help('sdof');",
                   None)
    out = "".join(e.text for e in events if isinstance(e, Stdout))
    assert "roughness" in out and "linspace(a, b, n)" in out
    assert "help plot" in out and "nosuchthing not found" in out
    assert "m x''" in kernel._interp.workspace["s"].to_str()
    kernel.list_toolboxes()
    listing = [e for e in events if isinstance(e, ToolboxList)][-1]
    fns = {f.name: f for tb in listing.toolboxes for f in tb.functions}
    assert fns["plot"].signature.startswith("plot(y)") and fns["plot"].summary
    assert fns["fin"].params == ("h", "k", "P", "Ac", "L", "dT") and fns["fin"].help
