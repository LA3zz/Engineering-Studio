"""plotting.model: validation, normalisation, immutability, pickling (pure logic, no Qt)."""

from __future__ import annotations

import dataclasses
import pickle

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec


def line(x=(0, 1, 2), y=(0, 1, 4), **kw):
    return SeriesSpec("line", x, y, **kw)


# -- SeriesSpec: data ----------------------------------------------------------------
def test_vectors_become_readonly_float64():
    s = line([1, 2, 3], (4, 5, 6))
    assert s.x.dtype == np.float64 and s.y.dtype == np.float64
    assert s.x.shape == (3,) and s.n_points == 3
    with pytest.raises(ValueError):
        s.x[0] = 9.0


def test_row_column_and_scalar_inputs_are_flattened():
    assert line(np.array([[1.0, 2.0, 3.0]]), np.array([[1.0], [2.0], [3.0]])).x.shape == (3,)
    one = SeriesSpec("scatter", 2, 3)
    assert one.x.tolist() == [2.0] and one.y.tolist() == [3.0]


def test_input_is_copied_not_shared_or_mutated():
    xs = np.array([0.0, 1.0, 2.0])
    s = line(xs, xs.copy())
    xs[0] = 99.0
    assert s.x[0] == 0.0
    assert xs[0] == 99.0  # caller's array untouched by construction


def test_matrix_and_3d_data_are_rejected():
    with pytest.raises(DimensionError):
        line(np.ones((2, 2)), np.ones((2, 2)))
    with pytest.raises(DimensionError):
        line(np.ones((2, 2, 2)), np.ones(8))


def test_length_mismatch_names_both_lengths():
    with pytest.raises(DimensionError, match="3 points but y has 2"):
        line([1, 2, 3], [1, 2])
    assert issubclass(DimensionError, ValidationError)


def test_complex_and_text_data_are_rejected():
    with pytest.raises(ValidationError):
        line([1, 2], [1 + 1j, 2])
    with pytest.raises(ValidationError):
        line(["a", "b"], [1, 2])
    with pytest.raises(ValidationError):
        line([1, 2], [object(), 2])


def test_nan_is_allowed_and_compares_equal():
    a = line([0, 1, 2], [1, np.nan, 3])
    b = line([0, 1, 2], [1, np.nan, 3])
    assert a == b
    assert a != line([0, 1, 2], [1, 2, 3])


def test_empty_series_is_valid():
    assert line([], []).n_points == 0


# -- SeriesSpec: style ---------------------------------------------------------------
def test_style_defaults_and_valid_values():
    s = line(label="v", color="#1A2b3C", line_style="--", line_width=2, marker="o",
             marker_size=4)
    assert (s.label, s.color, s.line_style, s.line_width, s.marker, s.marker_size) == (
        "v", "#1A2b3C", "--", 2.0, "o", 4.0)
    d = line()
    assert d.color is None and d.marker is None and d.line_style == "-"


@pytest.mark.parametrize("kw", [
    {"color": "red"}, {"color": "#12345"}, {"color": 5}, {"line_style": "~"}, {"marker": "q"},
    {"line_width": 0}, {"line_width": -1}, {"line_width": float("inf")},
    {"line_width": "x"}, {"marker_size": 0}, {"label": 3},
])
def test_invalid_style_is_rejected(kw):
    with pytest.raises(ValidationError):
        line(**kw)


def test_invalid_kind_is_rejected():
    with pytest.raises(ValidationError):
        SeriesSpec("pie", [1], [1])  # type: ignore[arg-type]


def test_series_is_frozen():
    s = line()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.label = "x"  # type: ignore[misc]


# -- AxesSpec ------------------------------------------------------------------------
def test_axes_defaults_and_series_coerced_to_tuple():
    assert AxesSpec().series == () and AxesSpec().xscale == "linear"
    ax = AxesSpec(series=[line(), line()], title="T", grid=1, legend=0)
    assert isinstance(ax.series, tuple) and len(ax.series) == 2
    assert ax.grid is True and ax.legend is False


def test_axes_rejects_wrong_types():
    with pytest.raises(ValidationError):
        AxesSpec(series=("not a series",))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        AxesSpec(title=3)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        AxesSpec(xscale="sqrt")


def test_limits_are_validated_and_normalised():
    assert AxesSpec(xlim=[0, 10]).xlim == (0.0, 10.0)
    for bad in [(1, 1), (2, 1), (0, float("inf")), (float("nan"), 1), (1,), "ab", 5]:
        with pytest.raises(ValidationError):
            AxesSpec(ylim=bad)  # type: ignore[arg-type]


def test_log_axis_needs_positive_limits():
    assert AxesSpec(xscale="log", xlim=(0.1, 10)).xlim == (0.1, 10.0)
    with pytest.raises(ValidationError):
        AxesSpec(xscale="log", xlim=(0, 10))
    with pytest.raises(ValidationError):
        AxesSpec(yscale="log", ylim=(-1, 10))
    assert AxesSpec(xlim=(-5, 5)).xlim == (-5.0, 5.0)  # fine on a linear axis


# -- FigureSpec ----------------------------------------------------------------------
def test_figure_defaults():
    f = FigureSpec()
    assert (f.number, f.rows, f.cols, f.axes, f.title) == (1, 1, 1, (), "")


def test_figure_grid_capacity():
    ax = AxesSpec()
    assert len(FigureSpec(axes=[ax, ax, ax], rows=2, cols=2).axes) == 3
    with pytest.raises(ValidationError, match="do not fit"):
        FigureSpec(axes=[ax, ax], rows=1, cols=1)


@pytest.mark.parametrize("kw", [
    {"number": 0}, {"number": True}, {"number": 1.5}, {"rows": 0}, {"cols": -1},
    {"title": 1}, {"axes": ("x",)},
])
def test_figure_rejects_invalid_values(kw):
    with pytest.raises(ValidationError):
        FigureSpec(**kw)


def test_replace_revalidates():
    f = FigureSpec(number=3)
    assert dataclasses.replace(f, title="t").title == "t"
    with pytest.raises(ValidationError):
        dataclasses.replace(f, number=0)


def test_figure_equality_and_pickle_round_trip():
    f = FigureSpec(number=2, title="Fig", axes=(
        AxesSpec(series=(line(label="a", color="#000000"),
                         SeriesSpec("bar", [1, 2], [3, np.nan])),
                 xlim=(0, 2), legend=True),
    ))
    g = pickle.loads(pickle.dumps(f))
    assert g == f and g is not f
    assert g.axes[0].series[0].x.flags.writeable is False
    assert g != dataclasses.replace(f, title="other")


def test_deepcopy_keeps_data_readonly_and_equal():
    import copy

    s = line(label="a")
    c = copy.deepcopy(s)
    assert c == s and c.x.flags.writeable is False and c.y.flags.writeable is False
