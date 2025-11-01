"""Regression tests for checkpoint validation and failure handling."""

import pandas as pd
import pytest
from hotpass.error_handling import DataContractError
from hotpass.validation import run_checkpoint


def test_checkpoint_validation_passes_with_valid_data(tmp_path):
    """Checkpoint validation succeeds with conforming data."""
    df = pd.DataFrame({"Organisation Name": ["Test Org"], "ID": [1], "Type": ["Flight School"]})

    result = run_checkpoint(
        df,
        checkpoint_name="reachout_organisation",
        source_file="test.xlsx#Organisation",
        data_docs_dir=tmp_path / "data-docs",
    )

    assert result.success is True
    assert (tmp_path / "data-docs").exists()


def test_checkpoint_validation_fails_with_missing_required_field():
    """Checkpoint raises DataContractError when required field is null."""
    df = pd.DataFrame(
        {
            "Organisation Name": [None],  # Required field is null
            "ID": [1],
            "Type": ["Flight School"],
        }
    )

    with pytest.raises(DataContractError) as exc_info:
        run_checkpoint(
            df,
            checkpoint_name="reachout_organisation",
            source_file="test.xlsx#Organisation",
        )

    error = exc_info.value
    assert error.context.category.value == "validation_failure"
    assert error.context.severity.value == "error"
    assert "reachout_organisation" in error.context.message
    assert error.context.recoverable is False


def test_checkpoint_validation_provides_detailed_failure_info():
    """DataContractError includes detailed failure information."""
    # Create data with >84% null values to fail the "mostly": 0.16 threshold
    # (which requires at least 16% non-null, i.e., max 84% null)
    df = pd.DataFrame(
        {
            "Organisation Name": [None, None, None, None, None, None, "Valid Org"],
            "ID": [1, 2, 3, 4, 5, 6, 7],
            "Type": ["Flight School"] * 7,
        }
    )

    with pytest.raises(DataContractError) as exc_info:
        run_checkpoint(
            df,
            checkpoint_name="reachout_organisation",
            source_file="test.xlsx#Organisation",
        )

    error = exc_info.value
    assert "failures" in error.context.details
    failures = error.context.details["failures"]
    assert isinstance(failures, list)
    assert len(failures) > 0


def test_checkpoint_with_invalid_suite_name_raises_error():
    """Checkpoint fails gracefully when checkpoint config doesn't exist."""
    df = pd.DataFrame({"col": [1, 2, 3]})

    with pytest.raises(FileNotFoundError) as exc_info:
        run_checkpoint(
            df,
            checkpoint_name="nonexistent_checkpoint",
            source_file="test.xlsx#Sheet",
        )

    assert "nonexistent_checkpoint" in str(exc_info.value)


def test_checkpoint_validation_without_data_docs_succeeds(tmp_path):
    """Checkpoint can run without Data Docs generation."""
    df = pd.DataFrame({"Organisation Name": ["Test Org"], "ID": [1], "Type": ["Flight School"]})

    # Don't pass data_docs_dir
    result = run_checkpoint(
        df,
        checkpoint_name="reachout_organisation",
        source_file="test.xlsx#Organisation",
    )

    assert result.success is True
