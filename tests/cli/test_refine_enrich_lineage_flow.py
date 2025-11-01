from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from hotpass import cli
from hotpass.orchestration import rehydrate_archive_task

from tests.fixtures.lineage import CapturedLineage

if TYPE_CHECKING:
    from tests.conftest import MultiWorkbookBundle


def expect(condition: bool, message: str) -> None:
    """Fail the current test with a descriptive message."""

    if not condition:
        pytest.fail(message)


def test_refine_enrich_lineage_from_archived_bundle(
    multi_workbook_bundle: "MultiWorkbookBundle",
    tmp_path: Path,
    capture_lineage: CapturedLineage,
) -> None:
    """End-to-end refine→enrich→lineage flow for archived multi-workbook bundles."""

    restore_dir = tmp_path / "rehydrated"
    extracted_dir = rehydrate_archive_task(
        multi_workbook_bundle.archive_path, restore_dir
    )
    expect(extracted_dir.exists(), "Rehydrated archive should exist for refine run.")

    refined_path = tmp_path / "refined.xlsx"
    dist_dir = tmp_path / "dist"

    exit_code = cli.main(
        [
            "refine",
            "--input-dir",
            str(extracted_dir),
            "--output-path",
            str(refined_path),
            "--dist-dir",
            str(dist_dir),
            "--log-format",
            "json",
            "--archive",
        ]
    )
    expect(exit_code == 0, "Refine command should succeed for archived bundle inputs.")
    expect(refined_path.exists(), "Refined workbook should be created.")

    archives = list(dist_dir.glob("refined-data-*.zip"))
    expect(archives, "Archive packaging should produce a refined-data zip artifact.")

    events = capture_lineage.events
    expect(len(events) >= 2, "Lineage capture should record start and complete events.")
    start_event, complete_event = events[0], events[-1]
    expect(start_event.eventType == "START", "First lineage event should be START.")
    expect(
        complete_event.eventType == "COMPLETE",
        "Last lineage event should be COMPLETE.",
    )
    input_names = {dataset.name for dataset in start_event.inputs}
    expect(
        len(input_names) >= 2,
        "Lineage inputs should list multiple workbooks from the bundle.",
    )
    expect(
        any(name.endswith("refined.xlsx") for name in (dataset.name for dataset in complete_event.outputs)),
        "Output lineage should reference the refined workbook.",
    )

    enriched_path = tmp_path / "enriched.xlsx"
    exit_code = cli.main(
        [
            "enrich",
            "--input",
            str(refined_path),
            "--output",
            str(enriched_path),
            "--allow-network",
            "false",
        ]
    )
    expect(exit_code == 0, "Enrich command should succeed on refined workbook.")
    expect(enriched_path.exists(), "Enriched workbook should be written to disk.")

    refined_df = pd.read_excel(refined_path)
    enriched_df = pd.read_excel(enriched_path)
    expect(len(refined_df) > 0, "Refined workbook should contain data rows.")
    expect(len(enriched_df) == len(refined_df), "Enrichment should preserve row count.")
    expect(
        "provenance_source" in enriched_df.columns,
        "Enriched workbook should include provenance metadata columns.",
    )


def test_backfill_cli_prepares_runs_for_archived_bundle(
    multi_workbook_bundle: "MultiWorkbookBundle",
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backfill CLI should pass archive context to orchestration layer."""

    archive_root = multi_workbook_bundle.archive_root
    archive_target = multi_workbook_bundle.archive_path

    restore_root = tmp_path / "restore"
    recorded: dict[str, object] = {}

    def _fake_backfill_pipeline_flow(
        *,
        runs: list[dict[str, str]],
        archive_root: str,
        restore_root: str,
        archive_pattern: str,
        base_config: dict[str, object] | None,
        parameters: dict[str, object],
        concurrency_limit: int,
        concurrency_key: str,
    ) -> dict[str, object]:
        recorded.update(
            {
                "runs": runs,
                "archive_root": archive_root,
                "restore_root": restore_root,
                "archive_pattern": archive_pattern,
                "parameters": parameters,
            }
        )
        return {
            "metrics": {
                "total_runs": len(runs),
                "successful_runs": len(runs),
            },
            "runs": [
                {
                    "run_date": run["run_date"],
                    "version": run["version"],
                    "status": "success",
                }
                for run in runs
            ],
        }

    monkeypatch.setattr(
        "hotpass.cli.commands.backfill.backfill_pipeline_flow",
        _fake_backfill_pipeline_flow,
    )

    exit_code = cli.main(
        [
            "backfill",
            "--start-date",
            multi_workbook_bundle.run_date,
            "--end-date",
            multi_workbook_bundle.run_date,
            "--version",
            multi_workbook_bundle.version,
            "--archive-root",
            str(archive_root),
            "--restore-root",
            str(restore_root),
            "--archive-pattern",
            multi_workbook_bundle.pattern,
            "--input-dir",
            str(multi_workbook_bundle.input_dir),
            "--output-path",
            str(tmp_path / "refined-output.xlsx"),
            "--dist-dir",
            str(tmp_path / "refined-dist"),
            "--log-format",
            "json",
        ]
    )

    expect(exit_code == 0, "Backfill command should return success exit code.")
    expect(recorded, "Backfill pipeline flow should be invoked during CLI execution.")
    expect(
        str(archive_root) == recorded.get("archive_root"),
        "CLI should forward archive root to orchestration layer.",
    )
    expect(
        str(restore_root) == recorded.get("restore_root"),
        "CLI should forward restore root to orchestration layer.",
    )
    expect(
        recorded.get("runs"),
        "Backfill orchestration should receive expanded run definitions.",
    )
