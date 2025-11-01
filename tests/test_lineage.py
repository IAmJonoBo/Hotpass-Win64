"""Tests for the OpenLineage integration helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

for _module_name in ("duckdb", "pyarrow", "polars"):
    sys.modules.setdefault(_module_name, types.ModuleType(_module_name))
if not hasattr(sys.modules["pyarrow"], "bool_"):
    sys.modules["pyarrow"].bool_ = lambda: object()  # type: ignore[attr-defined]

_LINEAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "data-platform"
    / "hotpass"
    / "lineage.py"
)
_LINEAGE_SPEC = importlib.util.spec_from_file_location("hotpass.lineage", _LINEAGE_PATH)
if (
    _LINEAGE_SPEC is None or _LINEAGE_SPEC.loader is None
):  # pragma: no cover - safety check
    raise RuntimeError("Unable to load hotpass.lineage module specification")
lineage = importlib.util.module_from_spec(_LINEAGE_SPEC)
sys.modules.setdefault("hotpass.lineage", lineage)
_LINEAGE_SPEC.loader.exec_module(lineage)


def expect(condition: bool, message: str) -> None:
    """Fail the test with a descriptive message when condition is false."""

    if not condition:
        pytest.fail(message)


class _StubDataset:
    def __init__(
        self, *, namespace: str, name: str, facets: Mapping[str, object]
    ) -> None:
        self.namespace = namespace
        self.name = name
        self.facets = dict(facets)


class _StubRun:
    def __init__(self, *, runId: str, facets: Mapping[str, object] | None = None) -> None:  # noqa: N803 - OpenLineage naming
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
    ) -> None:
        self.eventTime = eventTime
        self.producer = producer
        self.eventType = eventType
        self.run = run
        self.job = job
        self.inputs = inputs
        self.outputs = outputs


class _StubRunState:
    START = "START"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"


class _StubClient:
    emitted: list[_StubRunEvent] = []

    def emit(self, event: _StubRunEvent) -> None:
        self.emitted.append(event)


def test_create_emitter_returns_null_when_openlineage_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubClient.emitted = []
    monkeypatch.setattr(lineage, "OpenLineageClient", None)
    monkeypatch.setattr(lineage, "InputDataset", None)
    monkeypatch.setattr(lineage, "OutputDataset", None)
    monkeypatch.setattr(lineage, "RunEvent", None)
    monkeypatch.setattr(lineage, "RunState", None)
    monkeypatch.setattr(lineage, "Job", None)
    monkeypatch.setattr(lineage, "Run", None)

    emitter = lineage.create_emitter("noop-job")

    expect(
        isinstance(emitter, lineage.NullLineageEmitter),
        "Expected NullLineageEmitter when OpenLineage is unavailable.",
    )
    expect(
        emitter.is_enabled is False, "Emitter should be disabled without OpenLineage."
    )


def test_lineage_emitter_emits_events_with_stubbed_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StubClient.emitted = []
    monkeypatch.setattr(lineage, "OpenLineageClient", _StubClient)
    monkeypatch.setattr(lineage, "set_lineage_producer", lambda _: None)
    monkeypatch.setattr(lineage, "InputDataset", _StubDataset)
    monkeypatch.setattr(lineage, "OutputDataset", _StubDataset)
    monkeypatch.setattr(lineage, "Run", _StubRun)
    monkeypatch.setattr(lineage, "Job", _StubJob)
    monkeypatch.setattr(lineage, "RunEvent", _StubRunEvent)
    monkeypatch.setattr(lineage, "RunState", _StubRunState)

    emitter = lineage.create_emitter("active-job", run_id="run-123")

    expect(
        emitter.is_enabled is True,
        "Emitter should be enabled with a configured client.",
    )

    emitter.emit_start(inputs=["input-a"])
    emitter.emit_complete(outputs=["output-b"])

    expect(len(_StubClient.emitted) == 2, "Expected start and complete events to emit.")
    expect(
        _StubClient.emitted[0].eventType == _StubRunState.START,
        "First event should signal a START state.",
    )
    expect(
        _StubClient.emitted[1].eventType == _StubRunState.COMPLETE,
        "Second event should signal a COMPLETE state.",
    )
    expect(
        _StubClient.emitted[0].inputs[0].name.endswith("input-a"),
        "Input dataset name should include the provided alias.",
    )
    expect(
        _StubClient.emitted[1].outputs[0].name.endswith("output-b"),
        "Output dataset name should include the provided alias.",
    )

    emitter.emit_fail("boom", outputs=["output-c"])
    expect(
        len(_StubClient.emitted) == 3, "Expected failure event to append to the log."
    )
    expect(
        _StubClient.emitted[-1].eventType == _StubRunState.FAIL,
        "Final event should signal a FAIL state.",
    )
    expect(
        _StubClient.emitted[-1].outputs[0].name.endswith("output-c"),
        "Failure event output dataset should match the provided alias.",
    )


def test_lineage_emitter_honours_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment variables should override namespace and producer metadata."""

    _StubClient.emitted = []
    monkeypatch.setenv("HOTPASS_LINEAGE_NAMESPACE", "hotpass.staging")
    monkeypatch.setenv(
        "HOTPASS_LINEAGE_PRODUCER", "https://hotpass.dev/custom-producer"
    )

    captured: dict[str, str] = {}

    def _capture_producer(value: str) -> None:
        captured["producer"] = value

    monkeypatch.setattr(lineage, "OpenLineageClient", _StubClient)
    monkeypatch.setattr(lineage, "set_lineage_producer", _capture_producer)
    monkeypatch.setattr(lineage, "InputDataset", _StubDataset)
    monkeypatch.setattr(lineage, "OutputDataset", _StubDataset)
    monkeypatch.setattr(lineage, "Run", _StubRun)
    monkeypatch.setattr(lineage, "Job", _StubJob)
    monkeypatch.setattr(lineage, "RunEvent", _StubRunEvent)
    monkeypatch.setattr(lineage, "RunState", _StubRunState)

    emitter = lineage.create_emitter("marquez-job")

    expect(
        emitter.is_enabled is True,
        "Emitter should activate when OpenLineage is available.",
    )
    expect(
        emitter.namespace == "hotpass.staging",
        "Namespace should honour HOTPASS_LINEAGE_NAMESPACE override.",
    )
    expect(
        emitter.producer == "https://hotpass.dev/custom-producer",
        "Producer should honour HOTPASS_LINEAGE_PRODUCER override.",
    )

    emitter.emit_start(inputs=[{"namespace": "input", "name": "dataset", "facets": {}}])
    emitter.emit_complete(outputs=["refined"])

    expect(len(_StubClient.emitted) == 2, "Expected start and complete events to emit.")
    expect(
        captured.get("producer") == emitter.producer,
        "Producer setter should receive override value.",
    )
    latest_event = _StubClient.emitted[-1]
    hotpass_facet = cast(dict[str, Any], latest_event.run.facets.get("hotpass", {}))
    expect(
        bool(hotpass_facet),
        "Hotpass facet should be attached to run events.",
    )
    expect(
        hotpass_facet.get("hotpass_version") is not None,
        "Hotpass facet should include the package version.",
    )


def test_lineage_emitter_respects_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """HOTPASS_DISABLE_LINEAGE should short-circuit emitter initialisation."""

    monkeypatch.setenv("HOTPASS_DISABLE_LINEAGE", "1")
    monkeypatch.setattr(lineage, "OpenLineageClient", _StubClient)

    emitter = lineage.create_emitter("marquez-job")

    expect(
        emitter.is_enabled is False,
        "Emitter should be disabled when lineage is suppressed via env var.",
    )
