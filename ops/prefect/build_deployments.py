"""Generate Prefect RunnerDeployment manifests from Hotpass flows."""

from __future__ import annotations

from pathlib import Path

import yaml
from prefect.deployments import runner

from apps.data_platform.hotpass.orchestration import (  # type: ignore[import-not-found]
    backfill_pipeline_flow,
    refinement_pipeline_flow,
)

OUTPUT_DIR = Path("prefect/deployments")


def export_deployment(deployment: runner.RunnerDeployment, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deployment.model_dump(mode="json")
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def build_refinement() -> runner.RunnerDeployment:
    schedule = runner.construct_schedule(cron="0 6 * * *", timezone="UTC")
    return runner.RunnerDeployment.from_flow(
        refinement_pipeline_flow,
        name="hotpass-refinement",
        description="Daily incremental Hotpass refinement flow.",
        schedule=schedule,
        parameters={
            "input_dir": "./data",
            "output_path": "dist/refined/latest.parquet",
            "profile_name": "aviation",
            "archive": True,
            "dist_dir": "dist",
            "backfill": False,
            "incremental": True,
            "since": None,
        },
        tags=["hotpass", "refinement", "incremental"],
        work_pool_name="default-agent-pool",
    )


def build_backfill() -> runner.RunnerDeployment:
    schedule = runner.construct_schedule(interval=604800, timezone="UTC")
    return runner.RunnerDeployment.from_flow(
        backfill_pipeline_flow,
        name="hotpass-backfill",
        description="Weekly archive replay restoring historical input bundles and outputs.",
        schedule=schedule,
        parameters={
            "runs": [],
            "archive_root": "dist/input-archives",
            "restore_root": "dist/backfill",
            "archive_pattern": "hotpass-inputs-{date:%Y%m%d}-v{version}.zip",
            "base_config": {
                "pipeline": {
                    "dist_dir": "dist",
                    "archive": False,
                },
            },
            "parameters": {
                "pipeline": {
                    "backfill": True,
                    "incremental": False,
                    "since": None,
                },
            },
            "concurrency_limit": 2,
            "concurrency_key": "hotpass/backfill",
        },
        tags=["hotpass", "backfill"],
        work_pool_name="default-agent-pool",
    )


def main() -> None:
    deployments = {
        "hotpass-refinement.yaml": build_refinement(),
        "hotpass-backfill.yaml": build_backfill(),
    }
    for filename, deployment in deployments.items():
        export_deployment(deployment, OUTPUT_DIR / filename)


if __name__ == "__main__":
    main()
