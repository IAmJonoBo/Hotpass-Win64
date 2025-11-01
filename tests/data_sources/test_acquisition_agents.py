from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import hotpass.observability as observability
from hotpass.data_sources.agents import (
    AcquisitionPlan,
    AgentDefinition,
    ProviderDefinition,
    TargetDefinition,
    run_plan,
)
from hotpass.pipeline.config import PipelineConfig
from hotpass.pipeline.ingestion import ingest_sources
from hotpass.telemetry.registry import TelemetryModules, TelemetryPolicy, TelemetryRegistry

from tests._telemetry_stubs import (
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
from tests.helpers.fixtures import fixture


@fixture(autouse=True)
def telemetry_registry() -> Iterator[None]:
    DummyMetricReader.instances = []
    _meter, trace_module, metrics_module = build_modules()
    modules = TelemetryModules(
        available=True,
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
    policy = TelemetryPolicy(allowed_exporters={"console"})
    registry = TelemetryRegistry(
        modules=modules,
        policy=policy,
        metrics_factory=DummyMetrics,
        register_shutdown=lambda fn: fn(),
    )
    observability.use_registry(registry)
    observability.initialize_observability(service_name="test-acquisition")
    yield
    observability.shutdown_observability()


def _build_sample_plan() -> AcquisitionPlan:
    linkedin_options = {
        "profiles": {
            "hotpass": {
                "organization": "Hotpass Aero",
                "website": "https://hotpass.example",
                "profile_url": "https://linkedin.com/company/hotpass",
                "contacts": [
                    {
                        "name": "Pat Agent",
                        "title": "Director",
                        "email": "pat.agent@hotpass.example",
                        "phone": "+27 11 123 4567",
                        "confidence": 0.92,
                    }
                ],
            }
        }
    }
    clearbit_options = {
        "companies": {
            "hotpass.example": {
                "name": "Hotpass Aero",
                "domain": "hotpass.example",
                "description": "Aviation analytics",
                "category": "aviation",
                "tags": ["Aviation", "Analytics"],
                "confidence": 0.88,
            }
        }
    }
    return AcquisitionPlan(
        enabled=True,
        agents=(
            AgentDefinition(
                name="prospector",
                search_terms=("hotpass",),
                providers=(
                    ProviderDefinition(name="linkedin", options=linkedin_options),
                    ProviderDefinition(name="clearbit", options=clearbit_options),
                ),
                targets=(TargetDefinition(identifier="hotpass", domain="hotpass.example"),),
            ),
        ),
    )


def test_run_plan_collects_records_with_provenance() -> None:
    plan = _build_sample_plan()
    frame, timings, warnings = run_plan(plan, country_code="ZA")

    assert not frame.empty
    assert "provenance" in frame.columns
    first_provenance = frame.iloc[0]["provenance"]
    assert isinstance(first_provenance, list) and first_provenance
    assert any(entry.get("provider") == "linkedin" for entry in first_provenance)
    assert any(timing.agent_name == "prospector" for timing in timings)
    assert warnings == []


def test_ingest_sources_includes_agent_results(tmp_path: Path) -> None:
    plan = _build_sample_plan()
    config = PipelineConfig(
        input_dir=tmp_path,
        output_path=tmp_path / "refined.xlsx",
        acquisition_plan=plan,
    )
    frame, timings, events = ingest_sources(config)

    assert not frame.empty
    assert "LinkedIn" in frame["source_dataset"].unique()
    assert any(key.startswith("agent:") for key in timings)
    assert events == []


def test_run_plan_emits_telemetry() -> None:
    plan = _build_sample_plan()
    frame, timings, warnings = run_plan(plan, country_code="ZA")

    assert not frame.empty
    assert timings
    assert warnings == []

    tracer = observability.trace.get_tracer("hotpass")
    span_names = [span.name for span in tracer.spans]
    assert "acquisition.plan" in span_names
    assert "acquisition.agent" in span_names
    assert "acquisition.provider" in span_names

    plan_span = next(span for span in tracer.spans if span.name == "acquisition.plan")
    assert plan_span.attributes["hotpass.acquisition.records"] >= 1

    agent_span = next(span for span in tracer.spans if span.name == "acquisition.agent")
    assert agent_span.attributes["hotpass.acquisition.agent"] == "prospector"
    assert agent_span.attributes["hotpass.acquisition.records"] >= 1

    provider_spans = [span for span in tracer.spans if span.name == "acquisition.provider"]
    assert provider_spans
    providers_seen = {span.attributes["hotpass.acquisition.provider"] for span in provider_spans}
    assert providers_seen == {"linkedin", "clearbit"}

    metrics = observability.get_pipeline_metrics()
    duration_calls = metrics.acquisition_duration.calls
    assert any(attrs.get("scope") == "plan" for _, attrs in duration_calls)
    assert any(
        attrs.get("scope") == "agent" and attrs.get("agent") == "prospector"
        for _, attrs in duration_calls
    )
    assert any(
        attrs.get("scope") == "provider" and attrs.get("provider") == "linkedin"
        for _, attrs in duration_calls
    )

    record_calls = metrics.acquisition_records.calls
    assert any(attrs.get("scope") == "plan" for _, attrs in record_calls)
    assert any(
        attrs.get("scope") == "provider" and attrs.get("provider") == "clearbit"
        for _, attrs in record_calls
    )
