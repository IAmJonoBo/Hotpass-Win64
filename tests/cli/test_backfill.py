from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from hotpass import cli

from tests.helpers.fixtures import fixture


@fixture
def base_backfill_config(tmp_path: Path) -> Path:
    archive_root = tmp_path / "archives"
    restore_root = tmp_path / "restore"
    archive_root.mkdir()
    restore_root.mkdir()
    config_path = tmp_path / "backfill.json"
    config_path.write_text(
        json.dumps(
            {
                "pipeline": {
                    "input_dir": str(tmp_path / "inputs"),
                    "output_path": str(tmp_path / "outputs" / "refined.xlsx"),
                },
                "orchestrator": {
                    "backfill": {
                        "archive_root": str(archive_root),
                        "restore_root": str(restore_root),
                        "concurrency_limit": 2,
                        "concurrency_key": "hotpass/tests",
                        "windows": [
                            {
                                "start_date": "2024-01-01",
                                "end_date": "2024-01-02",
                                "versions": ["baseline"],
                            }
                        ],
                    }
                },
            }
        )
    )
    return config_path


def test_backfill_command_expands_dates_and_versions(
    tmp_path: Path,
    base_backfill_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runs: list[dict[str, Any]] = []

    def fake_flow(**kwargs: Any) -> dict[str, Any]:
        runs.extend(kwargs.get("runs", []))
        return {"runs": kwargs.get("runs", []), "metrics": {"total_runs": len(runs)}}

    monkeypatch.setattr(
        "hotpass.cli.commands.backfill.backfill_pipeline_flow",
        fake_flow,
    )

    start = date(2024, 1, 3)
    end = date(2024, 1, 4)
    exit_code = cli.main(
        [
            "backfill",
            "--config",
            str(base_backfill_config),
            "--start-date",
            start.isoformat(),
            "--end-date",
            end.isoformat(),
            "--version",
            "v1",
            "--version",
            "v2",
            "--archive-root",
            str(tmp_path / "custom-archives"),
            "--restore-root",
            str(tmp_path / "custom-restore"),
            "--log-format",
            "json",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    log_lines = [json.loads(line) for line in captured.out.splitlines() if line.strip()]
    summary = next(entry for entry in log_lines if entry["event"] == "backfill.summary")
    assert summary["data"]["total_runs"] == 4
    assert {run["version"] for run in runs} == {"v1", "v2"}
    assert {run["run_date"] for run in runs} == {"2024-01-03", "2024-01-04"}


def test_backfill_command_uses_config_windows_when_not_overridden(
    base_backfill_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_flow(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        return {"runs": kwargs["runs"], "metrics": {"total_runs": len(kwargs["runs"])}}

    monkeypatch.setattr(
        "hotpass.cli.commands.backfill.backfill_pipeline_flow",
        fake_flow,
    )

    exit_code = cli.main(
        [
            "backfill",
            "--config",
            str(base_backfill_config),
            "--log-format",
            "json",
        ]
    )

    assert exit_code == 0
    assert observed["runs"] == [
        {"run_date": "2024-01-01", "version": "baseline"},
        {"run_date": "2024-01-02", "version": "baseline"},
    ]


def test_backfill_command_errors_without_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty_config = tmp_path / "empty.json"
    empty_config.write_text(json.dumps({"pipeline": {"input_dir": str(tmp_path)}}))

    calls: list[Any] = []

    monkeypatch.setattr(
        "hotpass.cli.commands.backfill.backfill_pipeline_flow",
        lambda **_: calls.append(1),
    )

    exit_code = cli.main(
        [
            "backfill",
            "--config",
            str(empty_config),
        ]
    )

    assert exit_code == 1
    assert not calls
    captured = capsys.readouterr()
    assert "No backfill windows" in captured.err or "No backfill windows" in captured.out


def test_backfill_command_overrides_concurrency(
    base_backfill_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_flow(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        return {"runs": kwargs.get("runs", []), "metrics": {"total_runs": 0}}

    monkeypatch.setattr(
        "hotpass.cli.commands.backfill.backfill_pipeline_flow",
        fake_flow,
    )

    exit_code = cli.main(
        [
            "backfill",
            "--config",
            str(base_backfill_config),
            "--concurrency-limit",
            "5",
            "--concurrency-key",
            "custom/key",
        ]
    )

    assert exit_code == 0
    assert observed["concurrency_limit"] == 5
    assert observed["concurrency_key"] == "custom/key"
