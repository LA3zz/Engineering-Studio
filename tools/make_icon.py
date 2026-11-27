"""Draw the Engineering Studio icon (src/engstudio/gui/engstudio.ico) with Pillow.

A rounded blue tile with a white damped-oscillation curve. Run from the project root:
``python tools/make_icon.py``.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "src" / "engstudio" / "gui" / "engstudio.ico"


def draw(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 6
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=(31, 92, 168, 255))
    d.rounded_rectangle((size * 0.06, size * 0.06, size * 0.94, size * 0.94), radius=r * 0.8,
                        outline=(255, 255, 255, 60), width=max(1, size // 64))
    pts = []
    for i in range(200):
        t = i / 199
        x = size * (0.12 + 0.76 * t)
        y = size * (0.5 - 0.3 * math.exp(-2.6 * t) * math.cos(2 * math.pi * 3.2 * t))
        pts.append((x, y))
    d.line(pts, fill=(255, 255, 255, 255), width=max(2, size // 22), joint="curve")
    d.line([(size * 0.12, size * 0.8), (size * 0.88, size * 0.8)], fill=(255, 196, 61, 255),
           width=max(2, size // 32))
    return img


if __name__ == "__main__":
    draw().save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                            (256, 256)])
    print("wrote", OUT)
