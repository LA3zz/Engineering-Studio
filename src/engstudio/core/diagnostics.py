"""Structured diagnostics: messages as data, never printed or raised implicitly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

Severity = Literal["info", "warning", "error"]
_SEVERITIES = get_args(Severity)


@dataclass(frozen=True)
class SourceLoc:
    """Position in a source file. Lines and columns are 1-based."""

    file: str | None = None
    line: int | None = None
    col: int | None = None

    def __str__(self) -> str:
        parts = [self.file or "<input>"]
        if self.line is not None:
            parts.append(str(self.line))
            if self.col is not None:
                parts.append(str(self.col))
        return ":".join(parts)


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    location: SourceLoc | None = None

    def __post_init__(self) -> None:
        if self.severity not in _SEVERITIES:
            raise ValueError(f"invalid severity {self.severity!r}; expected one of {_SEVERITIES}")
        if not self.code:
            raise ValueError("diagnostic code must be non-empty")

    def __str__(self) -> str:
        prefix = f"{self.location}: " if self.location else ""
        return f"{prefix}{self.severity} [{self.code}] {self.message}"


def info(code: str, message: str, location: SourceLoc | None = None) -> Diagnostic:
    return Diagnostic("info", code, message, location)


def warning(code: str, message: str, location: SourceLoc | None = None) -> Diagnostic:
    return Diagnostic("warning", code, message, location)


def error(code: str, message: str, location: SourceLoc | None = None) -> Diagnostic:
    return Diagnostic("error", code, message, location)