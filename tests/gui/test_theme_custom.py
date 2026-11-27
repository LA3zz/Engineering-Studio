"""Custom theme logic (G7). Pure Python: no Qt, no dialogs."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from engstudio.gui import theme_custom as tc
from engstudio.gui.settings import UiSettings
from engstudio.gui.theme import DARK, LIGHT, Palette, contrast_ratio


def test_roles_match_palette_fields():
    fields = [f for f in Palette.__dataclass_fields__ if f != "name"]
    assert list(tc.ROLES) == fields
    assert set(tc.ROLE_LABELS) == set(fields)
    assert all(a in fields and b in fields for a, b in tc.CONTRAST_PAIRS)


def test_module_has_no_qt_import():
    tree = ast.parse(Path(tc.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith("PySide6") for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("PySide6")


@pytest.mark.parametrize("text,expected", [
    ("#FF8000", "#ff8000"), ("ff8000", "#ff8000"), ("#f80", "#ff8800"), ("  #ABC ", "#aabbcc"),
])
def test_parse_hex_ok(text, expected):
    assert tc.parse_hex(text) == expected


@pytest.mark.parametrize("bad", ["", "#12", "#12345", "#1234567", "#gggggg", "red", "# fff",
                                 None, 255, "#ff00ff\n#"])
def test_parse_hex_rejects(bad):
    with pytest.raises(ValueError):
        tc.parse_hex(bad)


def test_make_palette_fills_from_base():
    p = tc.make_palette("mine", {"accent": "#F00"}, DARK)
    assert p.name == "mine" and p.accent == "#ff0000"
    assert p.window == DARK.window and p.text == DARK.text


def test_make_palette_errors():
    with pytest.raises(ValueError, match="unknown colour role"):
        tc.make_palette("x", {"nope": "#000000"}, LIGHT)
    with pytest.raises(ValueError, match="accent"):
        tc.make_palette("x", {"accent": "zzz"}, LIGHT)
    with pytest.raises(ValueError):
        tc.make_palette("x", ["#000000"], LIGHT)


def test_builtin_themes_have_no_contrast_issues():
    assert tc.contrast_issues(LIGHT) == []
    assert tc.contrast_issues(DARK) == []


def test_contrast_issue_detected_with_known_ratio():
    # Black text on a black editor background: ratio is exactly 1:1 (WCAG).
    p = tc.make_palette("bad", {"text": "#000000", "base": "#000000"}, LIGHT)
    issues = tc.contrast_issues(p)
    hit = [i for i in issues if (i.fg, i.bg) == ("text", "base")]
    assert len(hit) == 1 and hit[0].ratio == pytest.approx(1.0)
    assert "text on base 1.0:1" in tc.role_issues(issues, "base")
    assert tc.role_issues(issues, "border") == ""


def test_contrast_minimum_is_a_parameter():
    p = tc.make_palette("grey", {"text": "#777777", "base": "#ffffff"}, LIGHT)
    ratio = contrast_ratio("#777777", "#ffffff")  # about 4.48: just below AA
    assert ratio < 4.5
    assert any((i.fg, i.bg) == ("text", "base") for i in tc.contrast_issues(p))
    assert not any((i.fg, i.bg) == ("text", "base") for i in tc.contrast_issues(p, 4.0))


def test_readable_text_colour():
    assert tc.readable_text_colour("#000000") == "#ffffff"
    assert tc.readable_text_colour("#ffffff") == "#000000"
    assert tc.readable_text_colour("#0b5cad") == "#ffffff"


@pytest.mark.parametrize("name,clean", [("Night", "Night"), ("  My   theme ", "My theme"),
                                        ("Tème ✓", "Tème ✓")])
def test_validate_name_ok(name, clean):
    assert tc.validate_name(name) == clean


@pytest.mark.parametrize("bad", ["", "   ", "Light", "DARK", "x" * 41, "a\x00b", None, 5])
def test_validate_name_rejects(bad):
    with pytest.raises(ValueError):
        tc.validate_name(bad)


def test_validate_name_case_clash():
    with pytest.raises(ValueError, match="clashes"):
        tc.validate_name("night", existing=["Night"])
    assert tc.validate_name("Night", existing=["Night"]) == "Night"


def _themes():
    t = tc.CustomThemes()
    t.set("Night", tc.make_palette("Night", {"accent": "#ff8800"}, DARK), "dark")
    t.set("Paper", tc.make_palette("Paper", {}, LIGHT), "light")
    return t


def test_custom_themes_basic_operations():
    t = _themes()
    assert t.names() == ["Night", "Paper"] and len(t) == 2
    assert "Night" in t and "Light" not in t and 5 not in t
    assert t.get("Night").accent == "#ff8800" and t.get("Night").name == "Night"
    assert t.base_of("Night") == "dark"
    assert t.resolve("Night") is t.get("Night")
    assert t.resolve("dark") is DARK
    with pytest.raises(ValueError):
        t.resolve("nope")
    with pytest.raises(ValueError):
        t.get("nope")
    assert t.delete("Night") == "dark" and "Night" not in t
    with pytest.raises(ValueError):
        t.delete("Night")


def test_set_renames_palette_and_validates():
    t = tc.CustomThemes()
    assert t.set("  A  b ", tc.make_palette("zzz", {}, LIGHT), "light") == "A b"
    assert t.get("A b").name == "A b"
    with pytest.raises(ValueError):
        t.set("Dark", LIGHT, "light")
    with pytest.raises(ValueError):
        t.set("X", LIGHT, "solarized")
    assert t.names() == ["A b"]


def test_set_replaces_same_name_and_limits_count():
    t = tc.CustomThemes()
    for i in range(tc.MAX_THEMES):
        t.set(f"t{i}", LIGHT, "light")
    with pytest.raises(ValueError, match="at most"):
        t.set("one more", LIGHT, "light")
    t.set("t0", DARK, "dark")  # replacing an existing name is allowed
    assert t.base_of("t0") == "dark" and len(t) == tc.MAX_THEMES


def test_to_data_from_data_round_trip():
    t = _themes()
    data = t.to_data()
    assert set(data["Night"]) == {"base", "colors"}
    assert set(data["Night"]["colors"]) == set(tc.ROLES)
    back = tc.CustomThemes.from_data(json.loads(json.dumps(data)))
    assert back.errors == [] and back.names() == t.names()
    for n in t.names():
        assert back.get(n) == t.get(n) and back.base_of(n) == t.base_of(n)


def test_from_data_skips_bad_entries():
    good = _themes().to_data()["Night"]
    data = {"Good": good, "Light": good, "Notdict": 5, "BadBase": {"base": "x", "colors": {}},
            "BadColor": {"base": "dark", "colors": {"text": "zzz"}},
            "BadRole": {"colors": {"nope": "#000000"}}, "Colors": {"colors": []}}
    t = tc.CustomThemes.from_data(data)
    assert t.names() == ["Good"]
    assert len(t.errors) == 6


@pytest.mark.parametrize("data", [None, {}])
def test_from_data_empty(data):
    t = tc.CustomThemes.from_data(data)
    assert len(t) == 0 and t.errors == []


@pytest.mark.parametrize("data", [5, "x", ["a"]])
def test_from_data_wrong_type(data):
    t = tc.CustomThemes.from_data(data)
    assert len(t) == 0 and len(t.errors) == 1


def test_json_round_trip():
    p = tc.make_palette("Night", {"accent": "#ff8800"}, DARK)
    f = tc.palette_from_json(tc.palette_to_json(p, "dark"))
    assert f.name == "Night" and f.base == "dark" and f.palette == p


def test_json_missing_colours_use_base():
    text = json.dumps({"format": "engstudio-theme", "version": 1, "base": "dark",
                       "colors": {"accent": "#123456"}})
    f = tc.palette_from_json(text)
    assert f.name == "Imported" and f.palette.accent == "#123456"
    assert f.palette.window == DARK.window


@pytest.mark.parametrize("text", [
    "not json", "[]", "{}", '{"format": "other", "version": 1, "colors": {}}',
    '{"format": "engstudio-theme", "version": 2, "colors": {}}',
    '{"format": "engstudio-theme", "version": true, "colors": {}}',
    '{"format": "engstudio-theme", "version": 1}',
    '{"format": "engstudio-theme", "version": 1, "colors": {"text": "zzz"}}',
    '{"format": "engstudio-theme", "version": 1, "base": "x", "colors": {}}',
    '{"format": "engstudio-theme", "version": 1, "name": 5, "colors": {}}',
    "[" * 100000,
])
def test_json_rejects_bad_files(text):
    with pytest.raises(ValueError):
        tc.palette_from_json(text)


def test_to_json_rejects_bad_base():
    with pytest.raises(ValueError):
        tc.palette_to_json(LIGHT, "x")


def test_persist_through_ui_settings(tmp_path):
    path = tmp_path / "ui.json"
    s = UiSettings(path)
    s.set("custom_themes", _themes().to_data())
    s.set("theme", "Night")
    assert s.save()
    s2 = UiSettings(path)
    t = tc.CustomThemes.from_data(s2.get("custom_themes"))
    assert s2.get("theme") == "Night" and t.errors == []
    assert t.get("Night").accent == "#ff8800" and t.base_of("Paper") == "light"
