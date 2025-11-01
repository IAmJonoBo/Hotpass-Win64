"""Tests ensuring pipeline progress rendering remains responsive."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hotpass import cli
from hotpass.pipeline import (
    PIPELINE_EVENT_AGGREGATE_COMPLETED,
    PIPELINE_EVENT_AGGREGATE_PROGRESS,
    PIPELINE_EVENT_AGGREGATE_STARTED,
    PIPELINE_EVENT_START,
)
from rich.console import Console


def expect(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


class _RecordingTask:
    def __init__(self, task_id: int, description: str, total: int) -> None:
        self.id = task_id
        self.description = description
        self.total = total
        self.completed = 0


class _RecordingProgress:
    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 - parity with Progress
        self.tasks: list[_RecordingTask] = []
        self.log_messages: list[str] = []

    def __enter__(self) -> _RecordingProgress:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup needed
        return None

    def add_task(self, description: str, total: int = 1) -> int:
        task_id = len(self.tasks) + 1
        task = _RecordingTask(task_id, description, total)
        self.tasks.append(task)
        return task_id

    def update(
        self,
        task_id: int,
        *,
        total: int | None = None,
        completed: int | None = None,
    ) -> None:
        task = next(task for task in self.tasks if task.id == task_id)
        if total is not None:
            task.total = total
        if completed is not None:
            task.completed = completed

    def log(self, message: str) -> None:
        self.log_messages.append(message)


def _load_fixture(name: str) -> list[tuple[str, dict[str, Any]]]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / name
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    return [(entry["event"], entry["payload"]) for entry in data]


def test_pipeline_progress_throttles_high_volume_events() -> None:
    console = Console(record=True)
    progress = cli.PipelineProgress(
        console,
        progress_factory=_RecordingProgress,
        throttle_seconds=0.5,
    )

    with progress:
        progress.handle_event(PIPELINE_EVENT_START, {})
        progress.handle_event(PIPELINE_EVENT_AGGREGATE_STARTED, {"total": 100})
        for completed in range(1000):
            progress.handle_event(
                PIPELINE_EVENT_AGGREGATE_PROGRESS,
                {"completed": completed},
            )
        progress.handle_event(
            PIPELINE_EVENT_AGGREGATE_COMPLETED,
            {"aggregated_records": 100, "conflicts": 0},
        )

    recording_progress: _RecordingProgress = progress._progress
    aggregate_task = next(
        task for task in recording_progress.tasks if task.description == "Aggregating organisations"
    )
    expect(
        aggregate_task.completed == aggregate_task.total,
        "high volume updates should fill aggregate task",
    )
    suppression_logs = [msg for msg in recording_progress.log_messages if "Suppressed" in msg]
    expect(
        bool(suppression_logs),
        "high volume updates should emit suppression summary",
    )


def test_pipeline_progress_replays_high_volume_fixture() -> None:
    console = Console(record=True)
    progress = cli.PipelineProgress(
        console,
        progress_factory=_RecordingProgress,
        throttle_seconds=0.5,
    )
    events = _load_fixture("progress_high_volume.json")

    with progress:
        for event, payload in events:
            progress.handle_event(event, payload)

    recording_progress: _RecordingProgress = progress._progress
    aggregate_task = next(
        (
            task
            for task in recording_progress.tasks
            if task.description == "Aggregating organisations"
        ),
        None,
    )
    if aggregate_task is None:  # pragma: no cover - defensive guard for mypy
        pytest.fail("fixture playback should create aggregate task")
    assert aggregate_task is not None
    expect(
        aggregate_task.completed == aggregate_task.total,
        "aggregate task should finish when replaying fixture",
    )
    suppression_logs = [
        message for message in recording_progress.log_messages if "Suppressed" in message
    ]
    expect(
        bool(suppression_logs),
        "fixture playback should emit suppression summary",
    )
    suppressed_counts = [
        int("".join(ch for ch in message if ch.isdigit()) or "0") for message in suppression_logs
    ]
    expect(
        any(count > 0 for count in suppressed_counts),
        "suppression summary should report suppressed updates",
    )


def test_render_progress_without_console_uses_null_context() -> None:
    with cli.render_progress(None) as progress_context:
        expect(
            progress_context is None,
            "render_progress should yield None when console missing",
        )


def test_render_progress_with_console_uses_pipeline_progress() -> None:
    console = Console(record=True)
    with cli.render_progress(console) as progress_context:
        expect(
            isinstance(progress_context, cli.PipelineProgress),
            "render_progress should yield PipelineProgress when console available",
        )
