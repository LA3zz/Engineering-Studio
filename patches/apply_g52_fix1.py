"""G5.2 test fixes (exact-match, idempotent): three wrong assumptions in test_gui_figures.py.
Run from the project root: python patches\\apply_g52_fix1.py"""

from __future__ import annotations

import sys
from pathlib import Path

PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/gui/test_gui_figures.py")

EDITS = [
    # pyqtgraph keeps pen=None as None (no line is drawn)
    ('    assert a.opts["pen"].style() == Qt.PenStyle.NoPen and a.opts["symbol"] == "o"\n',
     '    assert a.opts["pen"] is None or a.opts["pen"].style() == Qt.PenStyle.NoPen\n'
     '    assert a.opts["symbol"] == "o"\n'),
    # a BarGraphItem is listed among the plot's data items in this pyqtgraph version
    ("    assert plot.listDataItems() == []\n",
     "    assert not [i for i in plot.listDataItems() if isinstance(i, pg.PlotDataItem)]\n"),
    # test data: x and y must have the same length
    ('    win.set_figure(one_axes(series("bar", x=(1, 2)), xscale="log"))\n',
     '    win.set_figure(one_axes(series("bar", x=(1, 2), y=(1, 2)), xscale="log"))\n'),
]

with open(PATH, encoding="utf-8", newline="") as f:
    text = f.read()
nl = "\r\n" if "\r\n" in text else "\n"
for old, new in EDITS:
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    if new in text:
        continue  # already applied
    if text.count(old) != 1:
        sys.exit(f"{PATH.name}: expected text not found exactly once:\n{old}")
    text = text.replace(old, new)
with open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print(f"fixed {PATH.name}")
