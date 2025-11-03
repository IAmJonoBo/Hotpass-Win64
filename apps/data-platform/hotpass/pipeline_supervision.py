from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence


@dataclass(slots=True)
class PipelineRunStatus:
    """Describe the state of a historical pipeline run."""

    run_id: str
    state: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "details": self.details,
        }


@dataclass(slots=True)
class PipelineTaskStatus:
    """Capture the status of an individual pipeline task."""

    name: str
    state: str
    attempts: int = 0
    last_updated: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "attempts": self.attempts,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "details": self.details,
        }


@dataclass(slots=True)
class PipelineSnapshot:
    """Aggregated view of a pipeline's recent activity."""

    name: str
    runs: tuple[PipelineRunStatus, ...] = ()
    tasks: tuple[PipelineTaskStatus, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PipelineSnapshot":
        name = str(payload.get("name", "unknown"))
        runs = tuple(
            _coerce_run(run)
            for run in payload.get("runs", ())
            if isinstance(run, Mapping)
        )
        tasks = tuple(
            _coerce_task(task)
            for task in payload.get("tasks", ())
            if isinstance(task, Mapping)
        )
        metrics_source = payload.get("metrics")
        metrics = dict(metrics_source) if isinstance(metrics_source, Mapping) else {}
        return cls(name=name, runs=runs, tasks=tasks, metrics=metrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runs": [run.to_dict() for run in self.runs],
            "tasks": [task.to_dict() for task in self.tasks],
            "metrics": self.metrics,
        }


@dataclass(slots=True)
class PipelineSupervisionReport:
    """Guidance produced after analysing the pipeline snapshot."""

    name: str
    latest_state: str
    unhealthy_tasks: tuple[PipelineTaskStatus, ...]
    recommendations: tuple[str, ...]
    metrics: dict[str, Any]
    runs: tuple[PipelineRunStatus, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "latest_state": self.latest_state,
            "unhealthy_tasks": [task.to_dict() for task in self.unhealthy_tasks],
            "recommendations": list(self.recommendations),
            "metrics": self.metrics,
            "runs": [run.to_dict() for run in self.runs],
        }


class PipelineSupervisor:
    """Derive actionable guidance for MCP agents supervising the pipeline."""

    HEALTHY_STATES = {"success", "completed", "skipped"}

    def inspect(self, snapshot: PipelineSnapshot) -> PipelineSupervisionReport:
        if not isinstance(snapshot, PipelineSnapshot):
            raise TypeError("snapshot must be a PipelineSnapshot instance")

        latest_state = self._resolve_latest_state(snapshot.runs)
        unhealthy = self._locate_unhealthy_tasks(snapshot.tasks)
        recommendations = self._build_recommendations(latest_state, unhealthy, snapshot.metrics)

        return PipelineSupervisionReport(
            name=snapshot.name,
            latest_state=latest_state,
            unhealthy_tasks=unhealthy,
            recommendations=recommendations,
            metrics=snapshot.metrics,
            runs=snapshot.runs,
        )

    def _resolve_latest_state(self, runs: Sequence[PipelineRunStatus]) -> str:
        if not runs:
            return "unknown"
        ordered = sorted(
            runs,
            key=lambda run: run.ended_at or run.started_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return ordered[0].state

    def _locate_unhealthy_tasks(
        self, tasks: Sequence[PipelineTaskStatus]
    ) -> tuple[PipelineTaskStatus, ...]:
        unhealthy: list[PipelineTaskStatus] = []
        for task in tasks:
            state = task.state.lower()
            if state not in self.HEALTHY_STATES:
                unhealthy.append(task)
            elif task.attempts > 3:
                unhealthy.append(
                    PipelineTaskStatus(
                        name=task.name,
                        state=task.state,
                        attempts=task.attempts,
                        last_updated=task.last_updated,
                        details={**task.details, "note": "High retry count"},
                    )
                )
        return tuple(unhealthy)

    def _build_recommendations(
        self,
        latest_state: str,
        unhealthy: Sequence[PipelineTaskStatus],
        metrics: Mapping[str, Any],
    ) -> tuple[str, ...]:
        advice: list[str] = []
        lower_state = latest_state.lower()
        if lower_state not in self.HEALTHY_STATES:
            advice.append("Review the latest run logs and re-run the pipeline once issues are resolved")
        if any(task.state.lower() == "failed" for task in unhealthy):
            advice.append("Requeue failed tasks with `hotpass qa rerun --from-failed`")
        if any("note" in task.details for task in unhealthy):
            advice.append("Investigate tasks with sustained retries; consider widening rate limits")
        latency = metrics.get("latency_seconds") if isinstance(metrics, Mapping) else None
        if isinstance(latency, (int, float)) and latency > 600:
            advice.append("Pipeline latency exceeds 10 minutes; audit upstream dependencies")
        if not advice:
            advice.append("Pipeline is healthy; continue monitoring telemetry dashboards")
        return tuple(dict.fromkeys(advice))


def _coerce_run(payload: Mapping[str, Any]) -> PipelineRunStatus:
    run_id = str(payload.get("run_id", payload.get("id", "unknown")))
    state = str(payload.get("state", "unknown"))
    started_at = _coerce_datetime(payload.get("started_at"))
    ended_at = _coerce_datetime(payload.get("ended_at"))
    details_source = payload.get("details")
    details = dict(details_source) if isinstance(details_source, Mapping) else {}
    return PipelineRunStatus(
        run_id=run_id,
        state=state,
        started_at=started_at,
        ended_at=ended_at,
        details=details,
    )


def _coerce_task(payload: Mapping[str, Any]) -> PipelineTaskStatus:
    name = str(payload.get("name", payload.get("task", "unknown")))
    state = str(payload.get("state", "unknown"))
    attempts_value = payload.get("attempts", 0)
    attempts = int(attempts_value) if isinstance(attempts_value, (int, float)) else 0
    last_updated = _coerce_datetime(payload.get("last_updated"))
    details_source = payload.get("details")
    details = dict(details_source) if isinstance(details_source, Mapping) else {}
    return PipelineTaskStatus(
        name=name,
        state=state,
        attempts=attempts,
        last_updated=last_updated,
        details=details,
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None
