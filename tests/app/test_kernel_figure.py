"""FigureUpdate kernel event (G5.1)."""

from __future__ import annotations

import dataclasses
import pickle
import typing

import pytest

from engstudio.app.kernel.protocol import Event, FigureUpdate
from engstudio.plotting.model import AxesSpec, FigureSpec, SeriesSpec


def make() -> FigureUpdate:
    fig = FigureSpec(axes=(AxesSpec(series=(SeriesSpec("line", [0, 1], [0, 1]),)),))
    return FigureUpdate(7, fig)


def test_event_carries_request_id_and_figure():
    ev = make()
    assert ev.request_id == 7 and isinstance(ev.figure, FigureSpec)


def test_event_is_in_the_event_union():
    assert FigureUpdate in typing.get_args(Event)


def test_event_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        make().request_id = 1  # type: ignore[misc]


def test_event_survives_a_pipe_round_trip():
    ev = make()
    assert pickle.loads(pickle.dumps(ev)) == ev
