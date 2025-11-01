"""Ensure the compatibility layer re-exports expected feature classes."""

from hotpass.pipeline.features import (
    ComplianceFeature,  # noqa: TID252
    EnhancedPipelineConfig,
    EnrichmentFeature,
)
from hotpass.pipeline_enhancements import (
    ComplianceFeature as ExportedComplianceFeature,
)  # noqa: TID252
from hotpass.pipeline_enhancements import EnhancedPipelineConfig as ExportedEnhancedPipelineConfig
from hotpass.pipeline_enhancements import EnrichmentFeature as ExportedEnrichmentFeature
from hotpass.pipeline_enhancements import __all__ as exported_symbols


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_pipeline_enhancements_reexports_feature_types() -> None:
    expect("ComplianceFeature" in exported_symbols, "Compliance feature should be exported")
    expect("EnhancedPipelineConfig" in exported_symbols, "Config should be exported")
    expect(
        ExportedComplianceFeature is ComplianceFeature,
        "Compliance feature should match source",
    )
    expect(
        ExportedEnhancedPipelineConfig is EnhancedPipelineConfig,
        "Enhanced config should match source",
    )
    expect(
        ExportedEnrichmentFeature is EnrichmentFeature,
        "Enrichment feature should match source",
    )
