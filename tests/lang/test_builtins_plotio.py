"""Animation and figure-file commands (P5.5)."""

import struct

import pytest

from engstudio.app.kernel.inprocess import to_function_syntax
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.builtins_plot import Publisher, install_plot
from engstudio.lang.figstate import FigureManager
from engstudio.lang.interp import Cancelled, Interpreter


class Rig:
    def __init__(self, interval=0.0):
        self.interp = Interpreter()
        install_core(self.interp)
        install_extra(self.interp)
        self.published = []
        self.manager = install_plot(self.interp, self.published.append, lambda n: None,
                                    min_interval=interval)

    def run(self, code):
        self.interp.execute(to_function_syntax(code), None)

    def ws(self, name):
        return self.interp.workspace[name]


@pytest.fixture
def rig():
    return Rig()


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def test_saveas_formats(rig, tmp_path):
    rig.run(f"plot(1:3); saveas(gcf, '{tmp_path / 'a.png'}'); saveas(1, '{tmp_path / 'b'}', 'pdf')")
    assert (tmp_path / "a.png").stat().st_size > 0
    assert (tmp_path / "b.pdf").read_bytes().startswith(b"%PDF")


def test_print_with_resolution(rig, tmp_path):
    rig.run(f"plot(1:3); print('-dpng', '-r50', '{tmp_path / 'p'}')")
    assert _png_size(tmp_path / "p.png") == (360, 240)  # 7.2 x 4.8 in at 50 dpi


def test_exportgraphics_svg_and_resolution(rig, tmp_path):
    rig.run(f"bar([1 2]); exportgraphics(gcf, '{tmp_path / 'e.svg'}');"
            f" exportgraphics(gcf, '{tmp_path / 'e.png'}', 'Resolution', 40)")
    assert b"<svg" in (tmp_path / "e.svg").read_bytes()[:400]
    assert _png_size(tmp_path / "e.png") == (288, 192)


def test_gif_animation_appends_frames(rig, tmp_path):
    from PIL import Image
    gif = tmp_path / "anim.gif"
    rig.run(f"x = linspace(0, 2*pi, 20); for k = 1:3, plot(x, sin(x + k));"
            f" exportgraphics(gcf, '{gif}', 'Append', true); end")
    with Image.open(gif) as im:
        assert im.n_frames == 3
    rig.run(f"exportgraphics(gcf, '{gif}')")  # without Append: a new file, one frame
    with Image.open(gif) as im:
        assert im.n_frames == 1


def test_animatedline_addpoints(rig):
    rig.run("h = animatedline('Color', 'r', 'MaximumNumPoints', 3);"
            " for k = 1:5, addpoints(h, k, k^2); end")
    (s,) = rig.published[-1].axes[0].series
    assert s.x.tolist() == [3, 4, 5] and s.y.tolist() == [9, 16, 25] and s.color == "#ff0000"
    rig.run("clearpoints(h)")
    assert rig.published[-1].axes[0].series[0].n_points == 0


def test_pause_flushes_and_sleeps(rig):
    import time
    rig.run("plot(1:3);")
    start = time.monotonic()
    rig.run("pause(0.12)")
    assert time.monotonic() - start >= 0.1


def test_pause_is_cancellable(rig):
    import threading
    t = threading.Timer(0.1, rig.interp.cancel)
    t.start()
    with pytest.raises(Cancelled):
        rig.interp.execute("pause(5)", None, reset_cancel=False)
    t.join()


def test_publisher_throttles_and_flushes():
    clock = [0.0]
    sent = []
    manager = FigureManager()
    manager.figure(1)
    pub = Publisher(sent.append, manager, min_interval=1.0, clock=lambda: clock[0])
    pub.push(1)
    pub.push(1)  # too soon: pending
    assert len(sent) == 1
    clock[0] = 2.0
    pub.push(1)
    assert len(sent) == 2
    pub.push(1)
    pub.flush()
    assert len(sent) == 3
    pub.flush()  # nothing pending
    assert len(sent) == 3


@pytest.mark.parametrize("code, text", [
    ("pause", "pause\\(seconds\\)"),
    ("pause(-1)", "non-negative"),
    ("plot(1); saveas(gcf, 'x.bmp')", "unsupported format"),
    ("saveas(7, 'x.png')", "does not exist"),
    ("plot(1); print('-dbmp', 'x')", "not supported"),
    ("plot(1); print('-dpng')", "printer"),
    ("plot(1); exportgraphics(gcf, 'x.png', 'Append', true)", "only supported for GIF"),
    ("plot(1); exportgraphics(gcf, 'x.png', 'Bogus', 1)", "unrecognized option"),
    ("addpoints(1, 2, 3)", "animatedline"),
])
def test_errors(rig, code, text, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(EngStudioError, match=text):
        rig.run(code)
