"""Plugin decorator, argument validation, registry and manifest tests.

Reference example: simply supported beam, point load P at mid-span:
delta = P*L**3 / (48*E*I)   (standard strength-of-materials result).
P=1000 N, L=2 m, E=200e9 Pa, I=8e-6 m^4  ->  8000 / 76.8e6 = 1.0416667e-4 m.
"""

import math
import sys
import types

import numpy as np
import pytest

from engstudio.core import plugin
from engstudio.core.errors import DimensionError, PluginError, ValidationError
from engstudio.core.plugin import Arg, Ret, sim_block, tb_function
from engstudio.core.registry import Registry


@tb_function(
    "beam_deflection_ss", "structural",
    args=[Arg("P", unit="N"), Arg("L", unit="m", positive=True),
          Arg("E", unit="Pa", positive=True), Arg("I", unit="m^4", positive=True)],
    returns=[Ret("delta", unit="m")],
)
def beam_deflection_ss(P, L, E, I):  # noqa: E741
    """Mid-span deflection of a simply supported beam under a central point load."""
    return P * L**3 / (48.0 * E * I)


def test_known_beam_result():
    d = beam_deflection_ss(1000, 2, 200e9, 8e-6)
    assert math.isclose(d, 1.0416666666666667e-4, rel_tol=1e-14)
    assert math.isclose(beam_deflection_ss(P=1000, L=2, E=200e9, I=8e-6), d, rel_tol=0)


def test_spec_metadata():
    spec = getattr(beam_deflection_ss, plugin.FUNC_ATTR)
    assert spec.name == "beam_deflection_ss" and spec.category == "structural"
    assert spec.summary.startswith("Mid-span deflection")
    assert [a.name for a in spec.args] == ["P", "L", "E", "I"]
    assert spec.returns[0].unit == "m"
    assert beam_deflection_ss.__name__ == "beam_deflection_ss"


def test_positive_rule_and_message():
    with pytest.raises(ValidationError, match=r"beam_deflection_ss: argument 'L' must be > 0"):
        beam_deflection_ss(1000, -2, 200e9, 8e-6)
    with pytest.raises(ValidationError, match="got 0.0"):
        beam_deflection_ss(1000, 0, 200e9, 8e-6)


def test_rejects_nan_inf_none_strings():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValidationError, match="NaN or Inf"):
            beam_deflection_ss(bad, 2, 200e9, 8e-6)
    with pytest.raises(ValidationError, match="required"):
        beam_deflection_ss(None, 2, 200e9, 8e-6)
    for bad in ("1000", True, [1, "a"]):
        with pytest.raises(ValidationError, match="numeric"):
            beam_deflection_ss(bad, 2, 200e9, 8e-6)


def test_wrong_call_signature_becomes_validation_error():
    with pytest.raises(ValidationError, match="beam_deflection_ss"):
        beam_deflection_ss(1, 2, 3)
    with pytest.raises(ValidationError):
        beam_deflection_ss(1, 2, 3, 4, 5)


def make(arg, default=None, has_default=False):
    if has_default:
        @tb_function("probe", "mathematics", args=[arg])
        def probe(x=default):
            return x
    else:
        @tb_function("probe", "mathematics", args=[arg])
        def probe(x):
            return x
    return probe


def test_normalisation_scalar_and_array():
    p = make(Arg("x"))
    assert type(p(3)) is float and p(3) == 3.0
    out = p([1, 2, 3])
    assert isinstance(out, np.ndarray) and out.dtype == np.float64
    assert type(p(np.float32(2.5))) is float


def test_shape_rules():
    vec3 = make(Arg("x", shape=(3,)))
    assert vec3([1, 2, 3]).shape == (3,)
    with pytest.raises(DimensionError, match=r"shape \(3,\), got \(2,\)"):
        vec3([1, 2])
    with pytest.raises(DimensionError, match="got scalar"):
        vec3(5)
    mat = make(Arg("x", shape=(None, 2)))
    assert mat([[1, 2], [3, 4], [5, 6]]).shape == (3, 2)
    with pytest.raises(DimensionError, match=r"\(\*, 2\)"):
        mat([[1, 2, 3]])
    scalar_only = make(Arg("x", shape=()))
    assert scalar_only(2) == 2.0
    with pytest.raises(DimensionError):
        scalar_only([2])


def test_range_rules_with_array_messages():
    nn = make(Arg("x", nonnegative=True))
    assert nn(0) == 0.0
    with pytest.raises(ValidationError, match=r"2 of 3 elements.*first: -1.0"):
        nn([-1, 2, -3])
    bounded = make(Arg("x", min=-1, max=1))
    assert bounded(1) == 1.0
    with pytest.raises(ValidationError, match="<= 1"):
        bounded(1.0001)
    with pytest.raises(ValidationError, match=">= -1"):
        bounded(-1.5)


def test_integer_rule():
    n = make(Arg("x", integer=True, min=1))
    assert n(3) == 3 and type(n(3.0)) is int
    arr = n([1, 2, 3])
    assert arr.dtype == np.int64
    with pytest.raises(ValidationError, match="integer-valued"):
        n(2.5)
    with pytest.raises(ValidationError, match=">= 1"):
        n(0)


def test_finite_false_allows_inf_but_not_nan_in_range():
    p = make(Arg("x", finite=False))
    assert p(float("inf")) == float("inf")
    q = make(Arg("x", finite=False, positive=True))
    with pytest.raises(ValidationError):
        q(float("nan"))


def test_optional_and_defaults_validated():
    opt = make(Arg("x", positive=True, optional=True), default=None, has_default=True)
    assert opt() is None and opt(2) == 2.0
    bad_default = make(Arg("x", positive=True), default=-1.0, has_default=True)
    with pytest.raises(ValidationError, match="> 0"):
        bad_default()


def test_choices():
    p = make(Arg("x", choices=("linear", "cubic")))
    assert p("cubic") == "cubic"
    with pytest.raises(ValidationError, match="one of"):
        p("quartic")


def test_complex_ok():
    p = make(Arg("x", complex_ok=True))
    assert p(1 + 2j) == 1 + 2j
    plain = make(Arg("x"))
    with pytest.raises(ValidationError, match="numeric"):
        plain(1 + 2j)


def test_inputs_not_mutated():
    p = make(Arg("x"))
    src = np.array([1.0, 2.0])
    out = p(src)
    out[0] = 99
    assert src[0] == 1.0  # caller's array is never modified


# ---- definition-time errors
def test_bad_definitions_raise_plugin_error():
    with pytest.raises(PluginError, match="unknown category"):
        tb_function("f", "astrology")
    with pytest.raises(PluginError, match="invalid function name"):
        tb_function("1bad", "mathematics")
    with pytest.raises(PluginError, match="duplicate Arg"):
        tb_function("f", "mathematics", args=[Arg("x"), Arg("x")])
    with pytest.raises(PluginError, match="not a parameter"):
        @tb_function("f", "mathematics", args=[Arg("y")])
        def f(x):
            return x
    with pytest.raises(PluginError, match=r"\*args"):
        @tb_function("f", "mathematics", args=[Arg("xs")])
        def g(*xs):
            return xs


def test_bad_arg_definitions():
    with pytest.raises(PluginError, match="invalid unit tag"):
        Arg("x", unit="furlongs")
    with pytest.raises(PluginError, match="min > max"):
        Arg("x", min=2, max=1)
    with pytest.raises(PluginError, match="redundant"):
        Arg("x", positive=True, nonnegative=True)
    with pytest.raises(PluginError, match="choices"):
        Arg("x", choices=("a",), positive=True)
    with pytest.raises(PluginError, match="complex"):
        Arg("x", complex_ok=True, positive=True)
    with pytest.raises(PluginError, match="finite"):
        Arg("x", integer=True, finite=False)
    with pytest.raises(PluginError, match="invalid argument name"):
        Arg("not valid")
    with pytest.raises(PluginError, match="invalid unit tag"):
        Ret("r", unit="nonsense")


def test_all_fifteen_categories():
    assert len(plugin.CATEGORIES) == 15 and len(set(plugin.CATEGORIES)) == 15


# ---- registry
def fresh_module(name="fake_toolbox"):
    mod = types.ModuleType(name)

    @tb_function("double_it", "mathematics", args=[Arg("x")])
    def double_it(x):
        return 2 * x

    @tb_function("half_it", "mathematics", args=[Arg("x")])
    def half_it(x):
        return x / 2

    @sim_block("Gain", "simulation")
    class Gain:
        pass

    for obj in (double_it, half_it, Gain):
        obj.__module__ = name
    mod.double_it, mod.half_it, mod.Gain = double_it, half_it, Gain
    mod.helper = lambda: None
    sys.modules[name] = mod
    return mod


def test_registry_register_module_and_query():
    reg = Registry()
    names = reg.register_module(fresh_module(), toolbox="fake")
    assert names == ("Gain", "double_it", "half_it")
    assert "double_it" in reg and "nope" not in reg
    assert reg.call("double_it", 4) == 8.0
    assert reg.get_function("half_it").toolbox == "fake"
    assert [s.name for s in reg.functions(category="mathematics")] == ["double_it", "half_it"]
    assert reg.functions(category="fluids") == []
    assert [s.name for s in reg.functions(toolbox="fake")] == ["double_it", "half_it"]
    assert [b.name for b in reg.blocks(toolbox="fake")] == ["Gain"]
    assert reg.get_block("Gain").category == "simulation"


def test_registry_skips_imported_objects():
    mod = fresh_module("mod_a")
    other = types.ModuleType("mod_b")
    other.double_it = mod.double_it  # imported, not defined here
    assert Registry().register_module(other) == ()


def test_registry_duplicates():
    reg = Registry()
    mod = fresh_module("mod_c")
    reg.register_module(mod, toolbox="a")
    reg.register_module(mod, toolbox="a")  # same objects: idempotent
    other = fresh_module("mod_d")  # same names, different function objects
    with pytest.raises(PluginError, match="already registered by a"):
        reg.register_module(other, toolbox="b")


def test_registry_errors():
    reg = Registry()
    with pytest.raises(PluginError, match="unknown function"):
        reg.get_function("x")
    with pytest.raises(PluginError, match="unknown block"):
        reg.get_block("x")
    with pytest.raises(PluginError, match="not decorated"):
        reg.add_function(lambda: None)
    with pytest.raises(PluginError, match="not decorated"):
        reg.add_block(int)
    assert reg.find_function("x") is None


def test_registry_remove_toolbox():
    reg = Registry()
    reg.register_module(fresh_module("mod_e"), toolbox="t1")
    assert reg.remove_toolbox("t1") == 3
    assert reg.functions() == [] and reg.blocks() == []
    assert reg.remove_toolbox("t1") == 0


def test_sim_block_requires_class_and_valid_category():
    with pytest.raises(PluginError, match="class"):
        sim_block("B", "simulation")(lambda: None)
    with pytest.raises(PluginError, match="unknown category"):
        sim_block("B", "astrology")


# ---- manifest
GOOD = """
[toolbox]
name = "mechanical"
display_name = "Mechanical Engineering"
version = "0.1.0"
api_version = 1
category = "mechanical"
"""


def test_manifest_valid():
    m = plugin.parse_manifest(GOOD)
    assert (m.name, m.version, m.api_version) == ("mechanical", "0.1.0", 1)
    assert m.category == "mechanical"
    assert m.display_name == "Mechanical Engineering"
    assert m.compatibility_diagnostic() is None


def test_manifest_display_name_defaults_to_name():
    text = GOOD.replace('display_name = "Mechanical Engineering"\n', "")
    assert plugin.parse_manifest(text).display_name == "mechanical"


def test_manifest_errors():
    bad_cases = {
        "invalid TOML": "[toolbox\nname=",
        "missing \\[toolbox\\]": "x = 1",
        "missing required key 'version'": GOOD.replace('version = "0.1.0"\n', ""),
        "version must look like": GOOD.replace('"0.1.0"', '"1.0"'),
        "api_version must be": GOOD.replace("api_version = 1", 'api_version = "1"'),
        "unknown category": GOOD.replace('category = "mechanical"', 'category = "magic"'),
        "invalid toolbox name": GOOD.replace('name = "mechanical"', 'name = "bad name"'),
    }
    for pattern, text in bad_cases.items():
        with pytest.raises(PluginError, match=pattern):
            plugin.parse_manifest(text, "t.toml")


def test_manifest_incompatible_api_gives_error_diagnostic():
    m = plugin.parse_manifest(GOOD.replace("api_version = 1", "api_version = 2"))
    d = m.compatibility_diagnostic()
    assert d is not None and d.severity == "error" and d.code == "E_PLUGIN_API"


def test_load_manifest_from_file(tmp_path):
    path = tmp_path / "toolbox.toml"
    path.write_text(GOOD, encoding="utf-8")
    assert plugin.load_manifest(path).name == "mechanical"
    with pytest.raises(PluginError, match="cannot read manifest"):
        plugin.load_manifest(tmp_path / "missing.toml")


def test_plugin_error_code():
    assert PluginError.code == "E_PLUGIN"
    assert PluginError("x").to_diagnostic().code == "E_PLUGIN"
    assert plugin.PLUGIN_API_VERSION == 1
