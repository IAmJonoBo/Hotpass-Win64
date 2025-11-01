"""Enhanced error handling and recovery for Hotpass pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors that can occur."""

    FILE_NOT_FOUND = "file_not_found"
    FILE_READ_ERROR = "file_read_error"
    SCHEMA_MISMATCH = "schema_mismatch"
    VALIDATION_FAILURE = "validation_failure"
    DATA_QUALITY = "data_quality"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FORMAT = "invalid_format"
    DUPLICATE_RECORD = "duplicate_record"
    CONFIGURATION_ERROR = "configuration_error"
    PROCESSING_ERROR = "processing_error"


@dataclass
class ErrorContext:
    """Context information for an error."""

    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    source_file: str | None = None
    source_row: int | None = None
    source_column: str | None = None
    suggested_fix: str | None = None
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "source_file": self.source_file,
            "source_row": self.source_row,
            "source_column": self.source_column,
            "suggested_fix": self.suggested_fix,
            "recoverable": self.recoverable,
        }


class HotpassError(Exception):
    """Base exception for Hotpass errors."""

    def __init__(self, context: ErrorContext):
        self.context = context
        super().__init__(context.message)


class FileNotFoundError(HotpassError):
    """Raised when a required file is not found."""

    @classmethod
    def create(cls, file_path: str, suggested_fix: str | None = None) -> FileNotFoundError:
        context = ErrorContext(
            category=ErrorCategory.FILE_NOT_FOUND,
            severity=ErrorSeverity.ERROR,
            message=f"File not found: {file_path}",
            details={"file_path": file_path},
            suggested_fix=suggested_fix or "Check the file path and ensure the file exists",
            recoverable=False,
        )
        return cls(context)


class ValidationError(HotpassError):
    """Raised when data validation fails."""

    @classmethod
    def create(
        cls,
        field: str,
        value: Any,
        expected: str,
        row: int | None = None,
        source_file: str | None = None,
    ) -> ValidationError:
        context = ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.WARNING,
            message=f"Validation failed for field '{field}'",
            details={
                "field": field,
                "value": str(value),
                "expected": expected,
            },
            source_file=source_file,
            source_row=row,
            source_column=field,
            suggested_fix=f"Ensure '{field}' matches expected format: {expected}",
            recoverable=True,
        )
        return cls(context)


class SchemaMismatchError(HotpassError):
    """Raised when source schema doesn't match expected schema."""

    @classmethod
    def create(
        cls,
        expected_columns: list[str],
        actual_columns: list[str],
        source_file: str | None = None,
    ) -> SchemaMismatchError:
        missing = set(expected_columns) - set(actual_columns)
        extra = set(actual_columns) - set(expected_columns)

        context = ErrorContext(
            category=ErrorCategory.SCHEMA_MISMATCH,
            severity=ErrorSeverity.WARNING,
            message="Schema mismatch detected",
            details={
                "expected_columns": expected_columns,
                "actual_columns": actual_columns,
                "missing_columns": list(missing),
                "extra_columns": list(extra),
            },
            source_file=source_file,
            suggested_fix=(
                "Use column mapping to align source columns with target schema, "
                "or update the expected schema"
            ),
            recoverable=True,
        )
        return cls(context)


class DataContractError(HotpassError):
    """Raised when governed data contracts fail during validation."""

    @classmethod
    def from_frictionless(
        cls,
        table_name: str,
        *,
        expected_fields: list[str],
        actual_fields: list[str],
        issues: list[str],
        source_file: str | None = None,
    ) -> DataContractError:
        missing = sorted(set(expected_fields) - set(actual_fields))
        extra = sorted(set(actual_fields) - set(expected_fields))
        context = ErrorContext(
            category=ErrorCategory.SCHEMA_MISMATCH,
            severity=ErrorSeverity.ERROR,
            message=f"Frictionless schema validation failed for {table_name}",
            details={
                "table": table_name,
                "missing_fields": missing,
                "extra_fields": extra,
                "issues": issues,
            },
            source_file=source_file,
            recoverable=False,
            suggested_fix=(
                "Align the ingest table with the governed schema or update the schema contract"
            ),
        )
        return cls(context)

    @classmethod
    def from_expectations(
        cls,
        suite_name: str,
        failures: list[str],
        *,
        source_file: str | None = None,
    ) -> DataContractError:
        failure_hint = failures[0] if failures else ""
        context = ErrorContext(
            category=ErrorCategory.VALIDATION_FAILURE,
            severity=ErrorSeverity.ERROR,
            message=(
                f"Great Expectations suite '{suite_name}' failed"
                + (f": {failure_hint}" if failure_hint else "")
            ),
            details={"suite": suite_name, "failures": failures},
            source_file=source_file,
            recoverable=False,
            suggested_fix=(
                "Inspect the expectation failures and correct the source data before retrying"
            ),
        )
        return cls(context)


@dataclass
class ErrorReport:
    """Aggregated error report for a pipeline run."""

    errors: list[ErrorContext] = field(default_factory=list)
    warnings: list[ErrorContext] = field(default_factory=list)

    def add_error(self, context: ErrorContext) -> None:
        """Add an error to the report."""
        if context.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL):
            self.errors.append(context)
        else:
            self.warnings.append(context)

    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors."""
        return any(e.severity == ErrorSeverity.CRITICAL for e in self.errors)

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "critical_errors": sum(1 for e in self.errors if e.severity == ErrorSeverity.CRITICAL),
            "recoverable_errors": sum(1 for e in self.errors if e.recoverable),
            "errors_by_category": self._count_by_category(),
        }

    def _count_by_category(self) -> dict[str, int]:
        """Count errors by category."""
        counts: dict[str, int] = {}
        for error in self.errors + self.warnings:
            category = error.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts

    def to_markdown(self) -> str:
        """Format report as markdown."""
        lines = ["# Error Report", ""]

        summary = self.get_summary()
        lines.extend(
            [
                "## Summary",
                "",
                f"- Total Errors: {summary['total_errors']}",
                f"- Total Warnings: {summary['total_warnings']}",
                f"- Critical Errors: {summary['critical_errors']}",
                f"- Recoverable Errors: {summary['recoverable_errors']}",
                "",
            ]
        )

        if self.errors:
            lines.extend(["## Errors", ""])
            for i, error in enumerate(self.errors, 1):
                lines.extend(
                    [
                        f"### Error {i}: {error.message}",
                        "",
                        f"**Category:** {error.category.value}",
                        f"**Severity:** {error.severity.value}",
                    ]
                )
                if error.source_file:
                    lines.append(f"**Source:** {error.source_file}")
                if error.source_row is not None:
                    lines.append(f"**Row:** {error.source_row}")
                if error.source_column:
                    lines.append(f"**Column:** {error.source_column}")
                if error.suggested_fix:
                    lines.extend(["", f"**Suggested Fix:** {error.suggested_fix}"])
                lines.append("")

        if self.warnings:
            lines.extend(["## Warnings", ""])
            for i, warning in enumerate(self.warnings, 1):
                lines.append(f"{i}. **{warning.message}**")
                if warning.suggested_fix:
                    lines.append(f"   - Fix: {warning.suggested_fix}")
                lines.append("")

        return "\n".join(lines)


class ErrorHandler:
    """Handles errors with configurable recovery strategies."""

    def __init__(self, fail_fast: bool = False):
        self.fail_fast = fail_fast
        self.report = ErrorReport()

    def handle_error(self, context: ErrorContext) -> None:
        """Handle an error based on severity and configuration."""
        self.report.add_error(context)

        if self.fail_fast and context.severity in (
            ErrorSeverity.ERROR,
            ErrorSeverity.CRITICAL,
        ):
            raise HotpassError(context)

        if context.severity == ErrorSeverity.CRITICAL and not context.recoverable:
            raise HotpassError(context)

    def get_report(self) -> ErrorReport:
        """Get the accumulated error report."""
        return self.report
