"""Small JSON store for UI preferences (theme, window geometry, dock layout).

Interim implementation: ARCHITECTURE.md plans SQLite (``app.db``) for app data; this can be
swapped for it later behind the same ``get``/``set``/``save`` interface.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path

__all__ = ["UiSettings", "default_settings_path"]


def default_settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "EngineeringStudio" / "ui_settings.json"


class UiSettings:
    """Key/value store. ``path=None`` keeps everything in memory (tests, smoke runs)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._data: dict[str, object] = {}
        self.load_error: str | None = None
        self.save_error: str | None = None
        self.load()

    def load(self) -> None:
        self._data = {}
        self.load_error = None
        if self._path is None or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("settings file root must be a JSON object")
            self._data = data
        except (OSError, ValueError) as exc:  # includes JSONDecodeError, UnicodeDecodeError
            self.load_error = str(exc)

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def get_bytes(self, key: str) -> bytes | None:
        v = self._data.get(key)
        if not isinstance(v, str):
            return None
        try:
            return base64.b64decode(v.encode("ascii"), validate=True)
        except (binascii.Error, ValueError):
            return None

    def set_bytes(self, key: str, value: bytes) -> None:
        self._data[key] = base64.b64encode(value).decode("ascii")

    def save(self) -> bool:
        """Atomic write (UTF-8, no BOM). Returns False and sets ``save_error`` on failure."""
        self.save_error = None
        if self._path is None:
            return True
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_name(self._path.name + ".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
            return True
        except OSError as exc:
            self.save_error = str(exc)
            return False
