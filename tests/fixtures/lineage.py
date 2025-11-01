from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import pytest
from tests.helpers.fixtures import fixture


@dataclass(slots=True)
class CapturedLineage:
    """Record OpenLineage events captured during a test run."""

    events: list[Any]


@fixture()
def capture_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[CapturedLineage]:
    """Stub the OpenLineage client and capture emitted events."""

    captured: list[Any] = []
    if "duckdb" not in sys.modules:
        sys.modules["duckdb"] = ModuleType("duckdb")

    lineage = importlib.import_module("hotpass.lineage")

    class _StubClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.events = captured

        def emit(self, event: Any) -> None:
            captured.append(event)

    class _StubDataset:
        def __init__(self, *, namespace: str, name: str, facets: Mapping[str, object]) -> None:
            self.namespace = namespace
            self.name = name
            self.facets = dict(facets)

    class _StubRun:
        def __init__(
            self,
            *,
            runId: str,
            facets: Mapping[str, object] | None = None,
        ) -> None:  # noqa: N803 - OpenLineage naming
            self.runId = runId
            self.facets = dict(facets or {})

    class _StubJob:
        def __init__(
            self,
            *,
            namespace: str,
            name: str,
            facets: Mapping[str, object] | None = None,
        ) -> None:
            self.namespace = namespace
            self.name = name
            self.facets = dict(facets or {})

    class _StubRunEvent:
        def __init__(
            self,
            *,
            eventTime: str,
            producer: str,
            eventType: str,
            run: _StubRun,
            job: _StubJob,
            inputs: list[_StubDataset],
            outputs: list[_StubDataset],
            **_: Any,
        ) -> None:
            self.eventTime = eventTime
            self.producer = producer
            self.eventType = eventType
            self.run = run
            self.job = job
            self.inputs = list(inputs)
            self.outputs = list(outputs)

    class _StubRunState:
        START = "START"
        COMPLETE = "COMPLETE"
        FAIL = "FAIL"

    monkeypatch.setattr(lineage, "OpenLineageClient", _StubClient)
    monkeypatch.setattr(lineage, "set_lineage_producer", lambda *_: None)
    monkeypatch.setattr(lineage, "InputDataset", _StubDataset)
    monkeypatch.setattr(lineage, "OutputDataset", _StubDataset)
    monkeypatch.setattr(lineage, "Run", _StubRun)
    monkeypatch.setattr(lineage, "Job", _StubJob)
    monkeypatch.setattr(lineage, "RunEvent", _StubRunEvent)
    monkeypatch.setattr(lineage, "RunState", _StubRunState)

    try:
        yield CapturedLineage(events=captured)
    finally:
        captured.clear()
