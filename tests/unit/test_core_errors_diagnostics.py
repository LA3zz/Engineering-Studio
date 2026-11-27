from dataclasses import FrozenInstanceError

import pytest

from engstudio.core import diagnostics as dg
from engstudio.core import errors as er


def test_hierarchy():
    assert issubclass(er.DimensionError, er.ValidationError)
    assert issubclass(er.UnitError, er.ValidationError)
    for cls in (er.ValidationError, er.SingularMatrixError, er.ConvergenceError,
                er.NotSupportedError):
        assert issubclass(cls, er.EngStudioError)


def test_codes_unique():
    classes = [er.EngStudioError, er.ValidationError, er.DimensionError, er.UnitError,
               er.SingularMatrixError, er.ConvergenceError, er.NotSupportedError]
    codes = [c.code for c in classes]
    assert len(set(codes)) == len(codes)


def test_singular_matrix_error_rcond():
    e = er.SingularMatrixError(rcond=1e-18)
    assert e.rcond == 1e-18
    assert "1.000e-18" in str(e)
    assert er.SingularMatrixError().rcond is None


def test_convergence_error_fields():
    e = er.ConvergenceError("no convergence", iterations=50, last_estimate=1.5)
    assert (e.iterations, e.last_estimate) == (50, 1.5)


def test_to_diagnostic():
    loc = dg.SourceLoc("a.m", 3, 7)
    d = er.UnitError("bad unit").to_diagnostic(loc)
    assert (d.severity, d.code, d.message, d.location) == ("error", "E_UNIT", "bad unit", loc)


def test_invalid_severity_rejected():
    with pytest.raises(ValueError):
        dg.Diagnostic("fatal", "X", "m")


def test_empty_code_rejected():
    with pytest.raises(ValueError):
        dg.Diagnostic("info", "", "m")


def test_diagnostic_is_frozen():
    d = dg.info("I1", "hello")
    with pytest.raises(FrozenInstanceError):
        d.message = "changed"  # type: ignore[misc]


def test_str_formats():
    assert str(dg.warning("W1", "careful")) == "warning [W1] careful"
    d = dg.error("E1", "boom", dg.SourceLoc("x.m", 2, 5))
    assert str(d) == "x.m:2:5: error [E1] boom"
    assert str(dg.SourceLoc()) == "<input>"
    assert str(dg.SourceLoc("f.m", 4)) == "f.m:4"