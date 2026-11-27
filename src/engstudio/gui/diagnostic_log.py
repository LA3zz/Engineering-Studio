"""History of kernel diagnostics for the Diagnostics panel. Pure Python (no Qt).

Entries are kept across executions (oldest dropped beyond ``cap``) until cleared. A
``SourceLoc`` is read by field position (file, line, column), the order the kernel builds it in,
so the panel does not depend on the field names.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePath

from engstudio.app.kernel.protocol import Diagnostics

__all__ = ["CAP", "SEVERITIES", "SEVERITY_COLORS", "DiagnosticEntry", "DiagnosticLog",
           "format_location", "location_parts"]

SEVERITIES = ("error", "warning", "info")
CAP = 500

# Text colours per theme; each has contrast >= 4.5 against the table's row backgrounds
# (tests/gui/test_diagnostic_log.py).
SEVERITY_COLORS: dict[str, dict[str, str]] = {
    "light": {"error": "#b3261e", "warning": "#8a5a00", "info": "#0b5cad"},
    "dark": {"error": "#ff8a80", "warning": "#ffcc66", "info": "#7db7ff"},
}


def location_parts(loc: object) -> tuple[str | None, int | None, int | None]:
    """(file, line, column) of a ``SourceLoc``; all ``None`` for no location."""
    if loc is None:
        return None, None, None
    if dataclasses.is_dataclass(loc) and not isinstance(loc, type):
        values = [getattr(loc, f.name) for f in dataclasses.fields(loc)]
    else:
        values = [getattr(loc, name, None) for name in ("file", "line", "col")]
    values += [None] * (3 - len(values))
    file, line, col = values[:3]
    return (
        None if file is None else str(file),
        line if isinstance(line, int) else None,
        col if isinstance(col, int) else None,
    )


def format_location(file: str | None, line: int | None, col: int | None) -> str:
    if line is None:
        return ""
    where = f"line {line}" + (f", col {col}" if col is not None else "")
    if file:
        return f"{PurePath(file).name}: {where}"
    return where


@dataclass(frozen=True)
class DiagnosticEntry:
    seq: int  # grows for the lifetime of the log (clearing does not reset it)
    request_id: int
    severity: str
    code: str
    message: str
    file: str | None = None
    line: int | None = None
    col: int | None = None

    @property
    def location_text(self) -> str:
        return format_location(self.file, self.line, self.col)


class DiagnosticLog:
    def __init__(self, cap: int = CAP) -> None:
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
            raise ValueError(f"cap must be an integer >= 1, got {cap!r}")
        self.cap = cap
        self.dropped = 0  # entries discarded because the log was full
        self._entries: list[DiagnosticEntry] = []
        self._next_seq = 1

    @property
    def entries(self) -> tuple[DiagnosticEntry, ...]:
        return tuple(self._entries)

    def add(self, event: Diagnostics) -> int:
        """Append the items of a ``Diagnostics`` event; returns how many were added.
        An unknown severity is stored as ``info``."""
        for item in event.items:
            file, line, col = location_parts(item.location)
            severity = item.severity if item.severity in SEVERITIES else "info"
            self._entries.append(DiagnosticEntry(
                self._next_seq, event.request_id, severity, item.code, item.message,
                file, line, col))
            self._next_seq += 1
        excess = len(self._entries) - self.cap
        if excess > 0:
            del self._entries[:excess]
            self.dropped += excess
        return len(event.items)

    def clear(self) -> None:
        self._entries.clear()
        self.dropped = 0

    def counts(self) -> dict[str, int]:
        out = dict.fromkeys(SEVERITIES, 0)
        for e in self._entries:
            out[e.severity] += 1
        return out

    def visible(self, severities: Collection[str]) -> list[DiagnosticEntry]:
        return [e for e in self._entries if e.severity in severities]
