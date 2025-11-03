"""Telemetry registry that manages OpenTelemetry providers and policies."""

from __future__ import annotations

import atexit
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any


def _default_register_shutdown(callback: Callable[[], None]) -> None:
    atexit.register(callback)


@dataclass(frozen=True)
class TelemetryConfig:
    """Configuration requested for telemetry instrumentation."""

    service_name: str
    environment: str | None = None
    exporters: tuple[str, ...] = ("console",)
    service_version: str = "0.2.0"
    resource_attributes: Mapping[str, str | None] = field(default_factory=dict)
    exporter_settings: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class TelemetryModules:
    """Collection of OpenTelemetry primitives for the registry to use."""

    available: bool
    metrics: Any
    trace: Any
    meter_provider_cls: type[Any]
    metric_reader_cls: type[Any]
    tracer_provider_cls: type[Any]
    span_processor_cls: type[Any]
    console_span_exporter_cls: type[Any]
    console_metric_exporter_cls: type[Any]
    resource_cls: Any
    span_export_result_cls: Any | None = None
    span_exporter_factories: Mapping[str, Callable[[Mapping[str, Any]], Any]] = field(
        default_factory=dict
    )
    metric_exporter_factories: Mapping[str, Callable[[Mapping[str, Any]], Any]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class TelemetryContext:
    """Active telemetry context returned by the registry."""

    config: TelemetryConfig
    tracer: Any
    meter: Any
    metrics: Any


class TelemetryPolicy:
    """Validate requested telemetry configuration against policy rules."""

    def __init__(self, allowed_exporters: Iterable[str] | None = None) -> None:
        self.allowed_exporters = set(allowed_exporters or {"console", "noop", "otlp"})

    def validate(self, config: TelemetryConfig) -> TelemetryConfig:
        errors: list[str] = []

        service_name = config.service_name.strip()
        if not service_name:
            errors.append("service_name is required")

        exporters = config.exporters or ("console",)
        settings_input = dict(config.exporter_settings or {})
        invalid = [exporter for exporter in exporters if exporter not in self.allowed_exporters]
        if invalid:
            errors.append(f"unsupported exporters: {', '.join(sorted(invalid))}")

        extra_settings = set(settings_input) - set(exporters)
        if extra_settings:
            errors.append(
                "settings provided for exporters that are not enabled: "
                f"{', '.join(sorted(extra_settings))}"
            )

        env_source = config.environment or os.getenv("HOTPASS_ENVIRONMENT") or "development"
        environment = env_source.strip()
        if not environment:
            errors.append("environment is required")

        if errors:
            raise ValueError("; ".join(errors))

        normalised_settings: dict[str, dict[str, Any]] = {}
        for exporter in exporters:
            values = settings_input.get(exporter, {})
            if values and not isinstance(values, Mapping):
                raise ValueError(f"settings for exporter '{exporter}' must be a mapping")
            normalised_settings[exporter] = {
                str(key): value for key, value in dict(values or {}).items()
            }

        attributes = {
            "service.name": service_name,
            "service.version": config.service_version,
            "deployment.environment": environment,
        }
        for key, value in dict(config.resource_attributes).items():
            if value is None:
                continue
            attributes[str(key)] = str(value)

        return TelemetryConfig(
            service_name=service_name,
            environment=environment,
            exporters=tuple(exporters),
            service_version=config.service_version,
            resource_attributes=attributes,
            exporter_settings=normalised_settings,
        )


class TelemetryRegistry:
    """Manage telemetry providers and exporters with dependency injection."""

    def __init__(
        self,
        *,
        modules: TelemetryModules,
        policy: TelemetryPolicy | None = None,
        metrics_factory: Callable[[Any, Callable[[float], Any]], Any],
        register_shutdown: Callable[[Callable[[], None]], None] = _default_register_shutdown,
    ) -> None:
        self.modules = modules
        self._policy = policy or TelemetryPolicy()
        self._metrics_factory = metrics_factory
        self._register_shutdown = register_shutdown

        self._context: TelemetryContext | None = None
        self._shutdown_registered = False
        self._metric_readers: list[Any] = []
        self._metrics: Any | None = None

        self.meter_provider: Any | None = None
        self.tracer_provider: Any | None = None
        self._shutdown_guard = False

    def configure(self, config: TelemetryConfig) -> TelemetryContext:
        """Initialise telemetry if not yet configured and return the context."""

        if self._context is not None:
            return self._context

        validated = self._policy.validate(config)

        if not self.modules.available:
            tracer = self.modules.trace.get_tracer(validated.service_name)
            meter = self.modules.metrics.get_meter(validated.service_name)
            metrics = self._ensure_metrics(meter)
            self._context = TelemetryContext(
                config=validated,
                tracer=tracer,
                meter=meter,
                metrics=metrics,
            )
            context = self._context
            if not self._shutdown_registered:
                self._register_shutdown(self.shutdown)
                self._shutdown_registered = True
            return context

        resource = self.modules.resource_cls.create(dict(validated.resource_attributes))

        self.tracer_provider = self.modules.tracer_provider_cls(resource=resource)
        for exporter in self._create_span_exporters(
            validated.exporters, validated.exporter_settings
        ):
            processor = self.modules.span_processor_cls(exporter)
            self.tracer_provider.add_span_processor(processor)
        self.modules.trace.set_tracer_provider(self.tracer_provider)

        self._metric_readers = self._create_metric_readers(
            validated.exporters, validated.exporter_settings
        )
        self.meter_provider = self.modules.meter_provider_cls(
            metric_readers=self._metric_readers,
            resource=resource,
        )
        self.modules.metrics.set_meter_provider(self.meter_provider)

        tracer = self.modules.trace.get_tracer(validated.service_name)
        meter = self.modules.metrics.get_meter(validated.service_name)
        metrics = self._ensure_metrics(meter)
        self._context = TelemetryContext(
            config=validated,
            tracer=tracer,
            meter=meter,
            metrics=metrics,
        )

        context = self._context

        if not self._shutdown_registered:
            self._shutdown_guard = True
            try:
                self._register_shutdown(self.shutdown)
            finally:
                self._shutdown_guard = False
            self._shutdown_registered = True

        return context

    def get_tracer(self, name: str = "hotpass") -> Any:
        """Return a tracer instance for the supplied name."""

        return self.modules.trace.get_tracer(name)

    def get_meter(self, name: str = "hotpass") -> Any:
        """Return a meter instance for the supplied name."""

        return self.modules.metrics.get_meter(name)

    def get_metrics(self) -> Any:
        """Return or lazily create the pipeline metrics sink."""

        return self._ensure_metrics()

    def shutdown(self) -> None:
        """Shut down configured providers and exporters."""

        if self._shutdown_guard:
            return

        for reader in self._metric_readers:
            shutdown = getattr(reader, "shutdown", None)
            if callable(shutdown):
                shutdown()

        self._metric_readers = []

        for component in (self.meter_provider, self.tracer_provider):
            if component is None:
                continue
            shutdown = getattr(component, "shutdown", None)
            if callable(shutdown):
                shutdown()

        self.meter_provider = None
        self.tracer_provider = None
        self._context = None

    def _create_span_exporters(
        self,
        exporters: tuple[str, ...],
        settings: Mapping[str, Mapping[str, Any]],
    ) -> list[Any]:
        result: list[Any] = []
        for name in exporters:
            if name == "noop":
                continue
            exporter_settings = settings.get(name, {})
            factory = self.modules.span_exporter_factories.get(name)
            if factory is not None:
                delegate = factory(exporter_settings)
                if delegate is not None:
                    result.append(self._safe_span_exporter(delegate))
                continue
            if name == "console":
                delegate = self.modules.console_span_exporter_cls()
                result.append(self._safe_span_exporter(delegate))
        return result

    def _create_metric_readers(
        self,
        exporters: tuple[str, ...],
        settings: Mapping[str, Mapping[str, Any]],
    ) -> list[Any]:
        readers: list[Any] = []
        for name in exporters:
            if name == "noop":
                continue
            exporter_settings = settings.get(name, {})
            factory = self.modules.metric_exporter_factories.get(name)
            if factory is not None:
                delegate = factory(exporter_settings)
                if delegate is None:
                    continue
                readers.append(
                    self.modules.metric_reader_cls(
                        self._safe_metric_exporter(delegate),
                        export_interval_millis=60000,
                    )
                )
                continue
            if name == "console":
                delegate = self.modules.console_metric_exporter_cls()
                readers.append(
                    self.modules.metric_reader_cls(
                        self._safe_metric_exporter(delegate),
                        export_interval_millis=60000,
                    )
                )
        return readers

    def _safe_span_exporter(self, delegate: Any) -> Any:
        result_cls = self.modules.span_export_result_cls

        def _fallback(_: ValueError) -> Any:
            if result_cls is not None:
                return getattr(result_cls, "SUCCESS", None)
            return None

        return _SafeExporterProxy(delegate, _fallback)

    def _safe_metric_exporter(self, delegate: Any) -> Any:
        def _fallback(_: ValueError) -> Any:
            return None

        return _SafeExporterProxy(delegate, _fallback)

    def _ensure_metrics(self, meter: Any | None = None) -> Any:
        if self._metrics is None:
            if meter is None:
                meter = self.modules.metrics.get_meter("hotpass")
            observation_factory = getattr(
                self.modules.metrics,
                "Observation",
                lambda value: SimpleNamespace(value=value),
            )
            self._metrics = self._metrics_factory(meter, observation_factory)
        return self._metrics


class _SafeExporterProxy:
    """Wrap an exporter and swallow ValueError on export."""

    def __init__(self, delegate: Any, fallback: Callable[[ValueError], Any]) -> None:
        self._delegate = delegate
        self._fallback = fallback

    def export(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - runtime guard
        try:
            return self._delegate.export(*args, **kwargs)
        except ValueError as exc:
            return self._fallback(exc)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._delegate, item)


def _build_noop_modules() -> TelemetryModules:
    class _NoopInstrument:
        def add(self, *_: Any, **__: Any) -> None:  # pragma: no cover - noop
            return None

        def record(self, *_: Any, **__: Any) -> None:  # pragma: no cover - noop
            return None

    class _NoopMeter:
        def create_counter(
            self, *args: Any, **kwargs: Any
        ) -> _NoopInstrument:  # pragma: no cover - noop
            return _NoopInstrument()

        def create_histogram(
            self, *args: Any, **kwargs: Any
        ) -> _NoopInstrument:  # pragma: no cover - noop
            return _NoopInstrument()

        def create_observable_gauge(
            self, *args: Any, **kwargs: Any
        ) -> _NoopInstrument:  # pragma: no cover - noop
            return _NoopInstrument()

    class _NoopMetrics(SimpleNamespace):
        def __init__(self) -> None:
            super().__init__(
                meter=_NoopMeter(),
                Observation=lambda value: SimpleNamespace(value=value),
            )
            self.provider: Any | None = None

        def get_meter(self, *_: Any, **__: Any) -> Any:
            return self.meter

        def set_meter_provider(self, provider: Any) -> None:
            self.provider = provider

    class _NoopSpan(SimpleNamespace):
        def set_attribute(self, *_: Any, **__: Any) -> None:  # pragma: no cover - noop
            return None

        def record_exception(self, *_: Any, **__: Any) -> None:  # pragma: no cover - noop
            return None

        def set_status(self, *_: Any, **__: Any) -> None:  # pragma: no cover - noop
            return None

    class _NoopTracer:
        def start_as_current_span(self, *_: Any, **__: Any) -> Any:  # pragma: no cover - noop
            span = _NoopSpan()
            return SimpleNamespace(
                __enter__=lambda: span,
                __exit__=lambda *_: False,
            )

    class _NoopTrace(SimpleNamespace):
        StatusCode = SimpleNamespace(ERROR="ERROR")

        def __init__(self) -> None:
            super().__init__(tracer=_NoopTracer())

        def get_tracer(self, *_: Any, **__: Any) -> Any:
            return self.tracer

        def set_tracer_provider(self, *_: Any, **__: Any) -> None:
            return None

        def Status(self, code: Any, description: str) -> dict[str, Any]:
            return {"code": code, "description": description}

    class _NoopProvider:
        def __init__(self, *_: Any, **__: Any) -> None:  # pragma: no cover - noop
            self.shutdown_called = False

        def add_span_processor(self, *_: Any) -> None:  # pragma: no cover - noop
            return None

        def shutdown(self) -> None:  # pragma: no cover - noop
            self.shutdown_called = True

    class _NoopReader(_NoopProvider):
        pass

    class _NoopResource:
        @staticmethod
        def create(
            attributes: Mapping[str, str],
        ) -> Mapping[str, str]:  # pragma: no cover - noop
            return attributes

    return TelemetryModules(
        available=False,
        metrics=_NoopMetrics(),
        trace=_NoopTrace(),
        meter_provider_cls=_NoopProvider,
        metric_reader_cls=_NoopReader,
        tracer_provider_cls=_NoopProvider,
        span_processor_cls=_NoopProvider,
        console_span_exporter_cls=_NoopProvider,
        console_metric_exporter_cls=_NoopProvider,
        resource_cls=_NoopResource,
        span_export_result_cls=None,
        span_exporter_factories={},
        metric_exporter_factories={},
    )


def build_default_modules() -> TelemetryModules:
    try:  # pragma: no cover - exercised in integration tests
        from opentelemetry import metrics as otel_metrics
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SpanExportResult,
        )

        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter as _OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as _OTLPSpanExporter,
            )
        except ImportError:  # pragma: no cover - optional exporter dependency
            _OTLPMetricExporter = None
            _OTLPSpanExporter = None
        OTLPMetricExporter: type[Any] | None = _OTLPMetricExporter
        OTLPSpanExporter: type[Any] | None = _OTLPSpanExporter
    except ImportError:  # pragma: no cover - runtime fallback
        return _build_noop_modules()

    def _build_console_span(_: Mapping[str, Any]) -> Any:
        return ConsoleSpanExporter()

    def _build_console_metric(_: Mapping[str, Any]) -> Any:
        return ConsoleMetricExporter()

    def _parse_otlp_kwargs(config: Mapping[str, Any], *, metrics: bool = False) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        endpoint_key = "metrics_endpoint" if metrics else "endpoint"
        endpoint_value = config.get(endpoint_key) or config.get("endpoint")
        if endpoint_value:
            kwargs["endpoint"] = str(endpoint_value)
        headers = config.get("headers")
        if isinstance(headers, Mapping):
            kwargs["headers"] = {str(key): str(value) for key, value in headers.items()}
        if "insecure" in config:
            kwargs["insecure"] = bool(config.get("insecure"))
        if "timeout" in config:
            timeout_value = config.get("timeout")
            if timeout_value is not None:
                try:
                    kwargs["timeout"] = float(timeout_value)
                except (TypeError, ValueError):
                    pass
        return kwargs

    span_factories: dict[str, Callable[[Mapping[str, Any]], Any]] = {
        "console": _build_console_span,
    }
    metric_factories: dict[str, Callable[[Mapping[str, Any]], Any]] = {
        "console": _build_console_metric,
    }

    if OTLPSpanExporter is not None and OTLPMetricExporter is not None:

        def _build_otlp_span(config: Mapping[str, Any]) -> Any:
            kwargs = _parse_otlp_kwargs(config, metrics=False)
            return OTLPSpanExporter(**kwargs)

        def _build_otlp_metric(config: Mapping[str, Any]) -> Any:
            kwargs = _parse_otlp_kwargs(config, metrics=True)
            return OTLPMetricExporter(**kwargs)

        span_factories["otlp"] = _build_otlp_span
        metric_factories["otlp"] = _build_otlp_metric

    return TelemetryModules(
        available=True,
        metrics=otel_metrics,
        trace=otel_trace,
        meter_provider_cls=MeterProvider,
        metric_reader_cls=PeriodicExportingMetricReader,
        tracer_provider_cls=TracerProvider,
        span_processor_cls=BatchSpanProcessor,
        console_span_exporter_cls=ConsoleSpanExporter,
        console_metric_exporter_cls=ConsoleMetricExporter,
        resource_cls=Resource,
        span_export_result_cls=SpanExportResult,
        span_exporter_factories=span_factories,
        metric_exporter_factories=metric_factories,
    )


def build_default_registry(
    metrics_factory: Callable[[Any, Callable[[float], Any]], Any],
) -> TelemetryRegistry:
    """Create a registry populated with default modules."""

    modules = build_default_modules()
    return TelemetryRegistry(modules=modules, metrics_factory=metrics_factory)
