"""Tests for quality validation functionality."""

import pandas as pd
import pytest

pytest.importorskip("frictionless")

from hotpass.quality import (
    ExpectationSummary,  # noqa: E402
    _run_with_great_expectations,
    build_ssot_schema,
    run_expectations,
)

try:
    from great_expectations.validator.validator import Validator  # noqa: F401

    HAS_GE = True
except ImportError:
    HAS_GE = False


def _with_validation_defaults(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    length = len(df)
    defaults = {
        "contact_primary_email_confidence": None,
        "contact_primary_email_status": None,
        "contact_primary_phone_confidence": None,
        "contact_primary_phone_status": None,
        "contact_primary_lead_score": None,
        "contact_validation_flags": None,
        "contact_email_confidence_avg": None,
        "contact_phone_confidence_avg": None,
        "contact_verification_score_avg": None,
        "contact_lead_score_avg": None,
    }
    for column, value in defaults.items():
        if column not in df.columns:
            df[column] = [value] * length
    return df


def test_build_ssot_schema():
    """Test that SSOT schema is created correctly."""
    schema = build_ssot_schema()

    assert schema is not None
    assert "organization_name" in schema.columns
    assert "organization_slug" in schema.columns
    assert "data_quality_score" in schema.columns

    # Organization name should not be nullable
    assert not schema.columns["organization_name"].nullable
    assert not schema.columns["organization_slug"].nullable


def test_ssot_schema_validates_valid_data():
    """Test that SSOT schema validates correct data."""
    schema = build_ssot_schema()

    valid_df = pd.DataFrame(
        {
            "organization_name": ["Test Org"],
            "organization_slug": ["test-org"],
            "province": ["Western Cape"],
            "country": ["South Africa"],
            "area": ["Cape Town"],
            "address_primary": ["123 Main St"],
            "organization_category": ["Flight School"],
            "organization_type": ["Active"],
            "status": ["Active"],
            "website": ["https://test.com"],
            "planes": ["Cessna 172"],
            "description": ["Test description"],
            "notes": ["Test notes"],
            "source_datasets": ["SACAA"],
            "source_record_ids": ["123"],
            "contact_primary_name": ["John Doe"],
            "contact_primary_role": ["Manager"],
            "contact_primary_email": ["john@test.com"],
            "contact_primary_phone": ["+27123456789"],
            "contact_secondary_emails": ["jane@test.com"],
            "contact_secondary_phones": ["+27987654321"],
            "data_quality_score": [0.85],
            "data_quality_flags": [""],
            "selection_provenance": ["SACAA"],
            "last_interaction_date": ["2024-01-01"],
            "priority": ["High"],
            "privacy_basis": ["Legitimate Interest"],
        }
    )
    valid_df = _with_validation_defaults(valid_df)

    # Should not raise an error
    validated = schema.validate(valid_df)
    assert len(validated) == 1


def test_run_expectations_with_valid_data():
    """Test run_expectations with valid data."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-org-1", "test-org-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert isinstance(result, ExpectationSummary)
    assert result.success is True
    assert len(result.failures) == 0


def test_run_expectations_with_missing_org_name():
    """Test run_expectations detects missing organization names."""
    df = pd.DataFrame(
        {
            "organization_name": [None, "Test Org"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert result.success is False
    assert any("organization_name" in str(f) for f in result.failures)


def test_run_expectations_with_invalid_quality_score():
    """Test run_expectations detects invalid quality scores."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org"],
            "organization_slug": ["test-org"],
            "country": ["South Africa"],
            "data_quality_score": [1.5],  # Invalid: > 1.0
            "contact_primary_email": ["test@example.com"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://test.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert result.success is False
    assert any("quality_score" in str(f).lower() for f in result.failures)


def test_run_expectations_with_invalid_email_format():
    """Test run_expectations detects invalid email formats."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2", "Test Org 3"],
            "organization_slug": ["test-1", "test-2", "test-3"],
            "country": ["South Africa", "South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9, 0.7],
            "contact_primary_email": [
                "invalid-email",  # Invalid
                "test@example.com",  # Valid
                "another@test.com",  # Valid
            ],
            "contact_primary_phone": ["+271234", "+272345", "+273456"],
            "website": ["https://test1.com", "https://test2.com", "https://test3.com"],
        }
    )
    df = _with_validation_defaults(df)

    # With default threshold of 0.85, 2/3 valid (66%) should fail
    result = run_expectations(df, email_mostly=0.85)

    assert result.success is False
    assert any("email" in str(f).lower() for f in result.failures)


def test_run_expectations_with_custom_thresholds():
    """Test run_expectations with custom validation thresholds."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": [
                "test1@example.com",  # Valid
                "invalid",  # Invalid
            ],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    # With 50% threshold, 1/2 valid should pass
    result = run_expectations(df, email_mostly=0.5)

    assert result.success is True


def test_run_expectations_with_blank_emails():
    """Test that blank emails are sanitized before validation."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2", "Test Org 3"],
            "organization_slug": ["test-1", "test-2", "test-3"],
            "country": ["South Africa", "South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9, 0.7],
            "contact_primary_email": [
                "test@example.com",  # Valid
                "",  # Blank - should be treated as NA
                "another@test.com",  # Valid
            ],
            "contact_primary_phone": ["+271234", "+272345", "+273456"],
            "website": ["https://test1.com", "https://test2.com", "https://test3.com"],
        }
    )
    df = _with_validation_defaults(df)

    # Blank should be ignored, so 2/2 non-blank should be valid (100%)
    result = run_expectations(df, email_mostly=0.85)

    # Should pass since blanks are excluded
    assert result.success is True


def test_run_expectations_with_invalid_phone_format():
    """Test run_expectations detects invalid phone formats."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": [
                "123456",  # Invalid: no +
                "+27123456789",  # Valid
            ],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)
    df = _with_validation_defaults(df)

    # With default threshold of 0.85, 1/2 valid (50%) should fail
    result = run_expectations(df, phone_mostly=0.85)

    assert result.success is False
    assert any("phone" in str(f).lower() for f in result.failures)


def test_run_expectations_with_invalid_website_format():
    """Test run_expectations detects invalid website formats."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": [
                "www.test.com",  # Invalid: no https://
                "https://test2.com",  # Valid
            ],
        }
    )
    df = _with_validation_defaults(df)
    df = _with_validation_defaults(df)

    # With default threshold of 0.85, 1/2 valid (50%) should fail
    result = run_expectations(df, website_mostly=0.85)

    assert result.success is False
    assert any("website" in str(f).lower() for f in result.failures)


def test_run_expectations_with_wrong_country():
    """Test run_expectations detects wrong country values."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org"],
            "organization_slug": ["test-org"],
            "country": ["United States"],  # Wrong country
            "data_quality_score": [0.8],
            "contact_primary_email": ["test@example.com"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://test.com"],
        }
    )
    df = _with_validation_defaults(df)
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert result.success is False
    assert any("country" in str(f).lower() for f in result.failures)


def test_run_expectations_with_empty_dataframe():
    """Test run_expectations handles empty DataFrame."""
    df = pd.DataFrame(
        {
            "organization_name": [],
            "organization_slug": [],
            "country": [],
            "data_quality_score": [],
            "contact_primary_email": [],
            "contact_primary_phone": [],
            "website": [],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert isinstance(result, ExpectationSummary)
    # Empty df should pass contact format checks (no data to validate)
    # But may fail other checks
    assert isinstance(result.success, bool)


def test_run_expectations_with_all_na_emails():
    """Test run_expectations when all emails are NA."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": [None, None],  # All NA
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    # Should pass email check since all are NA (no non-null values to validate)
    assert isinstance(result, ExpectationSummary)


def test_expectation_summary_structure():
    """Test ExpectationSummary dataclass structure."""
    summary = ExpectationSummary(success=True, failures=[])

    assert summary.success is True
    assert summary.failures == []

    summary2 = ExpectationSummary(success=False, failures=["error1", "error2"])

    assert summary2.success is False
    assert len(summary2.failures) == 2


class _StubProjectManager:
    def __init__(self) -> None:
        self.current_project: object = "previous_project"
        self.set_history: list[object] = []

    def get_project(self) -> object:
        return self.current_project

    def set_project(self, project: object) -> None:
        self.set_history.append(project)
        self.current_project = project


def _make_stub_ge_runtime(
    *,
    fail_on_validate: bool = False,
) -> tuple[dict[str, object], _StubProjectManager]:
    class _StubStoreDefaults:
        def __init__(self, *, init_temp_docs_sites: bool) -> None:
            self.init_temp_docs_sites = init_temp_docs_sites

    class _StubDataContextConfig:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class _StubDataContext:
        def __init__(self, project_config: object) -> None:
            self.project_config = project_config

    class _StubBatch:
        def __init__(self, data: pd.DataFrame) -> None:
            self.data = data

    class _StubExpectationSuite:
        def __init__(self, name: str) -> None:
            self.name = name

    class _StubExecutionEngine:
        pass

    class _StubExpectationResult:
        def __init__(
            self,
            success: bool,
            expectation_config: dict[str, object],
            result: dict[str, object],
        ) -> None:
            self.success = success
            self.expectation_config = expectation_config
            self.result = result

    class _StubValidation:
        def __init__(self, results: list[_StubExpectationResult], success: bool) -> None:
            self.results = results
            self.success = success

    project_manager = _StubProjectManager()

    class _StubValidator:
        def __init__(
            self,
            *,
            execution_engine: object,
            expectation_suite: _StubExpectationSuite,
            batches: list[_StubBatch],
            data_context: _StubDataContext,
        ) -> None:
            self.execution_engine = execution_engine
            self.expectation_suite = expectation_suite
            self.batches = batches
            self.data_context = data_context
            self.default_expectation_arguments: dict[str, object] = {}
            self.expectation_calls: list[object] = []

        def set_default_expectation_argument(self, name: str, value: object) -> None:
            self.default_expectation_arguments[name] = value

        def expect_column_values_to_not_be_null(self, column: str) -> None:
            self.expectation_calls.append(("not_null", column))

        def expect_column_values_to_be_between(self, column: str, **kwargs: object) -> None:
            self.expectation_calls.append(("between", column, kwargs))

        def expect_column_values_to_match_regex(
            self,
            column: str,
            pattern: str,
            *,
            mostly: float,
        ) -> None:
            self.expectation_calls.append(("match_regex", column, pattern, mostly))

        def expect_column_values_to_be_in_set(self, column: str, values: set[str]) -> None:
            self.expectation_calls.append(("in_set", column, values))

        def validate(self) -> _StubValidation:
            if fail_on_validate:
                raise RuntimeError("validation boom")

            results = [
                _StubExpectationResult(
                    success=False,
                    expectation_config={
                        "type": "expect_column_values_to_match_regex",
                        "kwargs": {"column": "contact_primary_email"},
                    },
                    result={"unexpected_list": ["bad1", "bad2", "bad3", "bad4"]},
                ),
                _StubExpectationResult(
                    success=False,
                    expectation_config={
                        "type": "expect_column_values_to_be_between",
                        "kwargs": {"column": "data_quality_score"},
                    },
                    result={"partial_unexpected_list": ["too-low"]},
                ),
                _StubExpectationResult(success=True, expectation_config={}, result={}),
            ]
            return _StubValidation(results=results, success=False)

    runtime = {
        "Batch": _StubBatch,
        "ExpectationSuite": _StubExpectationSuite,
        "EphemeralDataContext": _StubDataContext,
        "DataContextConfig": _StubDataContextConfig,
        "InMemoryStoreBackendDefaults": _StubStoreDefaults,
        "PandasExecutionEngine": _StubExecutionEngine,
        "Validator": _StubValidator,
        "project_manager": project_manager,
    }
    return runtime, project_manager


def test_run_with_great_expectations_collects_failures_and_restores_context():
    runtime, manager = _make_stub_ge_runtime()
    df = pd.DataFrame(
        {
            "organization_name": ["Org"],
            "organization_slug": ["org"],
            "data_quality_score": [0.2],
            "contact_primary_email": ["bad"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://example.com"],
            "country": ["South Africa"],
        }
    )
    df = _with_validation_defaults(df)

    summary = _run_with_great_expectations(
        df,
        email_mostly=0.9,
        phone_mostly=0.9,
        website_mostly=0.9,
        runtime_override=runtime,
    )

    assert summary is not None
    assert summary.success is False
    assert "unexpected ['bad1', 'bad2', 'bad3']" in summary.failures[0]
    assert any("data_quality_score" in failure for failure in summary.failures)
    assert manager.current_project == "previous_project"
    assert len(manager.set_history) == 2
    assert manager.set_history[-1] == "previous_project"


def test_run_with_great_expectations_restores_context_on_error():
    runtime, manager = _make_stub_ge_runtime(fail_on_validate=True)
    df = pd.DataFrame(
        {
            "organization_name": ["Org"],
            "organization_slug": ["org"],
            "data_quality_score": [0.2],
            "contact_primary_email": ["bad"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://example.com"],
            "country": ["South Africa"],
        }
    )
    df = _with_validation_defaults(df)

    with pytest.raises(RuntimeError):
        _run_with_great_expectations(
            df,
            email_mostly=0.9,
            phone_mostly=0.9,
            website_mostly=0.9,
            runtime_override=runtime,
        )

    assert manager.current_project == "previous_project"
    assert manager.set_history[-1] == "previous_project"


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_valid_data():
    """Test run_expectations uses Great Expectations when available."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-org-1", "test-org-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert isinstance(result, ExpectationSummary)
    assert result.success is True
    assert len(result.failures) == 0


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_missing_org_name():
    """Test GE path detects missing organization names."""
    df = pd.DataFrame(
        {
            "organization_name": [None, "Test Org"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert result.success is False
    assert any("organization_name" in str(f) for f in result.failures)


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_invalid_quality_score():
    """Test GE path detects invalid quality scores."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org"],
            "organization_slug": ["test-org"],
            "country": ["South Africa"],
            "data_quality_score": [1.5],  # Invalid: > 1.0
            "contact_primary_email": ["test@example.com"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://test.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert result.success is False
    assert any(
        "quality_score" in str(f).lower() or "between" in str(f).lower() for f in result.failures
    )


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_invalid_email_format():
    """Test GE path detects invalid email formats."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2", "Test Org 3"],
            "organization_slug": ["test-1", "test-2", "test-3"],
            "country": ["South Africa", "South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9, 0.7],
            "contact_primary_email": [
                "invalid-email",  # Invalid
                "test@example.com",  # Valid
                "another@test.com",  # Valid
            ],
            "contact_primary_phone": ["+271234", "+272345", "+273456"],
            "website": ["https://test1.com", "https://test2.com", "https://test3.com"],
        }
    )

    # With default threshold of 0.85, 2/3 valid (66%) should fail
    result = run_expectations(df, email_mostly=0.85)

    assert result.success is False
    assert any("email" in str(f).lower() for f in result.failures)


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_invalid_phone_format():
    """Test GE path detects invalid phone formats."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": [
                "123456",  # Invalid: no +
                "+27123456789",  # Valid
            ],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )

    # With default threshold of 0.85, 1/2 valid (50%) should fail
    result = run_expectations(df, phone_mostly=0.85)

    assert result.success is False
    assert any("phone" in str(f).lower() for f in result.failures)


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_invalid_website_format():
    """Test GE path detects invalid website formats."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": [
                "www.test.com",  # Invalid: no https://
                "https://test2.com",  # Valid
            ],
        }
    )

    # With default threshold of 0.85, 1/2 valid (50%) should fail
    result = run_expectations(df, website_mostly=0.85)

    assert result.success is False
    assert any("website" in str(f).lower() for f in result.failures)


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_wrong_country():
    """Test GE path detects wrong country values."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org"],
            "organization_slug": ["test-org"],
            "country": ["United States"],  # Wrong country
            "data_quality_score": [0.8],
            "contact_primary_email": ["test@example.com"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://test.com"],
        }
    )

    result = run_expectations(df)

    assert result.success is False
    assert any("country" in str(f).lower() or "in_set" in str(f).lower() for f in result.failures)


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_sanitizes_blank_values():
    """Test GE path sanitizes blank contact values before validation."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2", "Test Org 3"],
            "organization_slug": ["test-1", "test-2", "test-3"],
            "country": ["South Africa", "South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9, 0.7],
            "contact_primary_email": [
                "test@example.com",  # Valid
                "   ",  # Blank - should be treated as NA
                "another@test.com",  # Valid
            ],
            "contact_primary_phone": ["+271234567", "+272345678", "+273456789"],
            "website": ["https://test1.com", "https://test2.com", "https://test3.com"],
        }
    )
    df = _with_validation_defaults(df)

    # Blanks should be ignored, so 2/2 non-blank should be valid (100%)
    result = run_expectations(df, email_mostly=0.85)

    # Should pass since blanks are excluded from validation
    assert result.success is True


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_missing_organization_slug():
    """Test GE path detects missing organization slugs."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test Org", "Test Org 2"],
            "organization_slug": ["test-1", None],  # Missing slug
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.8, 0.9],
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df = _with_validation_defaults(df)

    result = run_expectations(df)

    assert result.success is False
    assert any("organization_slug" in str(f) for f in result.failures)


@pytest.mark.skipif(not HAS_GE, reason="Great Expectations not available")
def test_run_expectations_ge_with_boundary_quality_scores():
    """Test GE path validates quality scores at boundaries."""
    df_valid = pd.DataFrame(
        {
            "organization_name": ["Test Org 1", "Test Org 2"],
            "organization_slug": ["test-1", "test-2"],
            "country": ["South Africa", "South Africa"],
            "data_quality_score": [0.0, 1.0],  # Valid boundary values
            "contact_primary_email": ["test1@example.com", "test2@example.com"],
            "contact_primary_phone": ["+27123456789", "+27987654321"],
            "website": ["https://test1.com", "https://test2.com"],
        }
    )
    df_valid = _with_validation_defaults(df_valid)

    result = run_expectations(df_valid)
    assert result.success is True

    df_invalid = pd.DataFrame(
        {
            "organization_name": ["Test Org"],
            "organization_slug": ["test-org"],
            "country": ["South Africa"],
            "data_quality_score": [-0.1],  # Invalid: < 0.0
            "contact_primary_email": ["test@example.com"],
            "contact_primary_phone": ["+27123456789"],
            "website": ["https://test.com"],
        }
    )
    df_invalid = _with_validation_defaults(df_invalid)

    result2 = run_expectations(df_invalid)
    assert result2.success is False
