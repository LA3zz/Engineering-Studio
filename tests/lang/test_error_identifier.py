"""err.identifier: empty for error('msg'), the given id for error('a:b', ...), non-empty
(internal code) for errors raised by the interpreter itself."""

from engstudio.lang.builtins_core import install_core
from engstudio.lang.interp import Interpreter


def run(code: str):
    interp = Interpreter()
    install_core(interp)
    interp.execute(code, None)
    return interp.workspace


def test_identifier_cases():
    ws = run(
        "try, error('plain message'); catch e, a = e.identifier; m = e.message; end\n"
        "try, error('my:id', 'with id %d', 3); catch e, b = e.identifier; end\n"
        "try, undefined_name_xyz + 1; catch e, c = e.identifier; end\n"
    )
    assert ws["a"].to_str() == "" and ws["m"].to_str() == "plain message"
    assert ws["b"].to_str() == "my:id"
    assert ws["c"].to_str() != ""
