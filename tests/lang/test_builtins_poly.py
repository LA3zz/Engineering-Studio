"""Polynomial builtins (B2b-1). Expected values are exact algebra (Vieta, known roots)."""

from __future__ import annotations

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_poly import install_poly
from engstudio.lang.interp import Interpreter


def run(code: str):
    interp = Interpreter()
    install_core(interp)
    install_poly(interp)
    interp.execute(code, None)
    return interp.workspace


def test_poly_of_roots_vector():
    ws = run("p = poly([1 2 3]);")
    np.testing.assert_allclose(ws["p"], [[1, -6, 11, -6]], atol=1e-12)


def test_poly_of_diagonal_matrix():
    ws = run("p = poly([2 0; 0 3]);")
    np.testing.assert_allclose(ws["p"], [[1, -5, 6]], atol=1e-12)


def test_poly_nonsymmetric_matrix_with_complex_eigenvalues():
    ws = run("p = poly([0 -1; 1 0]);")  # lambda^2 + 1
    np.testing.assert_allclose(ws["p"], [[1, 0, 1]], atol=1e-12)
    assert ws["p"].dtype.kind == "f"


def test_poly_characteristic_polynomial_trace_and_det():
    ws = run("A = [4 1 0; 2 3 1; 0 1 5]; p = poly(A); t = trace(A); d = det(A);")
    p = ws["p"].ravel()
    assert p[1] == pytest.approx(-ws["t"][0, 0])  # -trace
    assert p[3] == pytest.approx(-ws["d"][0, 0])  # (-1)^3 det


def test_poly_rejects_non_square_matrix():
    with pytest.raises(EngStudioError):
        run("p = poly([1 2 3; 4 5 6]);")


def test_roots_real():
    ws = run("r = roots([1 -3 2]);")
    np.testing.assert_allclose(ws["r"], [[1], [2]], atol=1e-12)


def test_roots_complex_pair():
    ws = run("r = roots([1 0 1]);")
    got = sorted(ws["r"].ravel(), key=lambda z: z.imag)
    np.testing.assert_allclose(got, [-1j, 1j], atol=1e-12)


def test_roots_constant_and_zero_are_empty():
    ws = run("a = roots(5); b = roots([0 0]);")
    assert ws["a"].size == 0 and ws["b"].size == 0


def test_roots_trailing_zero_gives_zero_root():
    ws = run("r = roots([1 -1 0]);")
    np.testing.assert_allclose(ws["r"], [[0], [1]], atol=1e-12)


def test_polyval_scalar_and_vector():
    ws = run("a = polyval([1 2 3], 2); b = polyval([1 0 -1], [1 2 3]);")
    assert ws["a"][0, 0] == 11.0
    np.testing.assert_allclose(ws["b"], [[0, 3, 8]])


def test_polyfit_recovers_exact_quadratic():
    ws = run("x = 0:4; y = 2*x.^2 - 3*x + 1; p = polyfit(x, y, 2);")
    np.testing.assert_allclose(ws["p"], [[2, -3, 1]], atol=1e-9)


def test_polyfit_line_through_noisy_symmetric_data():
    # y = 1, 3, 3, 5 at x = 0..3: least squares line is y = 1.2 x + 1.2 (normal equations)
    ws = run("p = polyfit([0 1 2 3], [1 3 3 5], 1);")
    np.testing.assert_allclose(ws["p"], [[1.2, 1.2]], atol=1e-12)


def test_polyfit_too_few_points_is_an_error():
    with pytest.raises(EngStudioError):
        run("p = polyfit([1 2], [1 2], 3);")


def test_polyfit_second_output_not_supported():
    with pytest.raises(EngStudioError):
        run("[p, s] = polyfit([1 2 3], [1 2 3], 1);")
