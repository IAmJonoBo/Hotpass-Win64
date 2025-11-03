# ruff: noqa: I001

from __future__ import annotations

import pytest

pytest.importorskip("frictionless")

from hotpass.telemetry.registry import (
    TelemetryConfig,
    TelemetryModules,
    TelemetryPolicy,
    TelemetryRegistry,
)

from ._telemetry_stubs import (
    DummyConsoleMetricExporter,
    DummyConsoleSpanExporter,
    DummyMeterProvider,
    DummyMetricReader,
    DummyMetrics,
    DummyResource,
    DummySpanProcessor,
    DummyTracerProvider,
    build_modules,
)


def _modules(available: bool = True) -> TelemetryModules:
    DummyMetricReader.instances = []
    meter, trace_module, metrics_module = build_modules()

    return TelemetryModules(
        available=available,
        metrics=metrics_module,
        trace=trace_module,
        meter_provider_cls=DummyMeterProvider,
        metric_reader_cls=DummyMetricReader,
        tracer_provider_cls=DummyTracerProvider,
        span_processor_cls=DummySpanProcessor,
        console_span_exporter_cls=DummyConsoleSpanExporter,
        console_metric_exporter_cls=DummyConsoleMetricExporter,
        resource_cls=DummyResource,
    )


def test_policy_requires_service_and_exporters() -> None:
    policy = TelemetryPolicy(allowed_exporters={"console", "noop"})

    with pytest.raises(ValueError):
        policy.validate(TelemetryConfig(service_name="", environment=None, exporters=()))

    with pytest.raises(ValueError):
        policy.validate(
            TelemetryConfig(
                service_name="svc",
                environment=None,
                exporters=("unknown",),
            )
        )


def test_registry_initializes_console_exporters() -> None:
    modules = _modules()
    policy = TelemetryPolicy(allowed_exporters={"console"})
    registry = TelemetryRegistry(
        modules=modules,
        policy=policy,
        metrics_factory=DummyMetrics,
        register_shutdown=lambda fn: fn(),
    )

    context = registry.configure(
        TelemetryConfig(
            service_name="svc",
            environment="prod",
            exporters=("console",),
            resource_attributes={"custom": "value"},
        )
    )

    assert modules.trace.provider is registry.tracer_provider
    assert modules.metrics.provider is registry.meter_provider
    assert isinstance(context.metrics, DummyMetrics)
    assert DummyResource.last_attributes == {
        "service.name": "svc",
        "service.version": "0.2.0",
        "deployment.environment": "prod",
        "custom": "value",
    }
    assert modules.trace.tracer.start_as_current_span("run").__enter__().name == "run"


def test_registry_reuses_existing_context() -> None:
    modules = _modules()
    policy = TelemetryPolicy(allowed_exporters={"console"})
    registry = TelemetryRegistry(
        modules=modules,
        policy=policy,
        metrics_factory=DummyMetrics,
        register_shutdown=lambda fn: fn(),
    )

    context = registry.configure(
        TelemetryConfig(service_name="svc", environment="prod", exporters=("console",))
    )
    second = registry.configure(
        TelemetryConfig(service_name="svc", environment="prod", exporters=("console",))
    )

    assert second is context
    assert len(DummyMetricReader.instances) == 1


def test_registry_shutdown_invokes_components() -> None:
    modules = _modules()
    policy = TelemetryPolicy(allowed_exporters={"console"})
    registry = TelemetryRegistry(
        modules=modules,
        policy=policy,
        metrics_factory=DummyMetrics,
        register_shutdown=lambda fn: fn(),
    )

    registry.configure(
        TelemetryConfig(service_name="svc", environment="prod", exporters=("console",))
    )
    reader = DummyMetricReader.instances[0]
    meter_provider = registry.meter_provider
    tracer_provider = registry.tracer_provider

    registry.shutdown()

    assert reader.shutdown_called is True
    assert meter_provider is not None and meter_provider.shutdown_called is True
    assert tracer_provider is not None and tracer_provider.shutdown_called is True


def test_registry_handles_missing_dependencies() -> None:
    modules = _modules(available=False)
    policy = TelemetryPolicy(allowed_exporters={"console"})
    registry = TelemetryRegistry(
        modules=modules,
        policy=policy,
        metrics_factory=DummyMetrics,
        register_shutdown=lambda fn: fn(),
    )

    context = registry.configure(
        TelemetryConfig(service_name="svc", environment="prod", exporters=("console",))
    )

    assert context.metrics is not None
    assert registry.meter_provider is None
    assert registry.tracer_provider is None
