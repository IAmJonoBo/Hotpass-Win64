"""Compliance feature strategy."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from pandas import DataFrame

from ...compliance import (
    ConsentValidationError,
    POPIAPolicy,
    add_provenance_columns,
    detect_pii_in_dataframe,
)
from ..base import PipelineResult
from .base import FeatureContext, PipelineFeatureStrategy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ComplianceFeature(PipelineFeatureStrategy):
    """Execute POPIA compliance validation and reporting."""

    name: str = "compliance"

    def is_enabled(self, context: FeatureContext) -> bool:
        return context.enhanced_config.enable_compliance

    def apply(self, result: PipelineResult, context: FeatureContext) -> PipelineResult:
        if not self.is_enabled(context):
            return result

        config = context.enhanced_config
        df: DataFrame = result.refined

        with context.trace_factory(self.name):
            logger.info("Running compliance checks...")
            policy = POPIAPolicy()
            try:
                if config.audit_log_enabled:
                    result.refined = add_provenance_columns(df, source_name="hotpass_pipeline")
                else:
                    result.refined = df

                if config.consent_overrides:
                    _apply_consent_overrides(
                        result.refined,
                        policy.consent_status_field,
                        config.consent_overrides,
                    )

                if config.detect_pii:
                    pii_columns = [
                        "contact_primary_email",
                        "contact_primary_phone",
                        "contact_primary_name",
                    ]
                    result.refined = detect_pii_in_dataframe(
                        result.refined,
                        columns=pii_columns,
                        threshold=0.5,
                    )

                compliance_report = policy.generate_compliance_report(result.refined)
                if config.consent_required:
                    policy.enforce_consent(compliance_report)
                logger.info("Compliance report generated: %s", compliance_report)
                result.compliance_report = compliance_report
            except ConsentValidationError as consent_error:
                logger.error("Consent validation failed: %s", consent_error)
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Compliance checks failed: %s", exc)
        return result


def _apply_consent_overrides(
    df: DataFrame,
    consent_field: str,
    overrides: Mapping[str, str],
) -> None:
    for slug, status in overrides.items():
        mask = df["organization_slug"] == slug
        if mask.any():
            df.loc[mask, consent_field] = status
