from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("frictionless")

from hotpass import cli

from tests.fixtures.lineage import CapturedLineage


def expect(condition: bool, message: str) -> None:
    """Fail the current test with a descriptive message."""

    if not condition:
        pytest.fail(message)


def test_run_command_emits_lineage_events(
    sample_data_dir: Path,
    tmp_path: Path,
    capture_lineage: CapturedLineage,
) -> None:
    """The CLI should emit OpenLineage events for pipeline runs."""

    output_path = tmp_path / "refined.xlsx"

    exit_code = cli.main(
        [
            "run",
            "--input-dir",
            str(sample_data_dir),
            "--output-path",
            str(output_path),
            "--log-format",
            "json",
        ]
    )

    expect(exit_code == 0, "CLI run should succeed when sample data is available.")

    events = capture_lineage.events
    expect(len(events) == 2, "Expected start and complete lineage events to be emitted.")

    start_event, complete_event = events
    expect(start_event.eventType == "START", "First event should mark the run start.")
    expect(
        complete_event.eventType == "COMPLETE",
        "Second event should mark run completion.",
    )
    expect(
        start_event.job.name.startswith("hotpass.pipeline"),
        "Job name should carry the hotpass.pipeline namespace.",
    )
    expect(
        start_event.run.runId == complete_event.run.runId,
        "Run identifiers should match between emitted events.",
    )

    input_names = [dataset.name for dataset in start_event.inputs]
    expect(
        any(sample_data_dir.name in name for name in input_names),
        "Input lineage should reference the source data directory.",
    )

    output_names = [dataset.name for dataset in complete_event.outputs]
    expect(
        any(output_path.name in name for name in output_names),
        "Output lineage should include the refined workbook.",
    )
