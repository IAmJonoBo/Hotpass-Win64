"""Telemetry helpers for instrumenting pipeline stages."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

from ..observability import get_pipeline_metrics, get_tracer, trace

_STAGE_TO_METRIC = {
    "ingest": "load",
    "canonicalise": "aggregation",
    "canonicalize": "aggregation",
    "validate": "validation",
    "link": None,
    "publish": "write",
}


@contextmanager
def pipeline_stage(stage: str, attributes: Mapping[str, object] | None = None) -> Iterator[object]:
    """Create an OpenTelemetry span for a pipeline stage."""

    tracer = get_tracer("hotpass.pipeline")
    metrics = get_pipeline_metrics()
    span_name = f"pipeline.{stage}"
    start_time = time.perf_counter()
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("hotpass.pipeline.stage", stage)
        if attributes:
            for key, value in attributes.items():
                attr_key = f"hotpass.pipeline.{key}"
                if isinstance(value, str | bool | int | float):
                    span.set_attribute(attr_key, value)
                elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                    serialised = ", ".join(str(item) for item in value)
                    span.set_attribute(attr_key, serialised)
                else:
                    span.set_attribute(attr_key, str(value))
        try:
            yield span
        except Exception as exc:  # pragma: no cover - exercised in error tests
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise
        finally:
            duration = time.perf_counter() - start_time
            span.set_attribute("hotpass.pipeline.duration_seconds", duration)
            metric_key = _STAGE_TO_METRIC.get(stage)
            if metric_key == "load":
                metrics.record_load_duration(duration)
            elif metric_key == "aggregation":
                metrics.record_aggregation_duration(duration)
            elif metric_key == "validation":
                metrics.record_validation_duration(duration)
            elif metric_key == "write":
                metrics.record_write_duration(duration)
