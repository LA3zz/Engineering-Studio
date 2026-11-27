"""The start-up splash is drawn at the screen's resolution (sharp at any scaling)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.gui.splash import HEIGHT, WIDTH, make_splash, show_status, splash_pixmap  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_pixmap_matches_the_display_scale(app, scale):
    pm = splash_pixmap(scale)
    assert not pm.isNull()
    assert (pm.width(), pm.height()) == (round(WIDTH * scale), round(HEIGHT * scale))
    assert pm.devicePixelRatio() == scale
    img = pm.toImage()
    assert img.pixelColor(5, 2).name() == "#f2b134"  # accent bar along the top


def test_splash_shows_status(app, qtbot):
    s = make_splash()
    qtbot.addWidget(s)
    show_status(s, "Loading")
    assert "Loading" in s.message()
