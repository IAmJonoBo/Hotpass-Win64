"""Compliance and data protection module.

This module provides functionality for:
- PII (Personally Identifiable Information) detection
- Data redaction and anonymization
- POPIA (Protection of Personal Information Act) compliance
- Consent and provenance tracking
- Compliance reporting
"""

import logging
import os
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, cast

import pandas as pd

logger = logging.getLogger(__name__)


class AnalyzerResultProtocol(Protocol):
    entity_type: str
    start: int
    end: int
    score: float


class AnalyzerProtocol(Protocol):
    def analyze(
        self,
        *,
        text: str,
        language: str,
        score_threshold: float | None = ...,
    ) -> Sequence[AnalyzerResultProtocol]:
        """Return detected entities for a text payload."""


class AnonymizeResultProtocol(Protocol):
    text: str


class AnonymizerProtocol(Protocol):
    def anonymize(
        self,
        *,
        text: str,
        analyzer_results: Sequence[AnalyzerResultProtocol],
        operators: Mapping[str, Any],
    ) -> AnonymizeResultProtocol:
        """Return anonymised text when given analyzer outputs."""


AnalyzerFactory = Callable[..., AnalyzerProtocol]
AnonymizerFactory = Callable[..., AnonymizerProtocol]
OperatorFactory = Callable[..., Any]

# Runtime references that degrade gracefully when Presidio is unavailable. The
# explicit annotations avoid mypy "Cannot assign to a type" errors when we
# replace the imported classes with fallback implementations.
AnalyzerEngine: AnalyzerFactory | None
AnonymizerEngine: AnonymizerFactory | None
OperatorConfig: OperatorFactory
PRESIDIO_AVAILABLE: bool

try:
    from presidio_analyzer import AnalyzerEngine as _AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine as _AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig as _OperatorConfig

    AnalyzerEngine = cast(AnalyzerFactory, _AnalyzerEngine)
    AnonymizerEngine = cast(AnonymizerFactory, _AnonymizerEngine)
    OperatorConfig = cast(OperatorFactory, _OperatorConfig)
    PRESIDIO_AVAILABLE = True
except ImportError:

    class _OperatorConfigStub:  # pragma: no cover - only used when Presidio missing
        """Fallback operator config when Presidio is unavailable."""

        def __init__(self, operation: str, params: Mapping[str, Any] | None = None) -> None:
            self.operation = operation
            self.params = dict(params or {})

    AnalyzerEngine = None
    AnonymizerEngine = None
    OperatorConfig = cast(OperatorFactory, _OperatorConfigStub)
    PRESIDIO_AVAILABLE = False

if os.getenv("HOTPASS_ENABLE_PRESIDIO", "0") not in {"1", "true", "TRUE"}:
    PRESIDIO_AVAILABLE = False


DEFAULT_REDACTION_COLUMNS: tuple[str, ...] = (
    "contact_primary_name",
    "contact_primary_email",
    "contact_primary_phone",
    "contact_secondary_emails",
    "contact_secondary_phones",
    "notes",
    "description",
)


@dataclass(slots=True)
class PIIRedactionConfig:
    """Configuration controlling Presidio-powered redaction flows."""

    enabled: bool = True
    columns: tuple[str, ...] = DEFAULT_REDACTION_COLUMNS
    language: str = "en"
    score_threshold: float = 0.5
    operator: str = "redact"
    operator_params: Mapping[str, Any] | None = None
    capture_entity_scores: bool = True

    def iter_columns(self, frame: pd.DataFrame) -> Iterable[str]:
        """Yield configured columns that are present on the dataframe."""

        for column in self.columns:
            if column in frame.columns:
                yield column


class ConsentValidationError(RuntimeError):
    """Raised when consent validation fails for regulated fields."""

    def __init__(self, message: str, violations: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.violations = violations or []


class DataClassification(Enum):
    """Data classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"
    SENSITIVE_PII = "sensitive_pii"


class LawfulBasis(Enum):
    """Lawful basis for processing under POPIA."""

    CONSENT = "consent"
    LEGITIMATE_INTEREST = "legitimate_interest"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_INTEREST = "public_interest"


class PIIDetector:
    """PII detection service using Presidio."""

    def __init__(self) -> None:
        """Initialize PII detector."""

        self.analyzer: AnalyzerProtocol | None = None
        self.anonymizer: AnonymizerProtocol | None = None

        analyzer_factory = AnalyzerEngine
        anonymizer_factory = AnonymizerEngine

        if not PRESIDIO_AVAILABLE or analyzer_factory is None or anonymizer_factory is None:
            logger.info("PII detection disabled (enable via HOTPASS_ENABLE_PRESIDIO=1)")
            return

        try:
            self.analyzer = analyzer_factory()
            self.anonymizer = anonymizer_factory()
        except Exception as exc:  # pragma: no cover - defensive initialisation
            logger.warning("Failed to initialise Presidio engines: %s", exc)
            self.analyzer = None
            self.anonymizer = None

    def detect_pii(
        self, text: str | None, language: str = "en", threshold: float = 0.5
    ) -> list[dict[str, Any]]:
        """Detect PII entities in text.

        Args:
            text: Text to analyze
            language: Language code
            threshold: Confidence threshold (0-1)

        Returns:
            List of detected PII entities
        """
        if not self.analyzer:
            logger.warning("PII analyzer not initialized")
            return []

        if not text or pd.isna(text):
            return []

        try:
            results = self.analyzer.analyze(text=text, language=language, score_threshold=threshold)

            return [
                {
                    "entity_type": result.entity_type,
                    "start": result.start,
                    "end": result.end,
                    "score": result.score,
                    "text": text[result.start : result.end],
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error detecting PII: {e}")
            return []

    def anonymize_text(
        self,
        text: str,
        operation: str = "replace",
        language: str = "en",
        operator_params: Mapping[str, Any] | None = None,
    ) -> str:
        """Anonymize PII in text.

        Args:
            text: Text to anonymize
            operation: Anonymization operation (replace, redact, hash, mask)
            language: Language code

        Returns:
            Anonymized text
        """
        if not self.analyzer or not self.anonymizer:
            logger.warning("PII anonymizer not initialized")
            return text

        if not text or pd.isna(text):
            return text

        try:
            # Detect PII
            results = self.analyzer.analyze(text=text, language=language)

            if not results:
                return text

            # Anonymize
            operator = OperatorConfig(operation, operator_params or {})
            anonymized = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators={"DEFAULT": operator},
            )

            return anonymized.text

        except Exception as e:
            logger.error(f"Error anonymizing text: {e}")
            return text


def detect_pii_in_dataframe(
    df: pd.DataFrame, columns: list[str] | None = None, threshold: float = 0.5
) -> pd.DataFrame:
    """Detect PII in dataframe columns.

    Args:
        df: Input dataframe
        columns: Columns to check (if None, check all string columns)
        threshold: Detection confidence threshold

    Returns:
        Dataframe with PII detection results
    """
    detector = PIIDetector()

    if not detector.analyzer:
        logger.warning("PII detection not available")
        return df

    # Determine columns to check
    if columns is None:
        columns = df.select_dtypes(include=["object"]).columns.tolist()

    result_df = df.copy()

    # Add PII flag columns
    for col in columns:
        pii_col = f"{col}_has_pii"
        pii_types_col = f"{col}_pii_types"

        result_df[pii_col] = False
        result_df[pii_types_col] = None

        for idx, value in df[col].items():
            if pd.isna(value) or not value:
                continue

            pii_entities = detector.detect_pii(str(value), threshold=threshold)

            if pii_entities:
                result_df.at[idx, pii_col] = True
                result_df.at[idx, pii_types_col] = ",".join(
                    sorted(set(e["entity_type"] for e in pii_entities))
                )

    total_pii = sum(result_df[f"{col}_has_pii"].sum() for col in columns)
    logger.info(f"Detected PII in {total_pii} cells across {len(columns)} columns")

    return result_df


def anonymize_dataframe(
    df: pd.DataFrame, columns: list[str] | None = None, operation: str = "replace"
) -> pd.DataFrame:
    """Anonymize PII in dataframe columns.

    Args:
        df: Input dataframe
        columns: Columns to anonymize (if None, anonymize all string columns)
        operation: Anonymization operation (replace, redact, hash, mask)

    Returns:
        Dataframe with anonymized data
    """
    detector = PIIDetector()

    if not detector.anonymizer:
        logger.warning("PII anonymization not available")
        return df

    # Determine columns to anonymize
    if columns is None:
        columns = df.select_dtypes(include=["object"]).columns.tolist()

    result_df = df.copy()

    # Anonymize each column
    anonymized_count = 0
    for col in columns:
        for idx, value in df[col].items():
            if pd.isna(value) or not value:
                continue

            anonymized = detector.anonymize_text(str(value), operation=operation)

            if anonymized != str(value):
                result_df.at[idx, col] = anonymized
                anonymized_count += 1

    logger.info(f"Anonymized {anonymized_count} cells across {len(columns)} columns")

    return result_df


def _summarise_entities(
    entities: Iterable[Mapping[str, Any]],
    *,
    include_scores: bool,
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for entity in entities:
        entity_type = entity.get("entity_type", "UNKNOWN")
        item: dict[str, Any] = {"entity_type": entity_type}
        if include_scores and "score" in entity:
            try:
                item["score"] = round(float(entity["score"]), 4)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                pass
        summary.append(item)
    return summary


def redact_dataframe(
    df: pd.DataFrame,
    config: PIIRedactionConfig | None = None,
    *,
    detector: PIIDetector | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Redact PII from a dataframe and emit structured metadata."""

    if config is None or not config.enabled:
        return df, []

    detector = detector or PIIDetector()
    if not detector.analyzer or not detector.anonymizer:
        logger.warning("PII redaction unavailable; returning original dataframe")
        return df, []

    result_df = df.copy()
    events: list[dict[str, Any]] = []

    for column in config.iter_columns(df):
        for row_index, raw_value in df[column].items():
            if pd.isna(raw_value) or raw_value in {"", None}:
                continue

            if isinstance(raw_value, list | tuple):
                updated_values = list(raw_value)
                for value_index, item in enumerate(raw_value):
                    if item in {None, ""}:
                        continue
                    text = str(item)
                    entities = detector.detect_pii(
                        text,
                        language=config.language,
                        threshold=config.score_threshold,
                    )
                    if not entities:
                        continue
                    anonymized = detector.anonymize_text(
                        text,
                        operation=config.operator,
                        language=config.language,
                        operator_params=config.operator_params,
                    )
                    updated_values[value_index] = anonymized
                    events.append(
                        {
                            "row_index": row_index,
                            "column": column,
                            "value_index": value_index,
                            "entities": _summarise_entities(
                                entities, include_scores=config.capture_entity_scores
                            ),
                        }
                    )
                if updated_values != list(raw_value):
                    result_df.at[row_index, column] = updated_values
                continue

            text_value = str(raw_value)
            if not text_value.strip():
                continue

            entities = detector.detect_pii(
                text_value,
                language=config.language,
                threshold=config.score_threshold,
            )
            if not entities:
                continue

            anonymized = detector.anonymize_text(
                text_value,
                operation=config.operator,
                language=config.language,
                operator_params=config.operator_params,
            )
            if anonymized != text_value:
                result_df.at[row_index, column] = anonymized
            events.append(
                {
                    "row_index": row_index,
                    "column": column,
                    "value_index": None,
                    "entities": _summarise_entities(
                        entities, include_scores=config.capture_entity_scores
                    ),
                }
            )

    if events:
        logger.info(
            "Redacted %s values across %s columns",
            len(events),
            len(list(config.iter_columns(df))),
        )

    return result_df, events


class POPIAPolicy:
    """POPIA compliance policy manager."""

    def __init__(self, policy_config: dict[str, Any] | None = None):
        """Initialize POPIA policy.

        Args:
            policy_config: Policy configuration dictionary
        """
        self.config = dict(policy_config or {})

        raw_field_classifications = self.config.get("field_classifications", {})
        self.field_classifications: dict[str, Any] = dict(
            cast(Mapping[str, Any], raw_field_classifications)
        )

        raw_retention = self.config.get("retention_policies", {})
        self.retention_policies: dict[str, int] = (
            dict(cast(Mapping[str, int], raw_retention))
            if isinstance(raw_retention, Mapping)
            else {}
        )

        raw_consent_requirements = self.config.get("consent_requirements", {})
        self.consent_requirements: dict[str, bool] = (
            dict(cast(Mapping[str, bool], raw_consent_requirements))
            if isinstance(raw_consent_requirements, Mapping)
            else {}
        )

        if not self.consent_requirements:
            self.consent_requirements = {
                "contact_primary_email": True,
                "contact_primary_phone": True,
                "contact_primary_name": True,
            }
        self.consent_status_field = self.config.get("consent_status_field", "consent_status")
        self.consent_granted_statuses = {
            status.lower()
            for status in self.config.get(
                "consent_granted_statuses",
                ["granted", "approved", "allowed"],
            )
        }
        self.consent_pending_statuses = {
            status.lower()
            for status in self.config.get(
                "consent_pending_statuses",
                ["pending", "unknown", "review"],
            )
        }
        self.consent_denied_statuses = {
            status.lower()
            for status in self.config.get(
                "consent_denied_statuses",
                ["revoked", "denied", "withdrawn", "expired"],
            )
        }

    def classify_field(self, field_name: str) -> DataClassification:
        """Get classification for a field.

        Args:
            field_name: Field name

        Returns:
            Data classification level
        """
        classification = self.field_classifications.get(
            field_name, DataClassification.INTERNAL.value
        )
        return DataClassification(classification)

    def get_retention_period(self, field_name: str) -> int | None:
        """Get retention period for a field in days.

        Args:
            field_name: Field name

        Returns:
            Retention period in days, or None if not specified
        """
        if field_name in self.retention_policies:
            return self.retention_policies[field_name]
        return None

    def requires_consent(self, field_name: str) -> bool:
        """Check if field requires explicit consent.

        Args:
            field_name: Field name

        Returns:
            True if consent is required
        """
        if field_name in self.consent_requirements:
            return self.consent_requirements[field_name]
        return False

    def get_lawful_basis(self, field_name: str) -> LawfulBasis | None:
        """Get lawful basis for processing a field.

        Args:
            field_name: Field name

        Returns:
            Lawful basis for processing
        """
        basis = self.field_classifications.get(field_name, {}).get("lawful_basis")
        return LawfulBasis(basis) if basis else None

    def generate_compliance_report(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate POPIA compliance report for a dataframe.

        Args:
            df: Dataframe to analyze

        Returns:
            Compliance report dictionary
        """
        pii_fields: list[str] = []
        consent_required_fields: list[str] = []
        retention_policies: dict[str, int] = {}
        compliance_issues: list[str] = []
        field_classifications: dict[str, str] = {}
        consent_status_summary: Counter[str] = Counter()
        consent_violations: list[dict[str, Any]] = []

        # Analyze each field
        for col in df.columns:
            classification = self.classify_field(str(col))
            field_classifications[str(col)] = classification.value

            if classification in [
                DataClassification.PII,
                DataClassification.SENSITIVE_PII,
            ]:
                pii_fields.append(str(col))

            if self.requires_consent(str(col)):
                consent_required_fields.append(str(col))

            retention = self.get_retention_period(str(col))
            if retention:
                retention_policies[str(col)] = retention

        # Check for compliance issues
        if pii_fields and not consent_required_fields:
            compliance_issues.append("PII fields present but no consent requirements configured")

        if not retention_policies:
            compliance_issues.append("No retention policies configured for any fields")

        consent_status_field = self.consent_status_field
        if consent_required_fields:
            if consent_status_field not in df.columns:
                compliance_issues.append(
                    f"Consent status field '{consent_status_field}' missing from dataset"
                )
                logger.error(
                    "Consent status column '%s' missing while consent is required",
                    consent_status_field,
                )
            else:
                for index, row in df.iterrows():
                    applicable_fields = [
                        field
                        for field in consent_required_fields
                        if field in df.columns and self._value_requires_consent(row.get(field))
                    ]

                    if not applicable_fields:
                        continue

                    status_value = row.get(consent_status_field)
                    status = self._normalise_consent_status(status_value)
                    if status:
                        consent_status_summary[status] += 1
                    else:
                        consent_status_summary["untracked"] += 1

                    violation_reason = self._classify_consent_status(status)
                    if violation_reason:
                        consent_violations.append(
                            {
                                "row_index": int(index),
                                "fields": applicable_fields,
                                "status": status or None,
                                "reason": violation_reason,
                            }
                        )

        if consent_violations:
            compliance_issues.append(
                f"{len(consent_violations)} records require consent without a granted status"
            )
            logger.error("Detected %s consent validation violations", len(consent_violations))

        return {
            "generated_at": datetime.now().isoformat(),
            "total_fields": len(df.columns),
            "total_records": len(df),
            "field_classifications": field_classifications,
            "pii_fields": pii_fields,
            "consent_required_fields": consent_required_fields,
            "retention_policies": retention_policies,
            "compliance_issues": compliance_issues,
            "consent_status_field": consent_status_field,
            "consent_status_summary": dict(consent_status_summary),
            "consent_violations": consent_violations,
        }

    def enforce_consent(self, report: dict[str, Any]) -> None:
        """Raise an error when consent violations are present."""

        violations = report.get("consent_violations", [])
        if violations:
            raise ConsentValidationError(
                f"{len(violations)} records require consent but consent is not granted",
                violations=violations,
            )

    @staticmethod
    def _value_requires_consent(value: Any) -> bool:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    @staticmethod
    def _normalise_consent_status(status: Any) -> str | None:
        if status is None or (isinstance(status, float) and pd.isna(status)):
            return None
        text = str(status).strip().lower()
        return text or None

    def _classify_consent_status(self, status: str | None) -> str | None:
        if status is None:
            return "missing"
        if status in self.consent_granted_statuses:
            return None
        if status in self.consent_pending_statuses:
            return "pending"
        if status in self.consent_denied_statuses:
            return "denied"
        return "unknown"


def add_provenance_columns(
    df: pd.DataFrame, source_name: str, processing_timestamp: str | None = None
) -> pd.DataFrame:
    """Add provenance tracking columns to dataframe.

    Args:
        df: Input dataframe
        source_name: Name of the data source
        processing_timestamp: Optional timestamp (ISO format)

    Returns:
        Dataframe with provenance columns
    """
    enriched_df = df.copy()

    # Add provenance columns
    enriched_df["data_source"] = source_name
    enriched_df["processed_at"] = processing_timestamp or datetime.now().isoformat()
    if "consent_status" in enriched_df.columns:
        enriched_df["consent_status"] = (
            enriched_df["consent_status"].fillna("pending").replace("", "pending")
        )
    else:
        enriched_df["consent_status"] = "pending"  # Default status
    if "consent_date" not in enriched_df.columns:
        enriched_df["consent_date"] = None
    enriched_df["retention_until"] = None  # To be calculated based on policy

    logger.info("Added provenance columns for source: %s", source_name)

    return enriched_df
