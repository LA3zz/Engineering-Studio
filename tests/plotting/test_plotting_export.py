"""plotting.export: files on disk and the Matplotlib figure that is built (needs Matplotlib)."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError, ValidationError
from engstudio.gui.plot_params import bar_width as gui_bar_width
from engstudio.plotting.export import EXPORT_FORMATS, _bar_width, build_figure, export_figure
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec


def line(x=(0, 1, 2), y=(0, 1, 4), **kw):
    return SeriesSpec("line", x, y, **kw)


def fig_of(*axes, **kw):
    return FigureSpec(axes=tuple(axes), **kw)


def simple():
    return fig_of(AxesSpec(series=(line(),)))


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])  # IHDR width, height


# -- files ---------------------------------------------------------------------------
def test_png_has_the_requested_pixel_size(tmp_path):
    out = export_figure(simple(), tmp_path / "a.png", dpi=100, size_in=(6, 4))
    assert out == tmp_path / "a.png"
    assert png_size(out) == (600, 400)


def test_dpi_scales_the_png(tmp_path):
    out = export_figure(simple(), tmp_path / "b.png", dpi=50, size_in=(6, 4))
    assert png_size(out) == (300, 200)


def test_svg_and_pdf_are_written(tmp_path):
    svg = export_figure(simple(), tmp_path / "c.svg")
    assert b"<svg" in svg.read_bytes()[:2000]
    pdf = export_figure(simple(), tmp_path / "d.pdf")
    assert pdf.read_bytes()[:5] == b"%PDF-"


def test_suffix_is_case_insensitive(tmp_path):
    assert png_size(export_figure(simple(), tmp_path / "e.PNG", dpi=40))[0] > 0


def test_every_advertised_format_is_exportable(tmp_path):
    assert set(EXPORT_FORMATS) == {"png", "svg", "pdf"}
    for ext in EXPORT_FORMATS:
        assert export_figure(simple(), tmp_path / f"f.{ext}", dpi=40).stat().st_size > 500


def test_unsupported_suffix_is_rejected_and_nothing_is_written(tmp_path):
    for name in ("g.jpg", "g", "g.png.bak"):
        with pytest.raises(ValidationError, match="supported: .png, .svg, .pdf"):
            export_figure(simple(), tmp_path / name)
    assert list(tmp_path.iterdir()) == []


def test_invalid_arguments_are_rejected_before_writing(tmp_path):
    for kw in ({"dpi": 0}, {"dpi": 5000}, {"dpi": 1.5}, {"dpi": True}, {"dpi": "x"},
               {"size_in": (0, 4)}, {"size_in": (6,)}, {"size_in": "ab"},
               {"size_in": (float("nan"), 4)}, {"size_in": (200, 4)}):
        with pytest.raises(ValidationError):
            export_figure(simple(), tmp_path / "h.png", **kw)
    with pytest.raises(ValidationError):
        export_figure("not a figure", tmp_path / "h.png")  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []


def test_unwritable_target_raises_engstudio_error_and_leaves_no_temp_file(tmp_path):
    with pytest.raises(EngStudioError, match="cannot write"):
        export_figure(simple(), tmp_path / "missing_folder" / "i.png")
    assert list(tmp_path.iterdir()) == []


def test_failure_after_writing_removes_the_temp_file(tmp_path):
    target = tmp_path / "m.png"
    target.mkdir()  # the temp file is written, then the final rename must fail
    with pytest.raises(EngStudioError, match="cannot write"):
        export_figure(simple(), target, dpi=40)
    assert [p.name for p in tmp_path.iterdir()] == ["m.png"]
    assert target.is_dir()


def test_success_leaves_no_temp_file_and_overwrites(tmp_path):
    target = tmp_path / "j.png"
    target.write_bytes(b"old")
    export_figure(simple(), target, dpi=40)
    assert [p.name for p in tmp_path.iterdir()] == ["j.png"]
    assert target.read_bytes()[:4] == b"\x89PNG"


def test_empty_figure_and_nan_data_export(tmp_path):
    assert export_figure(FigureSpec(), tmp_path / "k.png", dpi=40).exists()
    nan = fig_of(AxesSpec(series=(line(y=(1, float("nan"), 3)),)))
    assert export_figure(nan, tmp_path / "l.png", dpi=40).exists()


def test_rich_figure_exports_in_all_formats(tmp_path):
    rich = fig_of(
        AxesSpec(series=(line(label="a"), SeriesSpec("scatter", [1, 2], [1, 2], marker="^")),
                 title="T", xlabel="x", ylabel="y", grid=True, legend=True, xlim=(0, 3)),
        AxesSpec(series=(SeriesSpec("bar", [1, 2, 3], [3, 1, 2], label="b"),),
                 yscale="log", ylim=(0.5, 5), legend=True),
        AxesSpec(series=(line(x=(1, 10, 100), y=(1, 2, 3)),), xscale="log"),
        title="Figure", rows=2, cols=2)
    for ext in EXPORT_FORMATS:
        assert export_figure(rich, tmp_path / f"rich.{ext}", dpi=60).stat().st_size > 1000


# -- the Matplotlib figure that gets drawn -----------------------------------------------
def test_axes_text_scales_limits_and_grid():
    fig = build_figure(fig_of(AxesSpec(
        series=(line(),), title="T", xlabel="X", ylabel="Y", xscale="log", xlim=(1, 100),
        ylim=(-1, 5), grid=True), title="Main"))
    (ax,) = fig.axes
    assert (ax.get_title(), ax.get_xlabel(), ax.get_ylabel()) == ("T", "X", "Y")
    assert ax.get_xscale() == "log" and ax.get_yscale() == "linear"
    assert ax.get_xlim() == pytest.approx((1, 100)) and ax.get_ylim() == pytest.approx((-1, 5))
    assert any(g.get_visible() for g in ax.get_xgridlines())
    assert fig.get_suptitle() == "Main"


def test_no_grid_title_or_legend_unless_requested():
    fig = build_figure(fig_of(AxesSpec(series=(line(label="a"),))))
    (ax,) = fig.axes
    assert ax.get_title() == "" and ax.get_legend() is None
    assert not any(g.get_visible() for g in ax.get_xgridlines())
    assert fig.get_suptitle() == ""


def test_line_scatter_and_style_properties():
    fig = build_figure(fig_of(AxesSpec(series=(
        line(color="#112233", line_width=2, line_style="--", marker="s", marker_size=7),
        SeriesSpec("scatter", [0, 1], [1, 2]),
        SeriesSpec("scatter", [0, 1], [1, 2], marker="^", color="#445566"),
    ))))
    a, b, c = fig.axes[0].lines
    assert a.get_color() == "#112233" and a.get_linewidth() == 2
    assert a.get_linestyle() == "--" and a.get_marker() == "s" and a.get_markersize() == 7
    assert b.get_linestyle() == "None" and b.get_marker() == "o"
    assert c.get_marker() == "^" and c.get_color() == "#445566"


def test_data_is_passed_unchanged():
    fig = build_figure(fig_of(AxesSpec(series=(line([0, 1, 2], [5, float("nan"), 7]),))))
    (ln,) = fig.axes[0].lines
    assert ln.get_xdata().tolist() == [0, 1, 2]
    y = ln.get_ydata()
    assert y[0] == 5 and np.isnan(y[1]) and y[2] == 7


def test_bars_heights_width_and_log_axis():
    fig = build_figure(fig_of(AxesSpec(
        series=(SeriesSpec("bar", [1, 2, 4], [3, 5, 2], label="b"),), yscale="log")))
    ax = fig.axes[0]
    assert [p.get_height() for p in ax.patches] == [3, 5, 2]
    assert ax.patches[0].get_width() == pytest.approx(0.8)
    assert ax.get_yscale() == "log"


def test_legend_lists_only_labelled_series():
    fig = build_figure(fig_of(AxesSpec(series=(line(label="a"), line(), line(label="b")),
                                       legend=True)))
    assert [t.get_text() for t in fig.axes[0].get_legend().get_texts()] == ["a", "b"]
    unlabelled = build_figure(fig_of(AxesSpec(series=(line(),), legend=True)))
    assert unlabelled.axes[0].get_legend() is None  # nothing to list, no warning either


def test_subplot_grid_is_row_major():
    a = AxesSpec(series=(line(),), title="1")
    b = AxesSpec(series=(line(),), title="2")
    c = AxesSpec(series=(line(),), title="3")
    fig = build_figure(fig_of(a, b, c, rows=2, cols=2))
    assert [ax.get_title() for ax in fig.axes] == ["1", "2", "3"]
    positions = [ax.get_subplotspec() for ax in fig.axes]
    assert [(p.rowspan.start, p.colspan.start) for p in positions] == [(0, 0), (0, 1), (1, 0)]


def test_bar_width_agrees_with_the_gui_renderer():
    for xs in ([1, 2, 3], [0, 0.5, 2], [3, 1, 2], [1, 1, 2], [5], [], [1.0, float("nan"), 2.0]):
        assert _bar_width(np.array(xs, dtype=float)) == pytest.approx(gui_bar_width(xs))


def test_export_does_not_touch_pyplot_or_global_state():
    import sys

    before = "matplotlib.pyplot" in sys.modules
    build_figure(simple())
    assert ("matplotlib.pyplot" in sys.modules) == before


# ----------------------------------------------------------------- P5.2 / P5.3 export
def test_cells_span_and_suptitle():
    spec = FigureSpec(rows=2, cols=2, title="\\theta modes", axes=(
        AxesSpec(series=(line(),), cell=(0, 0, 1, 1)),
        AxesSpec(series=(line(),), cell=(0, 1, 1, 1)),
        AxesSpec(series=(line(),), cell=(1, 0, 1, 2))))
    fig = build_figure(spec)
    spans = [ax.get_subplotspec() for ax in fig.axes]
    assert [(s.rowspan.start, s.colspan.start, len(s.colspan)) for s in spans] == [
        (0, 0, 1), (0, 1, 1), (1, 0, 2)]
    assert fig._suptitle.get_text() == "θ modes"


def test_ticks_labels_tex_and_kinds():
    ax_spec = AxesSpec(
        series=(SeriesSpec("bar", (1, 2), (1, -1), bar_width=0.6, base_value=0.0),
                SeriesSpec("stem", (1, 2), (0.5, 0.2), marker="o"),
                SeriesSpec("area", (1, 2), (0.1, 0.3))),
        xticks=(1, 2), xticklabels=("\\theta_1", "\\theta_2"), title="m/s^2",
        ylabel="\\omega")
    (ax,) = build_figure(fig_of(ax_spec)).axes
    assert [t.get_text() for t in ax.get_xticklabels()] == ["θ$_{1}$", "θ$_{2}$"]
    assert ax.get_title() == "m/s$^{2}$" and ax.get_ylabel() == "ω"
    assert len(ax.patches) == 2 and ax.patches[0].get_width() == pytest.approx(0.6)


def test_new_markers_export(tmp_path):
    spec = fig_of(AxesSpec(series=tuple(
        SeriesSpec("line", (0, 1), (0, 1), marker=m) for m in ("d", "v", "<", ">", "p", "h"))))
    assert export_figure(spec, tmp_path / "m.png").exists()
