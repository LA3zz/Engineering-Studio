"""format_size tests (no Qt needed)."""

from __future__ import annotations

import pytest

from engstudio.gui.formatting import format_size


@pytest.mark.parametrize("size,text", [
    ((1, 1), "1x1"), ((3, 4), "3x4"), ((2, 3, 4), "2x3x4"), ((0, 0), "0x0"), ((), "0x0"),
    ([5, 1], "5x1"),
])
def test_format_size(size, text):
    assert format_size(size) == text
