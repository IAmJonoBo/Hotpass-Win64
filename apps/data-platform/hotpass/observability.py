"""Telemetry helpers bridging the registry into existing Hotpass APIs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, cast

from .telemetry.metrics import PipelineMetrics
from .telemetry.registry import TelemetryConfig, TelemetryRegistry, build_default_registry


def _metrics_factory(meter: Any, observation_factory: Any) -> PipelineMetrics:
    return PipelineMetrics(meter, observation_factory)


_REGISTRY = build_default_registry(_metrics_factory)
trace = _REGISTRY.modules.trace
metrics = _REGISTRY.modules.metrics


def use_registry(registry: TelemetryRegistry) -> None:
    """Swap the active registry (used in tests for dependency injection)."""

    global _REGISTRY, trace, metrics
    _REGISTRY = registry
    trace = registry.modules.trace
    metrics = registry.modules.metrics


def initialize_observability(
    service_name: str = "hotpass",
    *,
    environment: str | None = None,
    export_to_console: bool = True,
    exporters: tuple[str, ...] | None = None,
    resource_attributes: Mapping[str, str] | None = None,
    exporter_settings: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Any, Any]:
    """Initialise telemetry instrumentation and return tracer/meter handles."""

    chosen_exporters = exporters
    if chosen_exporters is None:
        chosen_exporters = ("console",) if export_to_console else ("noop",)

    config = TelemetryConfig(
        service_name=service_name,
        environment=environment,
        exporters=chosen_exporters,
        resource_attributes=resource_attributes or {},
        exporter_settings=exporter_settings or {},
    )
    context = _REGISTRY.configure(config)
    return context.tracer, context.meter


def shutdown_observability() -> None:
    """Shutdown the active telemetry providers."""

    _REGISTRY.shutdown()


def get_tracer(name: str = "hotpass") -> Any:
    """Return the tracer from the active registry."""

    return _REGISTRY.get_tracer(name)


def get_meter(name: str = "hotpass") -> Any:
    """Return the meter from the active registry."""

    return _REGISTRY.get_meter(name)


def get_pipeline_metrics() -> PipelineMetrics:
    """Return the pipeline metrics collector."""

    return cast(PipelineMetrics, _REGISTRY.get_metrics())


@contextmanager
def trace_operation(
    operation_name: str, attributes: Mapping[str, Any] | None = None
) -> Iterator[Any]:
    """Create a span around a block of work and record exceptions."""

    tracer = get_tracer()
    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:  # pragma: no cover - exception path exercised in tests
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise


__all__ = [
    "PipelineMetrics",
    "get_tracer",
    "get_meter",
    "get_pipeline_metrics",
    "initialize_observability",
    "shutdown_observability",
    "trace_operation",
    "use_registry",
]
