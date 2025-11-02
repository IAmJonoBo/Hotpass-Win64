---
title: Explanation — data quality strategy
summary: Rationale behind Hotpass validation, enrichment, and compliance capabilities.
last_updated: 2025-11-02
---

The quality programme ensures that the refined dataset is trustworthy and compliant.

## Guiding principles

1. **Coverage first**: Capture as many valid records as possible before applying strict filters.
2. **Transparent remediation**: Provide actionable guidance in the quality report for each failure.
3. **Compliance by default**: Detect POPIA-sensitive information and track provenance to simplify audits.

## Validation lifecycle

- **Pre-ingestion**: Profiles declare required fields and acceptable ranges.
- **In-run checks**: Great Expectations validates completeness, uniqueness, format, and business rules.
- **Post-run reporting**: Markdown and JSON reports summarise findings with severity levels and remediation tips.
- **Regression monitoring**: Prefect and OpenTelemetry metrics flag unusual spikes in failures or runtime.

## Enrichment guardrails

- All external connectors cache responses to avoid rate limiting and to provide traceability.
- Deduplication is deterministic when Splink is unavailable, ensuring consistent fallback behaviour.
- Geospatial enhancements only persist when coordinates meet precision thresholds.

## Compliance controls

- The compliance module tags PII and stores a hashed fingerprint for auditability.
- Contact preferences and unsubscribe flags propagate through the SSOT to downstream systems.
- Provenance metadata lists every source system contributing to a record, supporting right-to-forget workflows.

These controls work together to keep the SSOT reliable while enabling rapid onboarding of new data sources.
