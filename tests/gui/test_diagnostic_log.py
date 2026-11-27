"""Diagnostic history for the Diagnostics panel (pure logic, no Qt)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from engstudio.app.kernel.protocol import Diagnostics
from engstudio.core.diagnostics import Diagnostic, SourceLoc
from engstudio.gui.diagnostic_log import (
    SEVERITIES,
    SEVERITY_COLORS,
    DiagnosticLog,
    format_location,
    location_parts,
)
from engstudio.gui.theme import THEMES, contrast_ratio


def diag(sev="error", code="E1", msg="m", loc=None):
    return Diagnostic(sev, code, msg, loc)


def ev(rid, *items):
    return Diagnostics(rid, tuple(items))


# -- locations -----------------------------------------------------------------------
def test_location_parts_of_the_real_source_loc():
    assert location_parts(None) == (None, None, None)
    assert location_parts(SourceLoc(None, 3, 5)) == (None, 3, 5)
    assert location_parts(SourceLoc("dir/a.m", 2, 7)) == ("dir/a.m", 2, 7)


def test_location_parts_reads_by_position_not_by_name():
    @dataclass(frozen=True)
    class Other:
        path: str
        row: int
        column: int

    assert location_parts(Other("f.m", 4, 9)) == ("f.m", 4, 9)


def test_location_parts_tolerates_other_shapes():
    class Plain:
        file = "x.m"
        line = 8
        col = 2

    @dataclass(frozen=True)
    class Short:
        file: str
        line: int

    assert location_parts(Plain()) == ("x.m", 8, 2)
    assert location_parts(Short("s.m", 6)) == ("s.m", 6, None)
    assert location_parts(object()) == (None, None, None)

    @dataclass(frozen=True)
    class Bad:
        file: object
        line: object
        col: object

    assert location_parts(Bad(None, "3", 2.5)) == (None, None, None)


def test_format_location():
    assert format_location(None, None, None) == ""
    assert format_location(None, 3, 5) == "line 3, col 5"
    assert format_location(None, 3, None) == "line 3"
    assert format_location("dir/a.m", 2, 1) == "a.m: line 2, col 1"


# -- the log -------------------------------------------------------------------------
def test_add_records_fields_order_and_request_ids():
    log = DiagnosticLog()
    assert log.add(ev(7, diag("error", "E1", "bad", SourceLoc(None, 2, 3)),
                      diag("warning", "W1", "careful"))) == 2
    assert log.add(ev(8, diag("info", "I1", "fyi"))) == 1
    a, b, c = log.entries
    assert (a.seq, a.request_id, a.severity, a.code, a.message) == (1, 7, "error", "E1", "bad")
    assert (a.file, a.line, a.col, a.location_text) == (None, 2, 3, "line 2, col 3")
    assert (b.seq, b.line, b.location_text) == (2, None, "")
    assert (c.seq, c.request_id, c.severity) == (3, 8, "info")


def test_empty_event_adds_nothing():
    log = DiagnosticLog()
    assert log.add(ev(1)) == 0 and log.entries == ()


def test_unknown_severity_is_stored_as_info():
    log = DiagnosticLog()
    odd = SimpleNamespace(severity="fatal", code="X", message="m", location=None)
    log.add(ev(1, odd))
    assert log.entries[0].severity == "info"


def test_cap_keeps_the_newest_and_counts_dropped():
    log = DiagnosticLog(cap=3)
    for i in range(5):
        log.add(ev(i, diag(code=f"E{i}")))
    assert [e.code for e in log.entries] == ["E2", "E3", "E4"]
    assert log.dropped == 2
    assert [e.seq for e in log.entries] == [3, 4, 5]


def test_cap_applies_within_one_event():
    log = DiagnosticLog(cap=2)
    log.add(ev(1, *(diag(code=f"E{i}") for i in range(4))))
    assert [e.code for e in log.entries] == ["E2", "E3"] and log.dropped == 2


def test_invalid_cap_is_rejected():
    for bad in (0, -1, True, 2.5, "3"):
        with pytest.raises(ValueError):
            DiagnosticLog(cap=bad)  # type: ignore[arg-type]


def test_clear_empties_but_sequence_keeps_growing():
    log = DiagnosticLog(cap=1)
    log.add(ev(1, diag(), diag()))
    log.clear()
    assert log.entries == () and log.dropped == 0
    log.add(ev(2, diag()))
    assert log.entries[0].seq == 3


def test_counts_and_visible_filter_keep_order():
    log = DiagnosticLog()
    log.add(ev(1, diag("error", "A"), diag("warning", "B"), diag("error", "C"),
               diag("info", "D")))
    assert log.counts() == {"error": 2, "warning": 1, "info": 1}
    assert [e.code for e in log.visible({"error"})] == ["A", "C"]
    assert [e.code for e in log.visible({"error", "info"})] == ["A", "C", "D"]
    assert log.visible(set()) == []
    assert DiagnosticLog().counts() == {"error": 0, "warning": 0, "info": 0}


# -- colours -------------------------------------------------------------------------
def test_severity_colours_cover_every_theme_and_are_readable():
    assert set(SEVERITY_COLORS) == set(THEMES)
    for theme, colours in SEVERITY_COLORS.items():
        assert set(colours) == set(SEVERITIES)
        for sev, colour in colours.items():
            for bg in (THEMES[theme].base, THEMES[theme].alt_base):
                ratio = contrast_ratio(colour, bg)
                assert ratio >= 4.5, f"{theme}/{sev} {colour} on {bg}: {ratio:.2f}"
