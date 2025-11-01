from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("frictionless")
pytestmark = pytest.mark.bandwidth("smoke")

from hotpass.pipeline import (
    PIIRedactionConfig,
    PipelineConfig,
    PipelineResult,
    QualityReport,
    default_feature_bundle,
)
from hotpass.pipeline.features import (
    ComplianceFeature,
    EnhancedPipelineConfig,
    EnrichmentFeature,
    EntityResolutionFeature,
    FeatureContext,
    GeospatialFeature,
    default_trace_factory,
)


def _base_context(tmp_path, enhanced_config) -> FeatureContext:
    base_config = PipelineConfig(
        input_dir=tmp_path,
        output_path=tmp_path / "refined.xlsx",
        pii_redaction=PIIRedactionConfig(enabled=False),
    )
    return FeatureContext(
        base_config=base_config,
        enhanced_config=enhanced_config,
        trace_factory=default_trace_factory(enhanced_config.enable_observability),
    )


def _result(frame: pd.DataFrame) -> PipelineResult:
    report = QualityReport(
        total_records=len(frame),
        invalid_records=0,
        schema_validation_errors=[],
        expectations_passed=True,
        expectation_failures=[],
        source_breakdown={},
        data_quality_distribution={"mean": 0.5},
        performance_metrics={},
    )
    return PipelineResult(refined=frame, quality_report=report, performance_metrics={})


def test_entity_resolution_feature_applies_linkage(tmp_path, monkeypatch):
    df = pd.DataFrame({"organization_name": ["Alpha"], "organization_slug": ["alpha"]})
    enhanced_config = EnhancedPipelineConfig(enable_entity_resolution=True)
    context = _base_context(tmp_path, enhanced_config)

    deduped = df.assign(priority_applied=True)

    def fake_link_entities(frame, _config):
        assert frame is df
        return SimpleNamespace(deduplicated=frame.assign(linked=True))

    def fake_add_scores(frame):
        assert "linked" in frame
        return deduped

    monkeypatch.setattr(
        "hotpass.pipeline.features.entity_resolution.link_entities", fake_link_entities
    )
    monkeypatch.setattr(
        "hotpass.pipeline.features.entity_resolution.add_ml_priority_scores",
        fake_add_scores,
    )

    result = EntityResolutionFeature().apply(_result(df), context)

    assert result.linkage is not None
    assert "priority_applied" in result.refined.columns


def test_entity_resolution_feature_falls_back(tmp_path, monkeypatch):
    df = pd.DataFrame({"organization_name": ["Alpha"], "organization_slug": ["alpha"]})
    enhanced_config = EnhancedPipelineConfig(enable_entity_resolution=True, use_splink=True)
    context = _base_context(tmp_path, enhanced_config)

    def fake_link_entities(frame, _config):  # pragma: no cover - triggered in test
        raise RuntimeError("missing dependency")

    def fake_fallback(frame, threshold):
        return frame.assign(fallback=True), []

    def fake_add_scores(frame):
        return frame.assign(priority=True)

    monkeypatch.setattr(
        "hotpass.pipeline.features.entity_resolution.link_entities", fake_link_entities
    )
    monkeypatch.setattr(
        "hotpass.pipeline.features.entity_resolution.resolve_entities_fallback",
        fake_fallback,
    )
    monkeypatch.setattr(
        "hotpass.pipeline.features.entity_resolution.add_ml_priority_scores",
        fake_add_scores,
    )

    result = EntityResolutionFeature().apply(_result(df), context)
    assert result.linkage is None
    assert "fallback" in result.refined.columns
    assert "priority" in result.refined.columns


def test_geospatial_feature_normalizes_addresses(tmp_path, monkeypatch):
    df = pd.DataFrame({"address_primary": ["123 Main"], "country": ["ZA"]})
    enhanced_config = EnhancedPipelineConfig(enable_geospatial=True, geocode_addresses=True)
    context = _base_context(tmp_path, enhanced_config)

    def fake_normalize(value):
        return f"normalized-{value}"

    def fake_geocode(frame, address_column, country_column):
        assert address_column == "address_primary"
        assert country_column == "country"
        return frame.assign(latitude=1.0)

    monkeypatch.setattr("hotpass.pipeline.features.geospatial.normalize_address", fake_normalize)
    monkeypatch.setattr("hotpass.pipeline.features.geospatial.geocode_dataframe", fake_geocode)

    result = GeospatialFeature().apply(_result(df), context)
    assert (result.refined["address_primary"].iloc[0]).startswith("normalized-")
    assert "latitude" in result.refined


def test_enrichment_feature_uses_cache(tmp_path, monkeypatch):
    df = pd.DataFrame({"website": ["https://example.com"]})
    enhanced_config = EnhancedPipelineConfig(
        enable_enrichment=True,
        enrich_websites=True,
        enrichment_concurrency=1,
    )
    context = _base_context(tmp_path, enhanced_config)

    cache_calls: list[str] = []

    class FakeCache:
        def __init__(self, db_path: str) -> None:
            cache_calls.append(db_path)

        def stats(self):
            return {"hits": 1}

    def fake_enrich(frame, website_column, cache):
        assert website_column == "website"
        cache.stats()
        return frame.assign(enriched=True)

    monkeypatch.setattr("hotpass.pipeline.features.enrichment.CacheManager", FakeCache)
    monkeypatch.setattr(
        "hotpass.pipeline.features.enrichment.enrich_dataframe_with_websites",
        fake_enrich,
    )

    result = EnrichmentFeature().apply(_result(df), context)
    assert cache_calls
    assert "enriched" in result.refined.columns


def test_compliance_feature_generates_report(tmp_path, monkeypatch):
    df = pd.DataFrame(
        {
            "organization_slug": ["alpha"],
            "contact_primary_email": ["a@example.com"],
        }
    )
    enhanced_config = EnhancedPipelineConfig(enable_compliance=True, detect_pii=True)
    context = _base_context(tmp_path, enhanced_config)

    def fake_add_provenance(frame, source_name):
        frame["data_source"] = source_name
        return frame

    def fake_detect(frame, columns, threshold):
        frame["pii"] = True
        return frame

    class FakePolicy:
        consent_status_field = "consent_status"

        def generate_compliance_report(self, frame):
            return {"rows": len(frame)}

        def enforce_consent(self, report):
            report["enforced"] = True

    monkeypatch.setattr(
        "hotpass.pipeline.features.compliance.add_provenance_columns",
        fake_add_provenance,
    )
    monkeypatch.setattr("hotpass.pipeline.features.compliance.detect_pii_in_dataframe", fake_detect)
    monkeypatch.setattr("hotpass.pipeline.features.compliance.POPIAPolicy", FakePolicy)

    result = ComplianceFeature().apply(_result(df), context)
    assert result.compliance_report == {"rows": 1, "enforced": True}
    assert "data_source" in result.refined
    assert "pii" in result.refined


def test_default_feature_bundle_order():
    bundle = default_feature_bundle()
    assert [type(feature).__name__ for feature in bundle] == [
        "EntityResolutionFeature",
        "GeospatialFeature",
        "EnrichmentFeature",
        "ComplianceFeature",
    ]
