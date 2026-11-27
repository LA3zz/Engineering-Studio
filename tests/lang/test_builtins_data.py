"""B2b-2 builtins. Expected values are closed-form (trapezoid areas, textbook variances, DFT)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_data import install_data
from engstudio.lang.interp import Interpreter


def run(code: str):
    interp = Interpreter()
    install_core(interp)
    install_data(interp)
    interp.execute(code, None)
    return interp.workspace


def test_trapz_vector_and_with_x():
    ws = run("a = trapz([1 2 3]); b = trapz([0 1 2], [0 1 4]);")
    assert ws["a"][0, 0] == 4.0
    assert ws["b"][0, 0] == 3.0


def test_trapz_matrix_is_columnwise():
    ws = run("a = trapz([1 2; 3 4; 5 6]);")
    np.testing.assert_allclose(ws["a"], [[6, 8]])


def test_cumtrapz_keeps_orientation():
    ws = run("a = cumtrapz([1 2 3]); b = cumtrapz([1; 2; 3]);")
    np.testing.assert_allclose(ws["a"], [[0, 1.5, 4]])
    assert ws["b"].shape == (3, 1)


def test_trapz_single_sample_is_an_error():
    with pytest.raises(EngStudioError):
        run("a = trapz(5);")


def test_interp1_linear_and_vector_query():
    ws = run("a = interp1([1 2 3], [10 20 30], 2.5); b = interp1([1 2 3], [10 20 30], [1.5 2.5]);")
    assert ws["a"][0, 0] == pytest.approx(25.0)
    np.testing.assert_allclose(ws["b"], [[15, 25]])


def test_interp1_default_x_is_index():
    ws = run("a = interp1([10 20 30], 2.5);")
    assert ws["a"][0, 0] == pytest.approx(25.0)


def test_interp1_methods():
    ws = run("""a = interp1([1 2 3], [10 20 30], 2.5, 'pchip');
b = interp1([1 2 3], [10 20 30], 2.4, 'nearest');
c = interp1([1 2 3], [10 20 30], 2.9, 'previous');
d = interp1([1 2 3], [10 20 30], 2.5, 'cubic');""")
    assert ws["a"][0, 0] == pytest.approx(25.0)
    assert ws["b"][0, 0] == 20.0
    assert ws["c"][0, 0] == 20.0
    assert ws["d"][0, 0] == pytest.approx(25.0)


def test_interp1_outside_range_options():
    with pytest.raises(EngStudioError):
        run("a = interp1([1 2 3], [10 20 30], 5);")
    ws = run("""a = interp1([1 2 3], [10 20 30], 5, 'linear', 'extrap');
b = interp1([1 2 3], [10 20 30], 5, 'linear', 0);
c = interp1([1 2 3], [10 20 30], 5, 'linear', NaN);""")
    assert ws["a"][0, 0] == pytest.approx(50.0)
    assert ws["b"][0, 0] == 0.0
    assert math.isnan(ws["c"][0, 0])


def test_std_var_known_values():
    ws = run("a = std([1 2 3 4]); b = std([1 2 3 4], 1); c = var([2 4 4 4 5 5 7 9], 1);")
    assert ws["a"][0, 0] == pytest.approx(math.sqrt(5 / 3))
    assert ws["b"][0, 0] == pytest.approx(math.sqrt(1.25))
    assert ws["c"][0, 0] == pytest.approx(4.0)  # classic textbook example, population variance


def test_std_var_matrix_columnwise():
    ws = run("a = std([1 2; 3 4; 5 6]); b = var([1 2; 3 4; 5 6]);")
    np.testing.assert_allclose(ws["a"], [[2, 2]])
    np.testing.assert_allclose(ws["b"], [[4, 4]])


def test_std_single_value_is_an_error():
    with pytest.raises(EngStudioError):
        run("a = std(5);")


def test_median_rms_zscore():
    ws = run("a = median([3 1 2]); b = median([1 2 3 4]); c = rms([3 4]); z = zscore([1 2 3]);")
    assert ws["a"][0, 0] == 2.0
    assert ws["b"][0, 0] == 2.5
    assert ws["c"][0, 0] == pytest.approx(math.sqrt(12.5))
    np.testing.assert_allclose(ws["z"], [[-1, 0, 1]])


def test_fft_known_transforms():
    ws = run("a = fft([1 0 0 0]); b = fft([1 1 1 1]); c = fft([1; 0; 0; 0]);")
    np.testing.assert_allclose(ws["a"], [[1, 1, 1, 1]], atol=1e-12)
    np.testing.assert_allclose(ws["b"], [[4, 0, 0, 0]], atol=1e-12)
    assert ws["c"].shape == (4, 1)


def test_fft_sine_amplitude_and_padding():
    # bin-centred sine, amplitude 1, N = 8: |X[1]| = N/2 = 4 (MATLAB index 2)
    ws = run("x = sin(2*pi*(0:7)/8); X = abs(fft(x)); Y = fft(x, 16);")
    assert ws["X"][0, 1] == pytest.approx(4.0)
    assert ws["Y"].shape == (1, 16)


def test_ifft_inverts_fft():
    ws = run("y = ifft(fft([1 2 3 4]));")
    np.testing.assert_allclose(ws["y"], [[1, 2, 3, 4]], atol=1e-12)
