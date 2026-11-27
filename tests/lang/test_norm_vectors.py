"""norm of vectors is the vector p-norm (MATLAB), of matrices the induced/Frobenius norm.
References by hand: v = [3 -4 12]: 1-norm 19, 2-norm 13, Inf-norm 12; A = [1 2; 3 4]: 1-norm
(max column sum) 6, Inf-norm (max row sum) 7, Frobenius sqrt(30)."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.interp import Interpreter


def val(code: str) -> float:
    interp = Interpreter()
    install_core(interp)
    interp.execute("v = [3 -4 12]; c = v'; A = [1 2; 3 4]; r = " + code + ";", None)
    return float(np.asarray(interp.workspace["r"]).reshape(-1)[0])


@pytest.mark.parametrize("code, expected", [
    ("norm(v)", 13.0), ("norm(v, 1)", 19.0), ("norm(v, 2)", 13.0), ("norm(v, Inf)", 12.0),
    ("norm(v, 'inf')", 12.0), ("norm(v, 'fro')", 13.0), ("norm(c, 1)", 19.0),
    ("norm(c, Inf)", 12.0), ("norm(v, 3)", (27 + 64 + 1728) ** (1 / 3)), ("norm(-5)", 5.0),
    ("norm(A, 1)", 6.0), ("norm(A, Inf)", 7.0), ("norm(A, 'fro')", math.sqrt(30)),
    ("norm(A)", float(np.linalg.norm([[1.0, 2], [3, 4]], 2))),
])
def test_norm_values(code, expected):
    assert val(code) == pytest.approx(expected, rel=1e-12)


def test_vector_p_below_one_is_an_error():
    with pytest.raises(EngStudioError):
        val("norm(v, 0.5)")
