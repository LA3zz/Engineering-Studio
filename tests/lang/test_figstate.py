"""Figure state and plot-argument tests (pure; the spec must hold exactly the inputs)."""

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.lang.figstate import (
    FigureManager,
    build_series,
    parse_color,
    parse_linespec,
)


def m(*rows):
    return np.array(rows, dtype=float)


def test_linespec_parts():
    assert parse_linespec("r--o") == ("#ff0000", "--", "o")
    assert parse_linespec("k-") == ("#000000", "-", None)
    assert parse_linespec("-.") == (None, "-.", None)
    assert parse_linespec("x") == (None, None, "x")


@pytest.mark.parametrize("bad", ["rr", "--:", "oo", "q", "r--z"])
def test_linespec_invalid(bad):
    with pytest.raises(ValidationError, match="invalid line specification"):
        parse_linespec(bad)


@pytest.mark.parametrize("spec, marker", [("d", "d"), ("rv", "v"), ("--<", "<"), (">", ">"),
                                          ("p", "p"), ("h:", "h")])
def test_linespec_all_matlab_markers(spec, marker):
    assert parse_linespec(spec)[2] == marker


def test_colors():
    assert parse_color("red") == "#ff0000"
    assert parse_color("#AABBCC") == "#aabbcc"
    assert parse_color(m([0.2, 0.45, 0.8])) == "#3373cc"  # 0.2*255=51, 0.45*255=114.75, 204
    with pytest.raises(ValidationError):
        parse_color(m([0, 2, 0]))
    with pytest.raises(ValidationError):
        parse_color("nocolor")


def test_plot_y_only_uses_1_to_n():
    (s,) = build_series([m([5, 6, 7])])
    assert s.x.tolist() == [1, 2, 3] and s.y.tolist() == [5, 6, 7]


def test_plot_xy_orientation_is_flattened():
    (s,) = build_series([m([1, 2, 3]), m([4], [5], [6])])
    assert s.x.tolist() == [1, 2, 3] and s.y.tolist() == [4, 5, 6]


def test_matrix_columns():
    y = m([1, 10], [2, 20], [3, 30])
    s = build_series([y])
    assert [v.y.tolist() for v in s] == [[1, 2, 3], [10, 20, 30]]
    assert all(v.x.tolist() == [1, 2, 3] for v in s)


def test_vector_x_matrix_y_rows_when_cols_match():
    y = m([1, 2, 3], [4, 5, 6])  # 2x3, x has 3 points -> two rows
    s = build_series([m([0, 1, 2]), y])
    assert [v.y.tolist() for v in s] == [[1, 2, 3], [4, 5, 6]]


def test_matrix_x_matrix_y_pairs_columns():
    x = m([0, 5], [1, 6])
    y = m([2, 7], [3, 8])
    s = build_series([x, y])
    assert [(v.x.tolist(), v.y.tolist()) for v in s] == [([0, 1], [2, 3]), ([5, 6], [7, 8])]


def test_several_groups_with_specs():
    s = build_series([m([0, 1]), m([2, 3]), "r--", m([4, 5]), "o"])
    assert [(v.kind, v.color, v.line_style, v.marker) for v in s] == [
        ("line", "#ff0000", "--", None), ("scatter", None, "-", "o")]
    assert s[1].x.tolist() == [1, 2]


def test_marker_with_line_stays_line():
    (s,) = build_series([m([1, 2]), "r--o"])
    assert (s.kind, s.marker, s.line_style) == ("line", "o", "--")


def test_name_value_pairs_apply_to_all():
    s = build_series([m([1, 2], [3, 4]), "Color", m([0, 0, 1]), "LineWidth", m([3]),
                      "DisplayName", "sig", "Marker", "s", "MarkerSize", m([9]),
                      "LineStyle", ":"])
    assert len(s) == 2
    for v in s:
        assert (v.color, v.line_width, v.label, v.marker, v.marker_size, v.line_style) == (
            "#0000ff", 3.0, "sig", "s", 9.0, ":")


def test_complex_single_argument_plots_real_vs_imag():
    (s,) = build_series([np.array([[1 + 2j, 3 - 1j]])])
    assert s.x.tolist() == [1, 3] and s.y.tolist() == [2, -1]


def test_errors():
    with pytest.raises(ValidationError, match="Not enough input"):
        build_series([])
    with pytest.raises(DimensionError, match="same length"):
        build_series([m([1, 2, 3]), m([1, 2])])
    with pytest.raises(DimensionError):
        build_series([m([1, 2, 3]), m([1, 2], [3, 4])])
    with pytest.raises(ValidationError, match="pairs"):
        build_series([m([1, 2]), "Color"])
    with pytest.raises(ValidationError, match="unrecognized property"):
        build_series([m([1, 2]), "Colour", "r"])
    with pytest.raises(ValidationError, match="positive"):
        build_series([m([1, 2]), "LineWidth", m([0])])
    with pytest.raises(ValidationError, match="complex"):
        build_series([m([1, 2]), np.array([[1j, 2]])])
    with pytest.raises(ValidationError, match="expected data"):
        build_series(["Color", "r"])


def test_empty_data():
    (s,) = build_series([np.empty((0, 0)), np.empty((0, 0))])
    assert s.n_points == 0


# ------------------------------------------------------------------ manager
def test_figure_numbers_and_current():
    fm = FigureManager()
    assert fm.figure() == 1 and fm.figure() == 2 and fm.figure(5) == 5
    assert fm.figure() == 3  # lowest unused
    assert fm.gcf() == 3
    fm.figure(1)
    assert fm.gcf() == 1 and fm.numbers() == [1, 2, 3, 5]


def test_gcf_creates_figure():
    fm = FigureManager()
    assert fm.gcf() == 1 and fm.numbers() == [1]


def test_figure_number_validation():
    with pytest.raises(ValidationError):
        FigureManager().figure(0)


def test_plot_replaces_unless_hold():
    fm = FigureManager()
    fm.add_lines(build_series([m([1, 2])]))
    fm.add_lines(build_series([m([3, 4])]))
    assert len(fm.snapshot().axes[0].series) == 1
    assert fm.snapshot().axes[0].series[0].y.tolist() == [3, 4]
    fm.hold("on")
    fm.add_lines(build_series([m([5, 6])]))
    assert [s.y.tolist() for s in fm.snapshot().axes[0].series] == [[3, 4], [5, 6]]
    assert fm.ishold() is True
    fm.hold("off")
    fm.add_lines(build_series([m([7, 8])]))
    assert len(fm.snapshot().axes[0].series) == 1


def test_hold_toggle_and_bad_option():
    fm = FigureManager()
    assert fm.hold() is True and fm.hold() is False
    with pytest.raises(ValidationError, match="unknown option"):
        fm.hold("maybe")


def test_handles_unique_and_axes_stable():
    fm = FigureManager()
    ax = fm.gca()
    h1 = fm.add_lines(build_series([m([1, 2], [3, 4])]))
    assert len(set(h1 + [ax])) == 3 and fm.gca() == ax and min(h1 + [ax]) > 100000


def test_clf_cla_close():
    fm = FigureManager()
    fm.add_lines(build_series([m([1, 2])]))
    fm.cla()
    assert fm.snapshot().axes[0].series == ()
    fm.add_lines(build_series([m([1, 2])]))
    fm.clf()
    assert fm.snapshot().axes == ()
    fm.figure(2)
    assert fm.close() == [2] and fm.gcf() == 1
    fm.figure(7)
    assert fm.close(1) == [1] and fm.numbers() == [7]
    with pytest.raises(ValidationError, match="does not exist"):
        fm.close(9)
    assert fm.close("all") == [7] and fm.numbers() == []
    assert fm.close() == []  # nothing open: no error, no figure created
    assert fm.numbers() == []


def test_name_in_snapshot():
    fm = FigureManager()
    fm.figure(1, name="Mode shapes", props={"Color": "w"})
    assert fm.snapshot().name == "Mode shapes"
    assert fm.props(1) == {"Color": "w"}
