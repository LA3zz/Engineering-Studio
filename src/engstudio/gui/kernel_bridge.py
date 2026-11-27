"""Qt adapter for a KernelClient: re-emits kernel events as a Qt signal and tracks whether
code is running.

If the client delivers events from another thread (the in-process worker or a future process
kernel), Qt queues the signal to receivers living in the GUI thread, so widgets never run on the
wrong thread. ``running_changed(bool)`` fires when the first request starts and when the last
one finishes; ``cancel_running()`` cancels every request that has not finished.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import ExecutionFinished

__all__ = ["KernelBridge"]


class KernelBridge(QObject):
    event = Signal(object)  # an engstudio.app.kernel.protocol event
    running_changed = Signal(bool)

    def __init__(self, client: KernelClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client = client
        self._pending: set[int] = set()
        self._executing = False
        self._finished_early: set[int] = set()
        self._unsubscribe = client.subscribe(self.event.emit)
        self.event.connect(self._track)

    @property
    def running(self) -> bool:
        """True while at least one request has not finished."""
        return bool(self._pending)

    def execute(self, code: str, file: str | None = None) -> int:
        """Run ``code``; ``file`` names its source so diagnostics can point back to it."""
        self._executing = True
        self._finished_early.clear()
        try:
            rid = self._client.execute(code) if file is None else self._client.execute(code, file)
        finally:
            self._executing = False
        if rid in self._finished_early:  # a synchronous client finished before returning
            self._finished_early.discard(rid)
        else:
            self._add_pending(rid)
        return rid

    def list_toolboxes(self) -> int:
        return self._client.list_toolboxes()

    def cancel(self, request_id: int) -> None:
        self._client.cancel(request_id)

    def figure_closed(self, number: int) -> None:
        """Tell the kernel the user closed figure window ``number``."""
        self._client.figure_closed(number)

    def cancel_running(self) -> None:
        for request_id in sorted(self._pending):
            self._client.cancel(request_id)

    def shutdown(self) -> None:
        """Stop forwarding events and shut the client down (idempotent)."""
        self._unsubscribe()
        self._pending.clear()
        self._client.shutdown()

    # -- internals -------------------------------------------------------------
    def _track(self, event: object) -> None:
        if not isinstance(event, ExecutionFinished):
            return
        if self._executing:
            self._finished_early.add(event.request_id)
        elif event.request_id in self._pending:
            self._pending.discard(event.request_id)
            if not self._pending:
                self.running_changed.emit(False)

    def _add_pending(self, request_id: int) -> None:
        was_idle = not self._pending
        self._pending.add(request_id)
        if was_idle:
            self.running_changed.emit(True)
