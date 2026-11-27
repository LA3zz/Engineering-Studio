"""UiSettings tests (no Qt needed)."""

from __future__ import annotations

from engstudio.gui.settings import UiSettings


def test_roundtrip(tmp_path):
    p = tmp_path / "sub" / "ui.json"
    s = UiSettings(p)
    assert s.get("theme") is None and s.get("theme", "light") == "light"
    s.set("theme", "dark")
    s.set_bytes("window_state", b"\x00\xff\x10abc")
    assert s.save() is True
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # UTF-8 without BOM
    s2 = UiSettings(p)
    assert s2.get("theme") == "dark"
    assert s2.get_bytes("window_state") == b"\x00\xff\x10abc"
    assert s2.load_error is None


def test_corrupt_file_is_ignored(tmp_path):
    p = tmp_path / "ui.json"
    p.write_text("{not json", encoding="utf-8")
    s = UiSettings(p)
    assert s.load_error is not None and s.get("theme") is None
    p.write_text("[1, 2]", encoding="utf-8")
    assert UiSettings(p).load_error is not None
    p.write_bytes(b"\xff\xfe\x00bad")
    assert UiSettings(p).load_error is not None


def test_bom_file_is_read(tmp_path):
    p = tmp_path / "ui.json"
    p.write_bytes(b"\xef\xbb\xbf" + b'{"theme": "dark"}')
    assert UiSettings(p).get("theme") == "dark"


def test_bad_bytes_value(tmp_path):
    s = UiSettings(None)
    s.set("window_state", "###not base64###")
    assert s.get_bytes("window_state") is None
    s.set("window_state", 5)
    assert s.get_bytes("window_state") is None
    assert s.get_bytes("missing") is None


def test_memory_only_never_writes(tmp_path):
    s = UiSettings(None)
    s.set("a", 1)
    assert s.save() is True


def test_save_failure_reported(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    s = UiSettings(blocker / "ui.json")  # parent is a file -> mkdir fails
    s.set("a", 1)
    assert s.save() is False and s.save_error
