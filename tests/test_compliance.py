"""Tests for compliance module."""

from unittest.mock import Mock, patch

import pandas as pd
import pytest

pytest.importorskip("frictionless")

from hotpass.compliance import (
    ConsentValidationError,  # noqa: E402
    DataClassification,
    LawfulBasis,
    PIIDetector,
    PIIRedactionConfig,
    POPIAPolicy,
    add_provenance_columns,
    anonymize_dataframe,
    detect_pii_in_dataframe,
    redact_dataframe,
)

from tests.helpers.assertions import expect  # noqa: E402


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", False)
def test_pii_detector_init_no_presidio():
    """Test PII detector initialization without Presidio."""
    detector = PIIDetector()
    expect(detector.analyzer is None, "Analyzer should be absent when Presidio disabled")
    expect(
        detector.anonymizer is None,
        "Anonymizer should be absent when Presidio disabled",
    )


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
@patch("hotpass.compliance.AnalyzerEngine")
@patch("hotpass.compliance.AnonymizerEngine")
def test_pii_detector_init_with_presidio(mock_anonymizer, mock_analyzer):
    """Test PII detector initialization with Presidio."""
    PIIDetector()
    mock_analyzer.assert_called_once()
    mock_anonymizer.assert_called_once()


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
def test_detect_pii_success():
    """Test successful PII detection."""
    with (
        patch("hotpass.compliance.AnalyzerEngine") as mock_analyzer_class,
        patch("hotpass.compliance.AnonymizerEngine"),
    ):
        # Mock analyzer results
        mock_result = Mock()
        mock_result.entity_type = "EMAIL_ADDRESS"
        mock_result.start = 0
        mock_result.end = 20
        mock_result.score = 0.95

        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = [mock_result]
        mock_analyzer_class.return_value = mock_analyzer

        detector = PIIDetector()
        results = detector.detect_pii("test@example.com")

        expect(len(results) == 1, "Detector should return a single result")
        expect(
            results[0]["entity_type"] == "EMAIL_ADDRESS",
            "Result entity type should match",
        )
        expect(results[0]["score"] == 0.95, "Result score should reflect analyzer output")


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
def test_detect_pii_empty_text():
    """Test PII detection with empty text."""
    with (
        patch("hotpass.compliance.AnalyzerEngine"),
        patch("hotpass.compliance.AnonymizerEngine"),
    ):
        detector = PIIDetector()
        expect(detector.detect_pii("") == [], "Empty text should yield no detections")
        expect(detector.detect_pii(None) == [], "None input should yield no detections")


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
def test_anonymize_text_success():
    """Test successful text anonymization."""
    with (
        patch("hotpass.compliance.AnalyzerEngine") as mock_analyzer_class,
        patch("hotpass.compliance.AnonymizerEngine") as mock_anonymizer_class,
    ):
        # Mock analyzer result
        mock_result = Mock()
        mock_result.entity_type = "EMAIL_ADDRESS"
        mock_result.start = 0
        mock_result.end = 20

        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = [mock_result]
        mock_analyzer_class.return_value = mock_analyzer

        # Mock anonymizer result
        mock_anonymized = Mock()
        mock_anonymized.text = "<EMAIL_ADDRESS>"

        mock_anonymizer = Mock()
        mock_anonymizer.anonymize.return_value = mock_anonymized
        mock_anonymizer_class.return_value = mock_anonymizer

        detector = PIIDetector()
        result = detector.anonymize_text("test@example.com")

        expect(result == "<EMAIL_ADDRESS>", "Anonymization should replace detected PII")


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
def test_anonymize_text_no_pii():
    """Test anonymization with no PII detected."""
    with (
        patch("hotpass.compliance.AnalyzerEngine") as mock_analyzer_class,
        patch("hotpass.compliance.AnonymizerEngine"),
    ):
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = []
        mock_analyzer_class.return_value = mock_analyzer

        detector = PIIDetector()
        result = detector.anonymize_text("Hello world")

        expect(result == "Hello world", "Text without PII should remain unchanged")


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
@patch("hotpass.compliance.PIIDetector")
def test_detect_pii_in_dataframe(mock_detector_class):
    """Test PII detection in dataframe."""
    df = pd.DataFrame(
        {
            "name": ["John Doe", "Jane Smith"],
            "email": ["john@example.com", "jane@example.com"],
        }
    )

    # Mock detector
    mock_detector = Mock()

    # Mock PII detection results
    mock_detector.detect_pii.side_effect = [
        [{"entity_type": "PERSON", "score": 0.9}],
        [{"entity_type": "EMAIL_ADDRESS", "score": 0.95}],
        [{"entity_type": "PERSON", "score": 0.85}],
        [{"entity_type": "EMAIL_ADDRESS", "score": 0.98}],
    ]
    mock_detector.analyzer = Mock()  # Not None so it passes the check
    mock_detector_class.return_value = mock_detector

    result_df = detect_pii_in_dataframe(df, columns=["name", "email"])

    expect("name_has_pii" in result_df.columns, "PII flags should be added for name column")
    expect(
        "email_has_pii" in result_df.columns,
        "PII flags should be added for email column",
    )
    expect(result_df["name_has_pii"].sum() == 2, "Name column should flag both rows")
    expect(result_df["email_has_pii"].sum() == 2, "Email column should flag both rows")


@patch("hotpass.compliance.PIIDetector")
def test_detect_pii_in_dataframe_no_presidio(mock_detector_class):
    """Test PII detection when Presidio is not available."""
    mock_detector = Mock()
    mock_detector.analyzer = None
    mock_detector_class.return_value = mock_detector

    df = pd.DataFrame(
        {
            "name": ["John Doe"],
        }
    )

    result_df = detect_pii_in_dataframe(df)

    # Should return original dataframe
    expect(
        len(result_df.columns) == len(df.columns),
        "When Presidio is unavailable the dataframe is unchanged",
    )


@patch("hotpass.compliance.PRESIDIO_AVAILABLE", True)
@patch("hotpass.compliance.PIIDetector")
def test_anonymize_dataframe(mock_detector_class):
    """Test dataframe anonymization."""
    df = pd.DataFrame(
        {
            "name": ["John Doe", "Jane Smith"],
            "email": ["john@example.com", "jane@example.com"],
        }
    )

    # Mock detector
    mock_detector = Mock()
    mock_detector.anonymizer = Mock()  # Not None so it passes the check
    # Order: name[0], name[1], email[0], email[1]
    mock_detector.anonymize_text.side_effect = [
        "<PERSON>",  # John Doe
        "<PERSON>",  # Jane Smith
        "<EMAIL_ADDRESS>",  # john@example.com
        "<EMAIL_ADDRESS>",  # jane@example.com
    ]
    mock_detector_class.return_value = mock_detector

    result_df = anonymize_dataframe(df, columns=["name", "email"])

    expect(
        result_df.loc[0, "name"] == "<PERSON>",
        "Name should be replaced with anonymized value",
    )
    expect(
        result_df.loc[0, "email"] == "<EMAIL_ADDRESS>",
        "Email should be replaced with anonymized value",
    )


@patch("hotpass.compliance.PIIDetector")
def test_redact_dataframe_captures_events(mock_detector_class):
    """Redaction should replace values and emit metadata events."""
    df = pd.DataFrame({"email": ["john@example.com", "clean"]})

    mock_detector = Mock()
    mock_detector.analyzer = Mock()
    mock_detector.anonymizer = Mock()
    mock_detector.detect_pii.side_effect = [
        [{"entity_type": "EMAIL_ADDRESS", "score": 0.91, "text": "john@example.com"}],
        [],
    ]
    mock_detector.anonymize_text.return_value = "<EMAIL_ADDRESS>"
    mock_detector_class.return_value = mock_detector

    config = PIIRedactionConfig(columns=("email",), capture_entity_scores=True)
    redacted, events = redact_dataframe(df, config)

    expect(redacted.loc[0, "email"] == "<EMAIL_ADDRESS>", "PII should be redacted")
    expect(redacted.loc[1, "email"] == "clean", "Non-PII should remain untouched")
    expect(
        bool(events),
        "Redaction should emit provenance events",
    )
    expect(
        events[0]["entities"][0]["entity_type"] == "EMAIL_ADDRESS",
        "Event entity type should match",
    )
    expect(
        events[0]["entities"][0]["score"] == pytest.approx(0.91, rel=1e-3),
        "Score should match detector output",
    )


def test_redact_dataframe_disabled():
    """Disabled configuration returns original dataframe and no events."""
    df = pd.DataFrame({"email": ["john@example.com"]})
    config = PIIRedactionConfig(enabled=False)
    redacted, events = redact_dataframe(df, config)

    pd.testing.assert_frame_equal(redacted, df)
    expect(events == [], "Redaction disabled should emit no events")


def test_data_classification_enum():
    """Test DataClassification enum."""
    expect(DataClassification.PUBLIC.value == "public", "Classification enum mismatch")
    expect(DataClassification.PII.value == "pii", "Classification enum mismatch")
    expect(
        DataClassification.SENSITIVE_PII.value == "sensitive_pii",
        "Classification enum mismatch",
    )


def test_lawful_basis_enum():
    """Test LawfulBasis enum."""
    expect(LawfulBasis.CONSENT.value == "consent", "Lawful basis enum mismatch")
    expect(
        LawfulBasis.LEGITIMATE_INTEREST.value == "legitimate_interest",
        "Lawful basis enum mismatch",
    )


def test_popia_policy_init():
    """Test POPIA policy initialization."""
    config = {
        "field_classifications": {
            "email": "pii",
        },
        "retention_policies": {
            "email": 730,
        },
    }

    policy = POPIAPolicy(config)

    expect(policy.config == config, "Policy should retain config payload")
    expect(policy.field_classifications["email"] == "pii", "Field classification mismatch")


def test_popia_policy_classify_field():
    """Test field classification."""
    config = {
        "field_classifications": {
            "email": "pii",
        },
    }

    policy = POPIAPolicy(config)

    expect(
        policy.classify_field("email") == DataClassification.PII,
        "Classification should map to PII",
    )
    expect(
        policy.classify_field("unknown") == DataClassification.INTERNAL,
        "Unknown fields default to internal",
    )


def test_popia_policy_retention_period():
    """Test retention period retrieval."""
    config = {
        "retention_policies": {
            "email": 730,
        },
    }

    policy = POPIAPolicy(config)

    expect(
        policy.get_retention_period("email") == 730,
        "Retention should resolve to configured value",
    )
    expect(
        policy.get_retention_period("unknown") is None,
        "Unknown retention should be None",
    )


def test_popia_policy_consent_requirements():
    """Test consent requirements."""
    config = {
        "consent_requirements": {
            "email": True,
        },
    }

    policy = POPIAPolicy(config)

    expect(
        policy.requires_consent("email") is True,
        "Consent requirement should match config",
    )
    expect(
        policy.requires_consent("unknown") is False,
        "Non-configured fields should not require consent",
    )


def test_popia_policy_generate_report():
    """Test compliance report generation."""
    config = {
        "field_classifications": {
            "email": "pii",
            "name": "pii",
        },
        "retention_policies": {
            "email": 730,
        },
        "consent_requirements": {
            "email": True,
        },
    }

    df = pd.DataFrame(
        {
            "email": ["test@example.com"],
            "name": ["John Doe"],
            "city": ["New York"],
            "consent_status": ["granted"],
        }
    )

    policy = POPIAPolicy(config)
    report = policy.generate_compliance_report(df)

    expect(report["total_fields"] == 4, "Report should include field count")
    expect(report["total_records"] == 1, "Report should include record count")
    expect("email" in report["pii_fields"], "PII fields should include email")
    expect(
        "email" in report["consent_required_fields"],
        "Consent-required fields should include email",
    )
    expect(
        report["retention_policies"]["email"] == 730,
        "Retention policy should propagate",
    )
    expect(
        report["consent_status_summary"]["granted"] == 1,
        "Consent summary should count granted entries",
    )
    expect(report["consent_violations"] == [], "No consent violations expected")

    policy.enforce_consent(report)


def test_popia_policy_report_compliance_issues():
    """Test compliance issue detection in report."""
    config = {
        "field_classifications": {
            "email": "pii",
        },
    }

    df = pd.DataFrame(
        {
            "email": ["test@example.com"],
        }
    )

    policy = POPIAPolicy(config)
    report = policy.generate_compliance_report(df)

    # Should have issues because no consent requirements or retention policies
    expect(len(report["compliance_issues"]) > 0, "Planned consent test should flag issues")


def test_popia_policy_reports_consent_violation():
    """Consent enforcement should flag rows without granted status."""
    config = {
        "consent_requirements": {"email": True},
    }

    df = pd.DataFrame({"email": ["test@example.com"], "consent_status": ["pending"]})

    policy = POPIAPolicy(config)
    report = policy.generate_compliance_report(df)

    expect(report["consent_violations"], "Violations should be recorded")
    with pytest.raises(ConsentValidationError):
        policy.enforce_consent(report)


def test_popia_policy_enforce_consent_allows_granted_status():
    """Consent enforcement should allow granted statuses."""
    config = {
        "consent_requirements": {"email": True},
    }

    df = pd.DataFrame({"email": ["test@example.com"], "consent_status": ["granted"]})

    policy = POPIAPolicy(config)
    report = policy.generate_compliance_report(df)

    expect(report["consent_violations"] == [], "No consent violations when consent granted")
    policy.enforce_consent(report)


def test_add_provenance_columns():
    """Test adding provenance columns."""
    df = pd.DataFrame(
        {
            "name": ["John Doe"],
            "email": ["john@example.com"],
        }
    )

    result_df = add_provenance_columns(df, source_name="Test Source")

    expect("data_source" in result_df.columns, "Data source column should be added")
    expect("processed_at" in result_df.columns, "Processed timestamp should be added")
    expect("consent_status" in result_df.columns, "Consent status column should be added")
    expect(result_df.loc[0, "data_source"] == "Test Source", "Data source value mismatch")


def test_add_provenance_columns_preserves_existing_consent():
    """Existing consent fields remain intact when provenance is added."""
    df = pd.DataFrame(
        {
            "name": ["Jane"],
            "consent_status": ["granted"],
            "consent_date": ["2025-10-01"],
        }
    )

    result_df = add_provenance_columns(df, source_name="Test Source")

    expect(result_df.loc[0, "consent_status"] == "granted", "Consent status value mismatch")
    expect(result_df.loc[0, "consent_date"] == "2025-10-01", "Consent date mismatch")


def test_add_provenance_columns_with_timestamp():
    """Test adding provenance columns with custom timestamp."""
    df = pd.DataFrame(
        {
            "name": ["John Doe"],
        }
    )

    timestamp = "2025-01-01T00:00:00"
    result_df = add_provenance_columns(df, source_name="Test", processing_timestamp=timestamp)

    expect(result_df.loc[0, "processed_at"] == timestamp, "Processed timestamp mismatch")
