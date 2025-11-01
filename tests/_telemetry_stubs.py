from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Literal


@dataclass
class DummyMetricsModule:
    meter: Any

    def __post_init__(self) -> None:
        self.provider: Any | None = None
        self.Observation = lambda value: SimpleNamespace(value=value)

    def get_meter(self, *_: Any, **__: Any) -> Any:
        return self.meter

    def set_meter_provider(self, provider: Any) -> None:
        self.provider = provider


class DummyMeter:
    def __init__(self) -> None:
        self.counters: dict[str, Any] = {}
        self.histograms: dict[str, Any] = {}
        self.gauges: dict[str, Any] = {}

    def create_counter(self, name: str, **_: Any) -> SimpleNamespace:
        counter = SimpleNamespace(calls=[])
        self.counters[name] = counter
        return counter

    def create_histogram(self, name: str, **_: Any) -> SimpleNamespace:
        histogram = SimpleNamespace(calls=[])
        self.histograms[name] = histogram
        return histogram

    def create_observable_gauge(self, name: str, callbacks: list[Any], **_: Any) -> SimpleNamespace:
        gauge = SimpleNamespace(callbacks=list(callbacks))
        self.gauges[name] = gauge
        return gauge


class DummyTraceModule:
    StatusCode = SimpleNamespace(ERROR="ERROR")

    def __init__(self) -> None:
        self.provider: Any | None = None
        self.tracer = DummyTracer()

    def get_tracer(self, *_: Any, **__: Any) -> Any:
        return self.tracer

    def set_tracer_provider(self, provider: Any) -> None:
        self.provider = provider

    def Status(self, code: Any, description: str) -> dict[str, Any]:
        return {"code": code, "description": description}


class DummyTracer:
    def __init__(self) -> None:
        self.spans: list[DummySpan] = []

    def start_as_current_span(self, name: str) -> DummySpanContext:
        span = DummySpan(name)
        self.spans.append(span)
        return DummySpanContext(span)


class DummySpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, Any] = {}
        self.exceptions: list[Exception] = []
        self.status: Any | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.exceptions.append(exc)

    def set_status(self, status: Any) -> None:
        self.status = status


class DummySpanContext:
    def __init__(self, span: DummySpan) -> None:
        self._span = span

    def __enter__(self) -> DummySpan:
        return self._span

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        return False


class DummyMeterProvider:
    def __init__(self, *, metric_readers: list[Any], resource: Any) -> None:
        self.metric_readers = list(metric_readers)
        self.resource = resource
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True


class DummyMetricReader:
    instances: list[DummyMetricReader] = []

    def __init__(self, exporter: Any, export_interval_millis: int = 60000) -> None:
        self.exporter = exporter
        self.export_interval_millis = export_interval_millis
        self.shutdown_called = False
        self.__class__.instances.append(self)

    def shutdown(self) -> None:
        self.shutdown_called = True


class DummyTracerProvider:
    def __init__(self, *, resource: Any) -> None:
        self.resource = resource
        self.processors: list[Any] = []
        self.shutdown_called = False

    def add_span_processor(self, processor: Any) -> None:
        self.processors.append(processor)

    def shutdown(self) -> None:
        self.shutdown_called = True


class DummySpanProcessor:
    def __init__(self, exporter: Any) -> None:
        self.exporter = exporter


class DummyConsoleSpanExporter:
    def __init__(self) -> None:
        self.exported: list[Any] = []

    def export(self, spans: Any) -> Any:
        self.exported.append(spans)
        return spans


class DummyConsoleMetricExporter:
    def export(self, *_: Any, **__: Any) -> Any:
        return None


class DummyResource:
    last_attributes: dict[str, Any] | None = None

    @staticmethod
    def create(attributes: dict[str, Any]) -> dict[str, Any]:
        DummyResource.last_attributes = attributes
        return attributes


class DummyMetrics:
    def __init__(self, meter: Any, observation_factory: Any) -> None:
        self.meter = meter
        self.observation_factory = observation_factory

        self.records_processed = self._counter("hotpass.records.processed")
        self.validation_failures = self._counter("hotpass.validation.failures")
        self.load_duration = self._histogram("hotpass.load.duration")
        self.aggregation_duration = self._histogram("hotpass.aggregation.duration")
        self.validation_duration = self._histogram("hotpass.validation.duration")
        self.write_duration = self._histogram("hotpass.write.duration")
        self.automation_requests = self._counter("hotpass.automation.requests")
        self.automation_failures = self._counter("hotpass.automation.failures")
        self.automation_latency = self._histogram("hotpass.automation.duration")
        self.acquisition_duration = self._histogram("hotpass.acquisition.duration")
        self.acquisition_records = self._counter("hotpass.acquisition.records")
        self.acquisition_warnings = self._counter("hotpass.acquisition.warnings")
        self.data_quality_score = meter.create_observable_gauge(
            name="hotpass.data.quality_score",
            callbacks=[self._observe_quality_score],
        )

        self._latest_quality_score = 0.0

    def _counter(self, name: str) -> SimpleNamespace:
        counter = self.meter.create_counter(name)

        def add(amount: int, attributes: dict[str, Any] | None = None) -> None:
            counter.calls.append((amount, attributes or {}))

        counter.add = add
        return counter  # type: ignore[no-any-return]

    def _histogram(self, name: str) -> SimpleNamespace:
        histogram = self.meter.create_histogram(name)

        def record(value: float, attributes: dict[str, Any] | None = None) -> None:
            histogram.calls.append((value, attributes or {}))

        histogram.record = record
        return histogram  # type: ignore[no-any-return]

    def _observe_quality_score(self, *_: Any) -> list[Any]:
        return [self.observation_factory(self._latest_quality_score)]

    def record_records_processed(self, count: int, source: str = "unknown") -> None:
        self.records_processed.add(count, {"source": source})

    def record_validation_failure(self, rule_name: str) -> None:
        self.validation_failures.add(1, {"rule": rule_name})

    def record_load_duration(self, seconds: float, source: str = "unknown") -> None:
        self.load_duration.record(seconds, {"source": source})

    def record_aggregation_duration(self, seconds: float) -> None:
        self.aggregation_duration.record(seconds)

    def record_validation_duration(self, seconds: float) -> None:
        self.validation_duration.record(seconds)

    def record_write_duration(self, seconds: float) -> None:
        self.write_duration.record(seconds)

    def update_quality_score(self, score: float) -> None:
        self._latest_quality_score = score

    def record_automation_delivery(
        self,
        *,
        target: str,
        status: str,
        endpoint: str | None,
        attempts: int,
        latency: float | None,
        idempotency: str,
    ) -> None:
        attributes: dict[str, Any] = {
            "target": target,
            "status": status,
            "attempts": attempts,
            "idempotency": idempotency,
        }
        if endpoint:
            attributes["endpoint"] = endpoint

        self.automation_requests.add(1, attributes)
        if status != "delivered":
            self.automation_failures.add(1, attributes)
        if latency is not None:
            self.automation_latency.record(latency, attributes)

    def record_acquisition_duration(
        self,
        seconds: float,
        *,
        scope: str,
        agent: str | None = None,
        provider: str | None = None,
        extra_attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = self._acquisition_attributes(scope, agent, provider, extra_attributes)
        self.acquisition_duration.record(seconds, attributes)

    def record_acquisition_records(
        self,
        count: int,
        *,
        scope: str,
        agent: str | None = None,
        provider: str | None = None,
        extra_attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = self._acquisition_attributes(scope, agent, provider, extra_attributes)
        self.acquisition_records.add(count, attributes)

    def record_acquisition_warnings(
        self,
        count: int,
        *,
        scope: str,
        agent: str | None = None,
        provider: str | None = None,
        extra_attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = self._acquisition_attributes(scope, agent, provider, extra_attributes)
        self.acquisition_warnings.add(count, attributes)

    @staticmethod
    def _acquisition_attributes(
        scope: str,
        agent: str | None,
        provider: str | None,
        extra_attributes: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        attributes: dict[str, Any] = {"scope": scope}
        if agent:
            attributes["agent"] = agent
        if provider:
            attributes["provider"] = provider
        if extra_attributes:
            attributes.update(extra_attributes)
        return attributes


def build_modules(
    available: bool = True,
) -> tuple[DummyMeter, DummyTraceModule, DummyMetricsModule]:
    meter = DummyMeter()
    metrics_module = DummyMetricsModule(meter=meter)
    trace_module = DummyTraceModule()
    return meter, trace_module, metrics_module
