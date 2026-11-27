"""Figure export for the GUI. The GUI imports this, never ``plotting.export`` or Matplotlib;
Matplotlib itself is only imported when a figure is actually saved."""

from __future__ import annotations

from pathlib import Path

from engstudio.plotting.export import (
    EXPORT_FORMATS,
    MATPLOTLIB_LOCK,
    draw_figure,
    export_figure,
    load_matplotlib,
)
from engstudio.plotting.model import FigureSpec

__all__ = ["EXPORT_FORMATS", "MATPLOTLIB_LOCK", "draw_into", "load_matplotlib", "save_figure"]


def save_figure(spec: FigureSpec, path: Path | str, dpi: int = 150) -> Path:
    """Write ``spec`` as PNG/SVG/PDF (chosen by the file suffix). Raises ``ValidationError``
    for an unsupported suffix and ``EngStudioError`` if the file cannot be written."""
    return export_figure(spec, path, dpi=dpi)


def draw_into(figure: object, spec: FigureSpec) -> None:
    """Draw ``spec`` onto an empty Matplotlib ``Figure`` (the GUI's embedded canvas for 3-D,
    polar and contour/surface figures)."""
    draw_figure(figure, spec)  # type: ignore[arg-type]