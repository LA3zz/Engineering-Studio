"""Qt-free display helpers shared by GUI panels."""

from __future__ import annotations

from collections.abc import Sequence


def format_size(size: Sequence[int]) -> str:
    """``(3, 4)`` -> ``"3x4"``; N-d sizes join with ``x``; an empty size shows as ``"0x0"``."""
    return "x".join(str(int(n)) for n in size) if size else "0x0"
