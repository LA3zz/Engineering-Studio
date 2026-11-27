"""Kernel messages (versioned frozen dataclasses). Plain data only, safe to send over a pipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engstudio.core.diagnostics import Diagnostic
from engstudio.plotting.model import FigureSpec

PROTOCOL_VERSION = 1

# -- requests (GUI -> kernel) -------------------------------------------------


@dataclass(frozen=True)
class Execute:
    request_id: int
    code: str


@dataclass(frozen=True)
class Cancel:
    request_id: int


@dataclass(frozen=True)
class Shutdown:
    pass


@dataclass(frozen=True)
class ListToolboxes:
    request_id: int


# -- events (kernel -> GUI) ---------------------------------------------------


@dataclass(frozen=True)
class Stdout:
    request_id: int
    text: str


@dataclass(frozen=True)
class Diagnostics:
    request_id: int
    items: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class VariableInfo:
    """Summary of one workspace variable. Never carries the full array."""

    name: str
    cls: str  # e.g. "double"
    size: tuple[int, ...]  # e.g. (1, 1)
    preview: str  # short text, e.g. "5"


@dataclass(frozen=True)
class WorkspaceSummary:
    request_id: int
    variables: tuple[VariableInfo, ...]  # sorted by name


ExecStatus = Literal["ok", "error", "cancelled"]


@dataclass(frozen=True)
class ExecutionFinished:
    request_id: int
    status: ExecStatus


@dataclass(frozen=True)
class ToolboxFunction:
    """One function listed in a toolbox. Plain data (no callable)."""

    name: str
    summary: str  # one line
    signature: str = ""  # e.g. "inv(A)"


@dataclass(frozen=True)
class ToolboxInfo:
    name: str  # identifier, e.g. "mathematics"
    display_name: str
    functions: tuple[ToolboxFunction, ...]


@dataclass(frozen=True)
class ToolboxList:
    request_id: int
    toolboxes: tuple[ToolboxInfo, ...]


@dataclass(frozen=True)
class FigureUpdate:
    """Full snapshot of one figure (the GUI creates or replaces its window)."""

    request_id: int
    figure: FigureSpec


@dataclass(frozen=True)
class FigureClosed:
    """The script closed figure ``number`` (the GUI closes its window)."""

    request_id: int
    number: int


@dataclass(frozen=True)
class OpenModel:
    """The script asked to open a simulation model (``open_system``) in the editor."""

    request_id: int
    path: str


@dataclass(frozen=True)
class FolderChanged:
    """The script changed the working folder (``cd``); the Current Folder panel follows."""

    request_id: int
    path: str


Event = (
    Stdout | Diagnostics | WorkspaceSummary | ExecutionFinished | ToolboxList
    | FigureUpdate | FigureClosed | OpenModel | FolderChanged
)
