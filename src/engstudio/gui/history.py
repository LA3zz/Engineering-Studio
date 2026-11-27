"""Command history with shell-style up/down navigation. Qt-free."""

from __future__ import annotations

from collections.abc import Iterable


class CommandHistory:
    """Keeps entered commands. ``previous``/``next`` walk the list; the text being typed
    before navigation started (the *draft*) is restored when walking past the newest entry."""

    def __init__(self, items: Iterable[str] = (), max_size: int = 1000) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max = max_size
        self._items: list[str] = [s for s in items if isinstance(s, str) and s.strip()]
        del self._items[: max(0, len(self._items) - max_size)]
        self._index = len(self._items)
        self._draft = ""

    def items(self) -> list[str]:
        return list(self._items)

    def add(self, entry: str) -> None:
        """Record an entry (blank entries and immediate repeats are ignored); resets navigation."""
        if entry.strip() and not (self._items and self._items[-1] == entry):
            self._items.append(entry)
            del self._items[: max(0, len(self._items) - self._max)]
        self.reset()

    def reset(self) -> None:
        self._index = len(self._items)
        self._draft = ""

    def previous(self, current: str = "") -> str | None:
        """Older entry, or None if there is none (already at the oldest / empty history)."""
        if not self._items or self._index == 0:
            return None
        if self._index == len(self._items):
            self._draft = current
        self._index -= 1
        return self._items[self._index]

    def next(self) -> str | None:
        """Newer entry (or the saved draft past the newest), or None if not navigating."""
        if self._index >= len(self._items):
            return None
        self._index += 1
        return self._draft if self._index == len(self._items) else self._items[self._index]
