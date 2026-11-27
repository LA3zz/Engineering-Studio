"""Start-up splash: a card drawn with vector graphics at the screen's real resolution, so it
stays sharp at any display scaling (the old splash enlarged the 48-pixel icon)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QSplashScreen

from engstudio.version import APP_NAME, __version__

__all__ = ["make_splash", "splash_pixmap"]

WIDTH, HEIGHT = 560, 300
_NAVY, _BLUE, _ACCENT = QColor("#0f2a47"), QColor("#1b5fa3"), QColor("#f2b134")


def _logo(p: QPainter, box: QRectF) -> None:
    """Rounded tile with a damped oscillation, like the app icon."""
    tile = QPainterPath()
    tile.addRoundedRect(box, box.width() * 0.18, box.width() * 0.18)
    grad = QLinearGradient(box.topLeft(), box.bottomRight())
    grad.setColorAt(0, QColor("#2c7be5"))
    grad.setColorAt(1, QColor("#174a8b"))
    p.fillPath(tile, grad)
    m = box.width() * 0.14
    left, right = box.left() + m, box.right() - m
    mid = box.top() + box.height() * 0.48
    amp = box.height() * 0.30
    wave = QPainterPath()
    n = 120
    for i in range(n + 1):
        s = i / n
        x = left + s * (right - left)
        y = mid - amp * math.exp(-3.2 * s) * math.cos(2 * math.pi * 3.2 * s)
        wave.moveTo(x, y) if i == 0 else wave.lineTo(x, y)
    p.setPen(QPen(QColor("white"), box.width() * 0.055, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(wave)
    p.setPen(QPen(_ACCENT, box.width() * 0.045, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    base = box.bottom() - box.height() * 0.17
    p.drawLine(QPointF(left, base), QPointF(right, base))


def splash_pixmap(scale: float = 1.0) -> QPixmap:
    pm = QPixmap(round(WIDTH * scale), round(HEIGHT * scale))
    pm.setDevicePixelRatio(scale)
    pm.fill(_NAVY)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    bg = QLinearGradient(0, 0, WIDTH, HEIGHT)
    bg.setColorAt(0, _NAVY)
    bg.setColorAt(1, QColor("#16406b"))
    p.fillRect(QRectF(0, 0, WIDTH, HEIGHT), bg)
    p.fillRect(QRectF(0, 0, WIDTH, 5), _ACCENT)
    _logo(p, QRectF(40, 62, 124, 124))
    title = QFont("Segoe UI", 26)
    title.setWeight(QFont.Weight.DemiBold)
    p.setFont(title)
    p.setPen(QColor("white"))
    p.drawText(QRectF(190, 70, WIDTH - 210, 50), Qt.AlignmentFlag.AlignLeft
               | Qt.AlignmentFlag.AlignVCenter, APP_NAME)
    sub = QFont("Segoe UI", 11)
    p.setFont(sub)
    p.setPen(QColor("#c9d9ec"))
    p.drawText(QRectF(192, 122, WIDTH - 210, 24), Qt.AlignmentFlag.AlignLeft,
               "Offline engineering computation")
    p.setPen(_ACCENT)
    p.drawText(QRectF(192, 148, WIDTH - 210, 24), Qt.AlignmentFlag.AlignLeft,
               f"Version {__version__}")
    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    p.drawLine(QPointF(40, HEIGHT - 58), QPointF(WIDTH - 40, HEIGHT - 58))
    p.end()
    return pm


def make_splash() -> QSplashScreen:
    screen = QGuiApplication.primaryScreen()
    scale = screen.devicePixelRatio() if screen is not None else 1.0
    splash = QSplashScreen(splash_pixmap(scale))
    font = QFont("Segoe UI", 10)
    splash.setFont(font)
    return splash


def show_status(splash: QSplashScreen, text: str) -> None:
    splash.showMessage(f"    {text}", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                       QColor("#c9d9ec"))
