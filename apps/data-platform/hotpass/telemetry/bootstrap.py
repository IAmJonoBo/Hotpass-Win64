"""Helper utilities for bootstrapping OpenTelemetry instrumentation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from ..observability import get_pipeline_metrics, initialize_observability, shutdown_observability
from .metrics import PipelineMetrics


@dataclass(slots=True)
class TelemetryBootstrapOptions:
    """Declarative options describing how telemetry should be initialised."""

    enabled: bool = False
    service_name: str = "hotpass"
    environment: str | None = None
    exporters: tuple[str, ...] = field(default_factory=tuple)
    resource_attributes: Mapping[str, str | None] = field(default_factory=dict)
    exporter_settings: Mapping[str, Mapping[str, Any] | object] = field(default_factory=dict)

    def resolved_exporters(self) -> tuple[str, ...]:
        """Return the exporter tuple accounting for enabled state and defaults."""

        if not self.enabled:
            return ("noop",)
        if not self.exporters:
            return ("console",)
        return tuple(self.exporters)

    def merged_resource_attributes(
        self, extra: Mapping[str, str | None] | None = None
    ) -> dict[str, str]:
        """Merge configured resource attributes with optional extras."""

        attributes: dict[str, str] = {
            str(key): str(value)
            for key, value in self.resource_attributes.items()
            if value is not None
        }
        if extra:
            for key, value in extra.items():
                if value is None:
                    continue
                attributes[str(key)] = str(value)
        return attributes

    def merged_exporter_settings(self) -> dict[str, dict[str, Any]]:
        """Coerce exporter settings into a plain dictionary."""

        settings: dict[str, dict[str, Any]] = {}
        for name, values in self.exporter_settings.items():
            if not isinstance(values, Mapping):
                continue
            settings[str(name)] = {str(key): value for key, value in values.items()}
        return settings


def bootstrap_metrics(
    options: TelemetryBootstrapOptions,
    *,
    additional_attributes: Mapping[str, str] | None = None,
) -> PipelineMetrics | None:
    """Initialise telemetry using the supplied options and return pipeline metrics."""

    if not options.enabled:
        return None

    attributes = options.merged_resource_attributes(additional_attributes)
    exporters = options.resolved_exporters()

    initialize_observability(
        service_name=options.service_name,
        environment=options.environment,
        exporters=exporters,
        resource_attributes=attributes,
        exporter_settings=options.merged_exporter_settings(),
    )
    return get_pipeline_metrics()


@contextmanager
def telemetry_session(
    options: TelemetryBootstrapOptions,
    *,
    additional_attributes: Mapping[str, str] | None = None,
    auto_shutdown: bool = True,
) -> Iterator[PipelineMetrics | None]:
    """Context manager that initialises telemetry and tears it down on exit."""

    if not options.enabled:
        yield None
    else:
        metrics = bootstrap_metrics(options, additional_attributes=additional_attributes)
        try:
            yield metrics
        finally:
            if auto_shutdown:
                shutdown_observability()


__all__ = [
    "TelemetryBootstrapOptions",
    "bootstrap_metrics",
    "telemetry_session",
]
