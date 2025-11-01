"""Regression coverage for the canonical configuration schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from hotpass.compliance import DataClassification
from hotpass.config_schema import (
    ComplianceControls,
    FeatureSwitches,
    GovernanceMetadata,
    HotpassConfig,
    PipelineRuntimeConfig,
)
from pydantic import ValidationError


def test_hotpass_config_to_pipeline_and_enhanced_configs(tmp_path: Path) -> None:
    """Canonical configs should materialise pipeline dataclasses on demand."""

    config = HotpassConfig(
        pipeline=PipelineRuntimeConfig(
            input_dir=tmp_path,
            output_path=tmp_path / "refined.xlsx",
            archive=True,
            expectation_suite="aviation",
            log_format="json",
        ),
        features=FeatureSwitches(
            compliance=True,
            enrichment=True,
            observability=True,
        ),
        governance=GovernanceMetadata(
            intent=["Refine POPIA regulated dataset"],
            data_owner="Data Governance",
            classification=DataClassification.SENSITIVE_PII,
        ),
        compliance=ComplianceControls(
            detect_pii=True,
            audit_log_enabled=True,
            consent_overrides={"acme-flight": "granted"},
        ),
    )

    base_config = config.to_pipeline_config()
    enhanced_config = config.to_enhanced_config()

    assert base_config.input_dir == tmp_path
    assert base_config.output_path == tmp_path / "refined.xlsx"
    assert base_config.expectation_suite_name == "aviation"
    assert base_config.pii_redaction.enabled is True
    assert enhanced_config.enable_compliance is True
    assert enhanced_config.enable_enrichment is True
    assert enhanced_config.detect_pii is True
    assert "Refine POPIA regulated dataset" in enhanced_config.governance_intent
    assert enhanced_config.consent_overrides == {"acme-flight": "granted"}


def test_hotpass_config_requires_governance_intent_when_compliance_enabled() -> None:
    """Compliance toggles should force the caller to declare an explicit intent."""

    with pytest.raises(ValidationError):
        HotpassConfig(
            features=FeatureSwitches(compliance=True),
            governance=GovernanceMetadata(
                intent=[],
                data_owner="Gov",
                classification=DataClassification.CONFIDENTIAL,
            ),
        )
