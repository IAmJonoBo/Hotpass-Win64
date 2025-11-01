"""Observability helper behaviour tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest
from hotpass import observability
from hotpass.telemetry.registry import TelemetryRegistry

from tests.helpers.assertions import expect
from tests.helpers.fixtures import fixture


class DummySpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, Any] = {}
        self.exceptions: list[Exception] = []
        self.status = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.exceptions.append(exc)

    def set_status(self, status: Any) -> None:
        self.status = status


class DummyTracer:
    def __init__(self) -> None:
        self.started: list[DummySpan] = []

    @contextmanager
    def start_as_current_span(self, name: str) -> Any:
        span = DummySpan(name)
        self.started.append(span)
        try:
            yield span
        finally:
            pass


class DummyMetrics:
    def __init__(self) -> None:
        self.records: list[str] = []


class StubStatusCode:
    ERROR = "error"


class StubStatus:
    def __init__(self, code: Any, description: str | None = None) -> None:
        self.code = code
        self.description = description


class StubModules:
    def __init__(self, tracer: DummyTracer) -> None:
        self.trace = SimpleNamespace(Status=StubStatus, StatusCode=StubStatusCode)
        self.metrics = SimpleNamespace(tracer=tracer)


class StubContext:
    def __init__(self, tracer: DummyTracer, meter: object) -> None:
        self.tracer = tracer
        self.meter = meter


class StubRegistry:
    def __init__(self) -> None:
        self.tracer = DummyTracer()
        self.meter = object()
        self.metrics = DummyMetrics()
        self.modules = StubModules(self.tracer)
        self.configured: list[Any] = []
        self.shutdown_called = False

    def configure(self, config: Any) -> StubContext:
        self.configured.append(config)
        return StubContext(self.tracer, self.meter)

    def shutdown(self) -> None:
        self.shutdown_called = True

    def get_tracer(self, name: str) -> DummyTracer:
        return self.tracer

    def get_meter(self, name: str) -> object:
        return self.meter

    def get_metrics(self) -> DummyMetrics:
        return self.metrics


@fixture()
def stub_registry(monkeypatch: pytest.MonkeyPatch) -> Generator[StubRegistry]:
    original = observability._REGISTRY
    registry = StubRegistry()
    observability.use_registry(cast(TelemetryRegistry, registry))
    try:
        yield registry
    finally:
        observability.use_registry(original)


def test_use_registry_updates_trace_and_metrics(stub_registry: StubRegistry) -> None:
    expect(
        observability.trace.Status is StubStatus,
        "Trace helpers should come from stub registry",
    )
    expect(
        observability.metrics.tracer is stub_registry.tracer,
        "Metrics module should surface tracer",
    )


def test_initialize_observability_configures_registry(
    stub_registry: StubRegistry,
) -> None:
    tracer, meter = observability.initialize_observability(
        service_name="svc",
        exporters=("noop",),
        export_to_console=False,
        resource_attributes={"env": "test"},
    )
    expect(bool(stub_registry.configured), "Registry configure should be invoked")
    config = stub_registry.configured[0]
    expect(config.service_name == "svc", "Service name should be forwarded to registry")
    expect(tracer is stub_registry.tracer, "Tracer handle should originate from registry")
    expect(meter is stub_registry.meter, "Meter handle should originate from registry")


def test_trace_operation_records_attributes_and_errors(
    stub_registry: StubRegistry,
) -> None:
    with observability.trace_operation("demo", {"key": "value"}) as span:
        expect(span.attributes["key"] == "value", "Attributes should be set on span")

    try:
        with observability.trace_operation("demo"):
            raise RuntimeError("boom")
    except RuntimeError:
        expect(
            bool(stub_registry.tracer.started[-1].exceptions),
            "Exception should be recorded on span",
        )
        status = stub_registry.tracer.started[-1].status
        expect(status is not None, "Status should be set on error")
        status_code = cast(StubStatus, status).code
        expect(status_code == StubStatusCode.ERROR, "Span status should mark error")
    else:  # pragma: no cover - defensive guard
        raise AssertionError("RuntimeError should propagate from trace_operation")


def test_shutdown_and_metric_helpers_use_registry(stub_registry: StubRegistry) -> None:
    metrics = observability.get_pipeline_metrics()
    assert isinstance(metrics, DummyMetrics), "Metric helper should proxy registry output"
    expect(metrics is stub_registry.metrics, "Metric helper should proxy registry output")
    observability.shutdown_observability()
    expect(stub_registry.shutdown_called is True, "Registry shutdown should be triggered")
