"""The engine API docs page lists every documented module and function that exists."""

from __future__ import annotations

import importlib
import re

import pytest

from engstudio.app.docs import DocService

PAGE = "engine-api"
NAMES = {
    "validation": ["as_matrix", "as_vector", "singular_error"],
    "linalg": ["solve", "inv", "det", "trace", "matmul", "transpose", "ctranspose", "dot",
               "cross", "norm", "rank", "cond", "rcond"],
    "decomp": ["lu", "qr", "svd", "cholesky", "eig", "eigh"],
    "calculus": ["derivative", "gradient", "jacobian", "derivative_data", "quad", "dblquad",
                 "trapz", "simpson", "cumtrapz"],
    "roots": ["bisect", "brentq", "newton", "secant", "fsolve", "polyroots"],
    "interp": ["interp1", "interp2"],
    "regression": ["linfit", "polyfit", "polyval", "fit_curve", "confidence_intervals"],
    "optimize": ["minimize_scalar", "minimize", "linprog"],
    "stats": ["mean", "median", "var", "std", "sem", "rms", "skewness", "kurtosis", "iqr",
              "quantile", "zscore", "cov", "pearsonr", "summary", "confidence_interval_mean",
              "ttest_1samp", "ttest_ind", "ttest_paired", "histogram"],
    "ode": ["solve_ode"],
    "transforms": ["fft", "ifft", "rfft", "irfft", "fftfreq", "rfftfreq", "window",
                   "amplitude_spectrum", "psd", "convolve", "butter_filter"],
    "symbolic": ["parse", "simplify", "expand", "factor", "subs", "equivalent", "to_numeric",
                 "lambdify", "diff", "integrate", "limit", "series", "solve", "solve_system",
                 "laplace", "inverse_laplace"],
    "uncertainty": ["propagate"],
}


@pytest.fixture(scope="module")
def text():
    return DocService().read(PAGE)


def test_page_is_registered_and_linked():
    s = DocService()
    assert PAGE in s.names()
    assert PAGE in {s.resolve(h) for h in s.links("index")}


@pytest.mark.parametrize("module", sorted(NAMES))
def test_module_section_present(text, module):
    assert re.search(rf"^## {module}\b", text, flags=re.M), module


@pytest.mark.parametrize("module", sorted(NAMES))
def test_documented_names_exist_and_are_mentioned(text, module):
    mod = importlib.import_module(f"engstudio.engine.{module}")
    for name in NAMES[module]:
        assert hasattr(mod, name), f"engine.{module}.{name} does not exist"
        assert re.search(rf"\b{re.escape(name)}\b", text), f"{name} missing from page"
