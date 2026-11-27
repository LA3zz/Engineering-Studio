"""ListToolboxes / ToolboxList on the stub kernel and the abstract client (G3.2)."""

from __future__ import annotations

import dataclasses

import pytest

from engstudio.app.kernel.client import KernelClient
from engstudio.app.kernel.protocol import ToolboxFunction, ToolboxInfo, ToolboxList
from engstudio.app.kernel.stub import SAMPLE_TOOLBOXES, StubKernelClient
from engstudio.core.errors import EngStudioError, NotSupportedError


def collect(client):
    got = []
    client.subscribe(got.append)
    return got


def test_stub_emits_one_toolbox_list():
    client = StubKernelClient()
    got = collect(client)
    rid = client.list_toolboxes()
    assert len(got) == 1
    ev = got[0]
    assert isinstance(ev, ToolboxList)
    assert ev.request_id == rid
    assert ev.toolboxes == SAMPLE_TOOLBOXES


def test_sample_catalogue_is_well_formed():
    names = [tb.name for tb in SAMPLE_TOOLBOXES]
    assert names and len(names) == len(set(names))
    for tb in SAMPLE_TOOLBOXES:
        assert isinstance(tb, ToolboxInfo) and tb.display_name and tb.functions
        fnames = [f.name for f in tb.functions]
        assert len(fnames) == len(set(fnames))
        assert all(isinstance(f, ToolboxFunction) and f.name and f.summary for f in tb.functions)


def test_request_ids_are_shared_with_execute():
    client = StubKernelClient()
    first = client.execute("x = 1;")
    second = client.list_toolboxes()
    third = client.list_toolboxes()
    assert first < second < third


def test_list_after_shutdown_raises():
    client = StubKernelClient()
    client.shutdown()
    with pytest.raises(EngStudioError):
        client.list_toolboxes()


def test_messages_are_immutable():
    ev = ToolboxList(1, SAMPLE_TOOLBOXES)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.request_id = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        SAMPLE_TOOLBOXES[0].name = "x"  # type: ignore[misc]


def test_base_client_does_not_support_toolboxes():
    class Minimal(KernelClient):
        def execute(self, code: str) -> int:
            return 0

        def cancel(self, request_id: int) -> None:
            return None

        def shutdown(self) -> None:
            return None

    with pytest.raises(NotSupportedError):
        Minimal().list_toolboxes()
