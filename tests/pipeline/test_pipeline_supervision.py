from datetime import UTC, datetime, timedelta

from hotpass.pipeline_supervision import PipelineSnapshot, PipelineSupervisor


def test_pipeline_supervision_identifies_unhealthy_tasks():
    now = datetime.now(UTC)
    payload = {
        "name": "research",
        "runs": [
            {
                "run_id": "old",
                "state": "failed",
                "ended_at": (now - timedelta(days=1)).isoformat(),
            },
            {
                "run_id": "latest",
                "state": "success",
                "ended_at": now.isoformat(),
            },
        ],
        "tasks": [
            {"name": "crawl", "state": "failed", "attempts": 1},
            {
                "name": "notify",
                "state": "success",
                "attempts": 5,
                "last_updated": now.isoformat(),
            },
        ],
        "metrics": {"latency_seconds": 1200},
    }

    snapshot = PipelineSnapshot.from_payload(payload)
    report = PipelineSupervisor().inspect(snapshot)

    assert report.name == "research"
    assert report.latest_state == "success"
    unhealthy_names = {task.name for task in report.unhealthy_tasks}
    assert unhealthy_names == {"crawl", "notify"}
    notify_details = next(task for task in report.unhealthy_tasks if task.name == "notify")
    assert notify_details.details.get("note") == "High retry count"
    assert any(
        "Requeue failed tasks" in recommendation
        for recommendation in report.recommendations
    )
    assert any(
        "Pipeline latency exceeds" in recommendation
        for recommendation in report.recommendations
    )


def test_pipeline_snapshot_from_payload_handles_missing_fields():
    snapshot = PipelineSnapshot.from_payload({})
    assert snapshot.name == "unknown"
    assert snapshot.runs == ()
    assert snapshot.tasks == ()
