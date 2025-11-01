"""Tests for enhanced error handling."""

import pytest

pytest.importorskip("frictionless")

from hotpass.error_handling import (
    ErrorCategory,
    ErrorContext,  # noqa: E402
    ErrorHandler,
    ErrorReport,
    ErrorSeverity,
    HotpassError,
    ValidationError,
)

from tests.helpers.assertions import expect


def test_error_context_to_dict():
    """Test error context serialization."""
    context = ErrorContext(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.WARNING,
        message="Test error",
        details={"field": "email"},
        suggested_fix="Check email format",
    )

    data = context.to_dict()

    expect(
        data["category"] == "validation_failure",
        "Category should be 'validation_failure'",
    )
    expect(data["severity"] == "warning", "Severity should be 'warning'")
    expect(data["message"] == "Test error", "Message should match")
    expect(data["details"]["field"] == "email", "Field detail should be 'email'")


def test_validation_error_create():
    """Test creating a validation error."""
    error = ValidationError.create(
        field="email",
        value="invalid",
        expected="valid email address",
        row=5,
    )

    expect(
        error.context.category == ErrorCategory.VALIDATION_FAILURE,
        "Error category should be VALIDATION_FAILURE",
    )
    expect(error.context.source_row == 5, "Source row should be 5")
    expect("email" in error.context.message, "Message should contain 'email'")


def test_error_report_add_error():
    """Test adding errors to report."""
    report = ErrorReport()

    error_ctx = ErrorContext(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.ERROR,
        message="Error message",
    )
    warning_ctx = ErrorContext(
        category=ErrorCategory.DATA_QUALITY,
        severity=ErrorSeverity.WARNING,
        message="Warning message",
    )

    report.add_error(error_ctx)
    report.add_error(warning_ctx)

    expect(len(report.errors) == 1, "Should have 1 error")
    expect(len(report.warnings) == 1, "Should have 1 warning")


def test_error_report_has_critical_errors():
    """Test detecting critical errors."""
    report = ErrorReport()

    critical_ctx = ErrorContext(
        category=ErrorCategory.FILE_NOT_FOUND,
        severity=ErrorSeverity.CRITICAL,
        message="Critical error",
    )

    report.add_error(critical_ctx)

    expect(report.has_critical_errors(), "Should have critical errors")
    expect(report.has_errors(), "Should have errors")


def test_error_report_get_summary():
    """Test error report summary."""
    report = ErrorReport()

    report.add_error(
        ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.ERROR,
            message="Error 1",
        )
    )
    report.add_error(
        ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.WARNING,
            message="Warning 1",
        )
    )

    summary = report.get_summary()

    expect(summary["total_errors"] == 1, "Total errors should be 1")
    expect(summary["total_warnings"] == 1, "Total warnings should be 1")
    expect(
        "validation_failure" in summary["errors_by_category"],
        "Should have validation_failure category",
    )


def test_error_report_to_markdown():
    """Test markdown export."""
    report = ErrorReport()

    report.add_error(
        ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.ERROR,
            message="Test error",
            suggested_fix="Fix it this way",
        )
    )

    markdown = report.to_markdown()

    expect("# Error Report" in markdown, "Should contain '# Error Report'")
    expect("Test error" in markdown, "Should contain error message")
    expect("Fix it this way" in markdown, "Should contain suggested fix")


def test_error_handler_fail_fast():
    """Test fail-fast mode."""
    handler = ErrorHandler(fail_fast=True)

    error_ctx = ErrorContext(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.ERROR,
        message="Error",
    )

    with pytest.raises(HotpassError):
        handler.handle_error(error_ctx)


def test_error_handler_accumulate():
    """Test error accumulation mode."""
    handler = ErrorHandler(fail_fast=False)

    error_ctx = ErrorContext(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.ERROR,
        message="Error",
        recoverable=True,
    )

    handler.handle_error(error_ctx)

    report = handler.get_report()
    expect(report.has_errors(), "Report should have errors")
    expect(len(report.errors) == 1, "Report should have 1 error")


def test_error_context_with_location():
    """Test error context with source location."""
    context = ErrorContext(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.ERROR,
        message="Test error",
        source_file="test.xlsx",
        source_row=10,
        source_column="email",
    )

    expect(context.source_file == "test.xlsx", "Source file should match")
    expect(context.source_row == 10, "Source row should be 10")
    expect(context.source_column == "email", "Source column should be 'email'")


def test_error_report_to_json():
    """Test JSON export of error report using get_summary."""
    import json

    report = ErrorReport()
    report.add_error(
        ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.ERROR,
            message="Test error",
        )
    )

    summary = report.get_summary()
    json_str = json.dumps(summary)
    data = json.loads(json_str)

    expect("total_errors" in data, "Should contain 'total_errors' key")
    expect("total_warnings" in data, "Should contain 'total_warnings' key")
    expect(data["total_errors"] == 1, "Total errors should be 1")


def test_error_report_empty():
    """Test empty error report."""
    report = ErrorReport()

    expect(not report.has_errors(), "Empty report should not have errors")
    expect(not report.has_critical_errors(), "Empty report should not have critical errors")
    expect(len(report.errors) == 0, "Empty report should have 0 errors")
    expect(len(report.warnings) == 0, "Empty report should have 0 warnings")


def test_hotpass_error_with_context():
    """Test HotpassError initialization with context."""
    context = ErrorContext(
        category=ErrorCategory.FILE_NOT_FOUND,
        severity=ErrorSeverity.CRITICAL,
        message="File not found",
    )

    error = HotpassError(context)

    expect(error.context == context, "Error context should match")
    expect("File not found" in str(error), "Error string should contain message")


def test_error_report_info_not_counted_as_error():
    """Test that INFO severity is not counted as error."""
    report = ErrorReport()

    info_ctx = ErrorContext(
        category=ErrorCategory.DATA_QUALITY,
        severity=ErrorSeverity.INFO,
        message="Info message",
    )

    report.add_error(info_ctx)

    expect(not report.has_errors(), "INFO severity should not count as error")
    # INFO goes to warnings
    expect(len(report.warnings) == 1, "INFO should be counted as warning")


def test_error_handler_with_warning():
    """Test handling warnings doesn't raise in fail-fast mode."""
    handler = ErrorHandler(fail_fast=True)

    warning_ctx = ErrorContext(
        category=ErrorCategory.DATA_QUALITY,
        severity=ErrorSeverity.WARNING,
        message="Warning",
    )

    # Should not raise
    handler.handle_error(warning_ctx)

    report = handler.get_report()
    expect(len(report.warnings) == 1, "Should have 1 warning")


def test_error_handler_with_critical_not_recoverable_raises():
    """Test that critical non-recoverable errors always raise."""
    handler = ErrorHandler(fail_fast=False)

    critical_ctx = ErrorContext(
        category=ErrorCategory.FILE_NOT_FOUND,
        severity=ErrorSeverity.CRITICAL,
        message="Critical error",
        recoverable=False,  # Not recoverable
    )

    with pytest.raises(HotpassError):
        handler.handle_error(critical_ctx)


def test_error_handler_with_critical_recoverable_no_raise():
    """Test that critical recoverable errors don't raise in accumulate mode."""
    handler = ErrorHandler(fail_fast=False)

    critical_ctx = ErrorContext(
        category=ErrorCategory.FILE_NOT_FOUND,
        severity=ErrorSeverity.CRITICAL,
        message="Critical error",
        recoverable=True,  # Recoverable
    )

    # Should not raise in accumulate mode
    handler.handle_error(critical_ctx)

    report = handler.get_report()
    expect(report.has_critical_errors(), "Report should have critical errors")


def test_error_report_get_by_category():
    """Test getting errors by category."""
    report = ErrorReport()

    report.add_error(
        ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.ERROR,
            message="Validation error",
        )
    )
    report.add_error(
        ErrorContext(
            category=ErrorCategory.FILE_NOT_FOUND,
            severity=ErrorSeverity.ERROR,
            message="File error",
        )
    )

    summary = report.get_summary()
    expect(
        summary["errors_by_category"][ErrorCategory.VALIDATION_FAILURE.value] == 1,
        "Should have 1 validation failure",
    )
    expect(
        summary["errors_by_category"][ErrorCategory.FILE_NOT_FOUND.value] == 1,
        "Should have 1 file not found error",
    )


def test_error_context_all_fields():
    """Test error context with all optional fields."""
    context = ErrorContext(
        category=ErrorCategory.VALIDATION_FAILURE,
        severity=ErrorSeverity.ERROR,
        message="Complete error",
        details={"key": "value"},
        suggested_fix="Fix suggestion",
        source_file="data.xlsx",
        source_row=100,
        source_column="email",
        recoverable=True,
    )

    data = context.to_dict()

    expect(
        data["category"] == ErrorCategory.VALIDATION_FAILURE.value,
        "Category should be VALIDATION_FAILURE",
    )
    expect(data["severity"] == ErrorSeverity.ERROR.value, "Severity should be ERROR")
    expect(data["message"] == "Complete error", "Message should match")
    expect(data["details"]["key"] == "value", "Details should match")
    expect(data["suggested_fix"] == "Fix suggestion", "Suggested fix should match")
    expect(data["source_file"] == "data.xlsx", "Source file should match")
    expect(data["source_row"] == 100, "Source row should be 100")
    expect(data["source_column"] == "email", "Source column should be 'email'")
    expect(data["recoverable"] is True, "Should be recoverable")
