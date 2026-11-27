"""Abstract kernel client: the only interface the GUI uses to run code."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from engstudio.app.kernel.protocol import Event
from engstudio.core.errors import NotSupportedError

EventHandler = Callable[[Event], None]


class KernelClient(ABC):
    """Send requests, receive events through subscribed handlers.

    Contract: for every ``execute`` the handlers receive zero or more ``Stdout`` /
    ``Diagnostics`` events, then one ``WorkspaceSummary``, then exactly one
    ``ExecutionFinished`` (always last). Implementations may deliver events synchronously
    (in-process stub) or from another thread (process kernel); GUI adapters must marshal
    to the GUI thread themselves.
    """

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        """Register ``handler``; returns a function that unsubscribes it."""
        self._handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsubscribe

    def _emit(self, event: Event) -> None:
        # Exceptions raised by a handler propagate: a buggy listener must not be hidden.
        for handler in list(self._handlers):
            handler(event)

    @abstractmethod
    def execute(self, code: str, file: str | None = None) -> int:
        """Run ``code``; returns the request id used in all resulting events.

        ``file`` names the source (used as the file of diagnostic locations).
        """

    @abstractmethod
    def cancel(self, request_id: int) -> None:
        """Request cancellation (no effect if the request already finished)."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release resources; further ``execute`` calls raise ``EngStudioError``."""

    def figure_closed(self, number: int) -> None:
        """The user closed figure window ``number``; the kernel forgets that figure (a later
        ``figure(number)`` starts empty). Default: nothing to forget."""
        return None

    def list_toolboxes(self) -> int:
        """Request the toolbox catalogue; answered by one ``ToolboxList`` event.

        Not abstract: clients without a catalogue raise ``NotSupportedError``.
        """
        raise NotSupportedError("this kernel client does not provide a toolbox list")
