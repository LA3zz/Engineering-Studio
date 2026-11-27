"""Custom themes (G7): colour parsing, palette validation, contrast checks, JSON.

Pure Python, no Qt. The editor dialog (``theme_dialog``) and the main window use this module;
settings hold the result of ``CustomThemes.to_data()`` under the key ``custom_themes``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from engstudio.gui.theme import THEMES, Palette, contrast_ratio, get_palette

__all__ = [
    "ROLE_LABELS", "ROLES", "MIN_CONTRAST", "MAX_NAME", "MAX_THEMES", "CONTRAST_PAIRS",
    "ContrastIssue", "ThemeFile", "CustomThemes", "parse_hex", "make_palette",
    "contrast_issues", "role_issues", "readable_text_colour", "validate_name",
    "palette_to_json", "palette_from_json",
]

ROLE_LABELS: dict[str, str] = {
    "window": "Window background",
    "base": "Editor and list background",
    "alt_base": "Alternate rows",
    "text": "Text",
    "text_dim": "Dim text",
    "border": "Borders",
    "accent": "Accent",
    "accent_text": "Text on accent",
    "button": "Buttons and inactive tabs",
    "hover": "Hover",
    "toolbar": "Toolbars and menu bar",
    "selection": "Selection",
}
ROLES: tuple[str, ...] = tuple(ROLE_LABELS)

MIN_CONTRAST = 4.5  # WCAG AA for normal text
MAX_NAME = 40
MAX_THEMES = 50
FORMAT = "engstudio-theme"
VERSION = 1

# (foreground role, background role) pairs that the stylesheet actually draws together.
CONTRAST_PAIRS: tuple[tuple[str, str], ...] = (
    ("text", "base"), ("text", "alt_base"), ("text", "window"), ("text", "toolbar"),
    ("text", "selection"), ("text", "hover"), ("text_dim", "base"), ("text_dim", "window"),
    ("text_dim", "toolbar"), ("text_dim", "button"), ("accent_text", "accent"),
)

_HEX = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def parse_hex(text: object) -> str:
    """Normalise ``#rgb``, ``rgb``, ``#rrggbb`` or ``rrggbb`` to lowercase ``#rrggbb``."""
    if not isinstance(text, str):
        raise ValueError(f"colour must be text like '#rrggbb', got {type(text).__name__}")
    m = _HEX.fullmatch(text.strip())
    if m is None:
        raise ValueError(f"invalid colour {text!r}; expected #rrggbb")
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def make_palette(name: str, colors: Mapping[str, object], base: Palette) -> Palette:
    """Palette named ``name``; roles missing from ``colors`` come from ``base``."""
    if not isinstance(colors, Mapping):
        raise ValueError("colors must be a mapping of role to #rrggbb")
    unknown = sorted(set(colors) - set(ROLES))
    if unknown:
        raise ValueError(f"unknown colour role(s): {', '.join(map(str, unknown))}")
    values = {}
    for role in ROLES:
        try:
            values[role] = parse_hex(colors.get(role, getattr(base, role)))
        except ValueError as exc:
            raise ValueError(f"{role}: {exc}") from None
    return Palette(name=name, **values)


@dataclass(frozen=True)
class ContrastIssue:
    fg: str
    bg: str
    ratio: float


def contrast_issues(palette: Palette, minimum: float = MIN_CONTRAST) -> list[ContrastIssue]:
    """Foreground/background pairs of ``CONTRAST_PAIRS`` whose WCAG ratio is below ``minimum``."""
    out = []
    for fg, bg in CONTRAST_PAIRS:
        ratio = contrast_ratio(getattr(palette, fg), getattr(palette, bg))
        if ratio < minimum:
            out.append(ContrastIssue(fg, bg, ratio))
    return out


def role_issues(issues: Iterable[ContrastIssue], role: str) -> str:
    """Text for the warning column of ``role`` ('' when it takes part in no failing pair)."""
    return "; ".join(f"{i.fg} on {i.bg} {i.ratio:.1f}:1" for i in issues if role in (i.fg, i.bg))


def readable_text_colour(background: str) -> str:
    """Black or white, whichever contrasts more with ``background`` (a ``#rrggbb`` colour)."""
    bg = parse_hex(background)
    return "#000000" if contrast_ratio("#000000", bg) >= contrast_ratio("#ffffff", bg) \
        else "#ffffff"


def validate_name(name: object, existing: Iterable[str] = ()) -> str:
    """Clean and check a custom theme name; returns the cleaned name or raises ValueError."""
    if not isinstance(name, str):
        raise ValueError("theme name must be text")
    clean = " ".join(name.split())
    if not clean:
        raise ValueError("enter a name for the theme")
    if len(clean) > MAX_NAME:
        raise ValueError(f"theme name is longer than {MAX_NAME} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in clean):
        raise ValueError("theme name contains control characters")
    if clean.casefold() in {t.casefold() for t in THEMES}:
        raise ValueError(f"{clean!r} is a built-in theme name; choose another")
    for other in existing:
        if other != clean and other.casefold() == clean.casefold():
            raise ValueError(f"name clashes with the existing theme {other!r}")
    return clean


class CustomThemes:
    """Named custom palettes, each with the built-in theme ('light'/'dark') it is based on."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[Palette, str]] = {}
        self.errors: list[str] = []  # problems found while loading stored data

    def names(self) -> list[str]:
        return list(self._items)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._items

    def __len__(self) -> int:
        return len(self._items)

    def get(self, name: str) -> Palette:
        if name not in self:
            raise ValueError(f"unknown custom theme {name!r}")
        return self._items[name][0]

    def base_of(self, name: str) -> str:
        if name not in self:
            raise ValueError(f"unknown custom theme {name!r}")
        return self._items[name][1]

    def resolve(self, name: str) -> Palette:
        """Palette of a custom theme, else of a built-in one (ValueError if neither)."""
        return self.get(name) if name in self else get_palette(name)

    def set(self, name: str, palette: Palette, base: str) -> str:
        """Add or replace a theme; returns the cleaned name. ValueError if invalid."""
        clean = validate_name(name, self._items)
        if not isinstance(base, str) or base not in THEMES:
            raise ValueError(f"base must be one of {sorted(THEMES)}")
        if clean not in self._items and len(self._items) >= MAX_THEMES:
            raise ValueError(f"at most {MAX_THEMES} custom themes are supported")
        colors = {role: getattr(palette, role) for role in ROLES}
        self._items[clean] = (make_palette(clean, colors, get_palette(base)), base)
        return clean

    def delete(self, name: str) -> str:
        """Remove a theme; returns its base theme name."""
        base = self.base_of(name)
        del self._items[name]
        return base

    def to_data(self) -> dict[str, dict[str, object]]:
        return {
            name: {"base": base, "colors": {r: getattr(p, r) for r in ROLES}}
            for name, (p, base) in self._items.items()
        }

    @classmethod
    def from_data(cls, data: object) -> CustomThemes:
        """Rebuild from stored data; invalid entries are skipped and listed in ``errors``."""
        themes = cls()
        if data is None:
            return themes
        if not isinstance(data, dict):
            themes.errors.append("custom_themes is not an object; ignored")
            return themes
        for name, entry in data.items():
            try:
                if not isinstance(entry, dict):
                    raise ValueError("entry is not an object")
                base = entry.get("base", "light")
                if not isinstance(base, str) or base not in THEMES:
                    raise ValueError(f"invalid base {base!r}")
                colors = entry.get("colors", {})
                themes.set(str(name), make_palette(str(name), colors, get_palette(base)), base)
            except ValueError as exc:
                themes.errors.append(f"{name!r}: {exc}")
        return themes


@dataclass(frozen=True)
class ThemeFile:
    name: str
    base: str
    palette: Palette


def palette_to_json(palette: Palette, base: str) -> str:
    if base not in THEMES:
        raise ValueError(f"base must be one of {sorted(THEMES)}")
    data = {"format": FORMAT, "version": VERSION, "name": palette.name, "base": base,
            "colors": {r: getattr(palette, r) for r in ROLES}}
    return json.dumps(data, indent=2)


def palette_from_json(text: str) -> ThemeFile:
    """Parse a theme file. Missing colours fall back to the base theme; ValueError if bad."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"not valid JSON: {exc}") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("not an Engineering Studio theme file")
    version = data.get("version")
    if type(version) is not int or version != VERSION:
        raise ValueError(f"unsupported theme file version {version!r}")
    base = data.get("base", "light")
    if not isinstance(base, str) or base not in THEMES:
        raise ValueError(f"invalid base {base!r}; expected one of {sorted(THEMES)}")
    name = data.get("name", "Imported")
    if not isinstance(name, str):
        raise ValueError("theme name must be text")
    clean = " ".join(name.split()) or "Imported"
    colors = data.get("colors")
    if not isinstance(colors, dict):
        raise ValueError("theme file has no 'colors' object")
    return ThemeFile(clean, base, make_palette(clean, colors, get_palette(base)))
