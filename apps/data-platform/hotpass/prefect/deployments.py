"""Prefect deployment manifest loading and application utilities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import yaml

try:  # pragma: no cover - exercised via tests when Prefect is installed
    from prefect.deployments import runner
    from prefect.utilities.importtools import import_object

    PREFECT_AVAILABLE = True
except ImportError:  # pragma: no cover - handled in tests
    runner = None
    import_object = None
    PREFECT_AVAILABLE = False


@dataclass(frozen=True, slots=True)
class DeploymentSchedule:
    """A structured representation of a deployment schedule."""

    kind: str
    value: Any
    timezone: str | None = None
    anchor_date: str | None = None

    def to_prefect_schedule(self) -> Any:
        """Convert the schedule metadata into a Prefect schedule object."""

        if not PREFECT_AVAILABLE:
            msg = "Prefect is not installed; schedule conversion is unavailable"
            raise RuntimeError(msg)

        kwargs: dict[str, Any] = {}
        if self.timezone:
            kwargs["timezone"] = self.timezone
        if self.kind == "cron":
            return runner.construct_schedule(cron=str(self.value), **kwargs)
        if self.kind == "interval":
            interval_value = self.value
            if isinstance(interval_value, Mapping):
                interval_value = interval_value.get("seconds")
            if self.anchor_date:
                kwargs["anchor_date"] = self.anchor_date
            return runner.construct_schedule(interval=interval_value, **kwargs)
        if self.kind == "rrule":
            return runner.construct_schedule(rrule=str(self.value), **kwargs)

        msg = f"Unsupported schedule kind: {self.kind}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    """In-memory representation of a Prefect deployment manifest."""

    identifier: str
    name: str
    flow: str
    description: str | None
    tags: tuple[str, ...]
    work_pool: str | None
    work_queue: str | None
    parameters: Mapping[str, Any]
    schedule: DeploymentSchedule | None
    paused: bool
    concurrency_limit: int | None
    job_variables: Mapping[str, Any]
    enforce_parameter_schema: bool

    @classmethod
    def from_mapping(cls, identifier: str, payload: Mapping[str, Any]) -> DeploymentSpec:
        """Build a deployment spec from a parsed manifest mapping."""

        schedule_block = payload.get("schedule")
        schedule: DeploymentSchedule | None = None
        if isinstance(schedule_block, Mapping):
            if "value" not in schedule_block:
                msg = f"Schedule definition for {identifier} must include a 'value' field"
                raise ValueError(msg)
            schedule = DeploymentSchedule(
                kind=str(schedule_block.get("kind", "cron")).lower(),
                value=schedule_block.get("value"),
                timezone=schedule_block.get("timezone"),
                anchor_date=schedule_block.get("anchor_date"),
            )

        parameters = payload.get("parameters") or {}
        if not isinstance(parameters, Mapping):
            msg = f"Parameters for {identifier} must be a mapping"
            raise TypeError(msg)

        job_variables = payload.get("job_variables") or {}
        if not isinstance(job_variables, Mapping):
            msg = f"Job variables for {identifier} must be a mapping"
            raise TypeError(msg)

        tags = tuple(str(tag) for tag in payload.get("tags", []) if tag is not None)
        work_pool = payload.get("work_pool")
        work_queue = payload.get("work_queue")

        concurrency_limit = payload.get("concurrency_limit")
        if concurrency_limit is not None:
            concurrency_limit = int(concurrency_limit)

        paused_value = payload.get("paused")
        if paused_value is None and isinstance(schedule_block, Mapping):
            paused_value = not bool(schedule_block.get("active", True))

        return cls(
            identifier=identifier,
            name=str(payload["name"]),
            flow=str(payload["flow"]),
            description=payload.get("description"),
            tags=tags,
            work_pool=str(work_pool) if work_pool else None,
            work_queue=str(work_queue) if work_queue else None,
            parameters=dict(parameters),
            schedule=schedule,
            paused=bool(paused_value) if paused_value is not None else False,
            concurrency_limit=concurrency_limit,
            job_variables=dict(job_variables),
            enforce_parameter_schema=bool(payload.get("enforce_parameter_schema", True)),
        )

    def load_flow(self) -> Any:
        """Import the flow function referenced by the manifest."""

        if not PREFECT_AVAILABLE:
            msg = "Prefect is not installed; flows cannot be imported"
            raise RuntimeError(msg)
        if import_object is None:  # pragma: no cover - defensive guard
            msg = "Prefect import helpers are unavailable"
            raise RuntimeError(msg)
        return import_object(self.flow)


def _read_manifest(path: Path) -> Mapping[str, Any]:
    data: Any
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        import json

        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        msg = f"Deployment manifest {path} is not a mapping"
        raise TypeError(msg)
    return data


def load_deployment_specs(base_dir: Path | None = None) -> list[DeploymentSpec]:
    """Discover and parse Prefect deployment manifests under the given directory."""

    root = Path(base_dir or Path.cwd() / "prefect")
    if not root.exists():
        return []

    manifests: dict[str, tuple[Path, DeploymentSpec]] = {}
    for manifest_path in sorted(
        (path for path in root.glob("**/*") if path.is_file()), key=lambda p: str(p)
    ):
        if manifest_path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        payload = _read_manifest(manifest_path)
        identifier = str(payload.get("id") or manifest_path.stem)
        spec = DeploymentSpec.from_mapping(identifier, payload)
        existing = manifests.get(identifier)
        if existing is not None:
            previous_path, _ = existing
            current_depth = len(manifest_path.relative_to(root).parts)
            previous_depth = len(previous_path.relative_to(root).parts)
            # Prefer manifests located deeper in the hierarchy (e.g., prefect/deployments/*)
            if current_depth <= previous_depth:
                continue
        manifests[identifier] = (manifest_path, spec)
    return [entry[1] for entry in manifests.values()]


def build_runner_deployment(spec: DeploymentSpec) -> Any:
    """Compile a deployment spec into a Prefect runner deployment."""

    if not PREFECT_AVAILABLE:
        msg = "Prefect is not installed; deployments cannot be built"
        raise RuntimeError(msg)

    flow = spec.load_flow()
    schedule = spec.schedule.to_prefect_schedule() if spec.schedule else None

    deployment = runner.RunnerDeployment.from_flow(
        flow,
        name=spec.name,
        schedule=schedule,
        tags=list(spec.tags),
        parameters=dict(spec.parameters),
        description=spec.description,
        work_pool_name=spec.work_pool,
        work_queue_name=spec.work_queue,
        concurrency_limit=spec.concurrency_limit,
        job_variables=dict(spec.job_variables),
        paused=spec.paused,
        enforce_parameter_schema=spec.enforce_parameter_schema,
    )

    return deployment


def deploy_pipeline(
    *,
    flows: Iterable[str] | None = None,
    base_dir: Path | None = None,
    build_image: bool = False,
    push_image: bool = False,
    deployment_name: str | None = None,
    schedule: str | None = None,
    disable_schedule: bool = False,
    work_pool: str | None = None,
) -> list[Any]:
    """Register Hotpass deployments with Prefect based on manifest definitions."""

    if not PREFECT_AVAILABLE:
        msg = "Prefect is not installed; deployment functionality is unavailable"
        raise RuntimeError(msg)

    specs = load_deployment_specs(base_dir)
    flow_filter = set(flows) if flows is not None else None
    selected = [spec for spec in specs if flow_filter is None or spec.identifier in flow_filter]

    def _apply_overrides(spec: DeploymentSpec) -> DeploymentSpec:
        updated = spec
        if deployment_name:
            updated = replace(updated, name=deployment_name)
        if work_pool is not None:
            updated = replace(updated, work_pool=work_pool)
        if disable_schedule:
            updated = replace(updated, schedule=None)
        elif schedule is not None:
            existing_schedule = spec.schedule
            anchor = existing_schedule.anchor_date if existing_schedule else None
            timezone = existing_schedule.timezone if existing_schedule else "UTC"
            updated_schedule = DeploymentSchedule(
                kind="cron",
                value=schedule,
                timezone=timezone,
                anchor_date=anchor,
            )
            updated = replace(updated, schedule=updated_schedule)
        return updated

    deployments_to_apply = [build_runner_deployment(_apply_overrides(spec)) for spec in selected]
    if not deployments_to_apply:
        return []

    return cast(
        list[Any],
        runner.deploy(
            *deployments_to_apply,
            build=build_image,
            push=push_image,
            print_next_steps_message=False,
        ),
    )


__all__ = [
    "DeploymentSchedule",
    "DeploymentSpec",
    "PREFECT_AVAILABLE",
    "build_runner_deployment",
    "deploy_pipeline",
    "load_deployment_specs",
]
