"""Tests covering Prefect deployment manifests and registration logic."""

from __future__ import annotations

import sys
import types
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest
from hotpass.prefect.deployments import DeploymentSpec

from tests.helpers.fixtures import fixture


@contextmanager
def _temporary_module(name: str, module: types.ModuleType | None) -> Iterator[None]:
    """Temporarily override ``sys.modules`` entry and restore afterwards."""

    previous = sys.modules.get(name)
    if module is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = module
    try:
        yield
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


@contextmanager
def _load_deployments_module() -> Iterator[types.ModuleType]:
    """Load ``hotpass.prefect.deployments`` with isolated module state."""

    prefect_module = pytest.importorskip("prefect")
    prefect_flow = prefect_module.flow

    # Ensure optional dependencies imported by deployments are stubbed if missing.
    stubbed: dict[str, types.ModuleType | None] = {}
    for module_name in ("duckdb", "polars", "pyarrow"):
        stubbed[module_name] = sys.modules.get(module_name)
        if module_name not in sys.modules:
            sys.modules[module_name] = types.ModuleType(module_name)

    module_path = (
        Path(__file__).resolve().parents[1]
        / "apps"
        / "data-platform"
        / "hotpass"
        / "prefect"
        / "deployments.py"
    )
    spec = spec_from_file_location("hotpass.prefect.deployments", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Unable to load deployment module spec")

    hotpass_pkg = types.ModuleType("hotpass")
    hotpass_pkg.__path__ = []
    prefect_pkg = types.ModuleType("hotpass.prefect")
    hotpass_pkg.prefect = prefect_pkg  # type: ignore[attr-defined]

    deployments = module_from_spec(spec)

    try:
        with (
            _temporary_module("hotpass", hotpass_pkg),
            _temporary_module("hotpass.prefect", prefect_pkg),
            _temporary_module("hotpass.prefect.deployments", deployments),
        ):
            spec.loader.exec_module(deployments)
            prefect_pkg.deployments = deployments  # type: ignore[attr-defined]

            orchestration_module = types.ModuleType("hotpass.orchestration")

            @prefect_flow(  # type: ignore[misc]
                name="hotpass-refinement-pipeline", validate_parameters=False
            )
            def refinement_pipeline_flow(**kwargs: object) -> dict[str, object]:
                return dict(kwargs)

            @prefect_flow(  # type: ignore[misc]
                name="hotpass-backfill", validate_parameters=False
            )
            def backfill_pipeline_flow(**kwargs: object) -> dict[str, object]:
                return dict(kwargs)

            orchestration_module.refinement_pipeline_flow = refinement_pipeline_flow
            orchestration_module.backfill_pipeline_flow = backfill_pipeline_flow

            with _temporary_module("hotpass.orchestration", orchestration_module):
                yield deployments
    finally:
        # Restore optional dependency modules to their previous state.
        for module_name, original in stubbed.items():
            if original is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original


@fixture(scope="module")
def deployments_module() -> Generator[types.ModuleType]:
    """Provide the Prefect deployments module with isolated imports."""

    with _load_deployments_module() as module:
        yield module


def expect(condition: bool, message: str) -> None:
    """Fail with a descriptive message when the condition is false."""

    if not condition:
        pytest.fail(message)


@fixture(scope="module")
def loaded_specs(
    deployments_module: types.ModuleType,
) -> dict[str, DeploymentSpec]:
    specs = deployments_module.load_deployment_specs(Path("prefect"))
    expect(bool(specs), "No deployment specs discovered under the prefect/ directory.")
    return {spec.identifier: spec for spec in specs}


def test_specs_include_refinement_and_backfill(
    loaded_specs: dict[str, DeploymentSpec],
) -> None:
    """The repo should ship manifests for both refinement and backfill flows."""

    expected_keys = {"refinement", "backfill"}
    expect(
        set(loaded_specs) == expected_keys,
        f"Deployment manifest identifiers should be {expected_keys} but were {set(loaded_specs)}.",
    )


def test_refinement_manifest_encodes_incremental_resume_options(
    loaded_specs: dict[str, DeploymentSpec],
) -> None:
    """The refinement manifest encodes parameters for incremental and resumable runs."""

    spec = loaded_specs["refinement"]
    expect(
        spec.parameters.get("backfill") is False,
        "Refinement flow should disable backfill by default.",
    )
    expect(
        spec.parameters.get("incremental") is True,
        "Refinement flow should run incrementally.",
    )
    expect(
        "since" in spec.parameters,
        (
            "Refinement deployment should expose a 'since' parameter "
            "so runs can resume from checkpoints."
        ),
    )
    schedule = spec.schedule
    expect(schedule is not None, "Refinement manifest should include a schedule block.")
    if schedule is not None:
        expect(
            schedule.kind == "cron",
            "Refinement schedule must use cron semantics.",
        )
        expect(
            schedule.timezone == "UTC",
            "Refinement schedule should explicitly set UTC timezone.",
        )


@pytest.mark.parametrize("identifier", ["refinement", "backfill"])  # type: ignore[misc]
def test_build_runner_deployment_renders_prefect_model(
    identifier: str,
    deployments_module: types.ModuleType,
    loaded_specs: dict[str, DeploymentSpec],
) -> None:
    """Deployment manifests compile into Prefect RunnerDeployment objects."""

    pytest.importorskip("prefect.deployments.runner")
    spec = loaded_specs[identifier]
    runner_deployment = deployments_module.build_runner_deployment(spec)
    expect(
        runner_deployment.name == spec.name,
        "Runner deployment name should match manifest name.",
    )
    expect(
        runner_deployment.parameters == spec.parameters,
        "Runner deployment should propagate manifest parameters verbatim.",
    )
    if spec.schedule is not None:
        expect(
            runner_deployment.schedules is not None
            and len(runner_deployment.schedules) == 1,
            "Scheduled deployments should yield exactly one schedule entry.",
        )


class DummyRunnerDeployRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *deployments_args: object, **kwargs: object) -> list[str]:
        self.calls.append((deployments_args, kwargs))
        return ["deployment-id"]


def test_deploy_pipeline_filters_and_registers(
    deployments_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deploy pipeline should register the selected deployment manifests via Prefect runner API."""

    pytest.importorskip("prefect.deployments.runner")
    monkeypatch.setattr(deployments_module, "PREFECT_AVAILABLE", True, raising=False)

    recorder = DummyRunnerDeployRecorder()
    monkeypatch.setattr(deployments_module.runner, "deploy", recorder, raising=False)

    registered = deployments_module.deploy_pipeline(flows=("refinement",))

    expect(
        registered == ["deployment-id"],
        "Runner should return the Prefect deployment IDs.",
    )
    expect(len(recorder.calls) == 1, "Runner deploy should have been invoked once.")
    args, kwargs = recorder.calls[0]
    expect(
        len(args) == 1, "Only the selected refinement deployment should be registered."
    )
    expect(
        kwargs.get("build") is False,
        "Deploy should skip image builds for in-repo flows.",
    )
    expect(
        kwargs.get("push") is False,
        "Deploy should avoid pushing images during registration.",
    )


def test_deploy_pipeline_without_prefect_raises(
    deployments_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deploying when Prefect is unavailable should raise a runtime error."""

    monkeypatch.setattr(deployments_module, "PREFECT_AVAILABLE", False, raising=False)
    with pytest.raises(RuntimeError, match="Prefect is not installed"):
        deployments_module.deploy_pipeline()


def test_deploy_pipeline_applies_overrides(
    deployments_module: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI overrides should adjust deployment metadata before registration."""

    pytest.importorskip("prefect.deployments.runner")
    monkeypatch.setattr(deployments_module, "PREFECT_AVAILABLE", True, raising=False)

    recorder = DummyRunnerDeployRecorder()
    monkeypatch.setattr(deployments_module.runner, "deploy", recorder, raising=False)

    captured: list[DeploymentSpec] = []
    original_build = deployments_module.build_runner_deployment

    def _capture(spec: DeploymentSpec) -> Any:
        captured.append(spec)
        return original_build(spec)

    monkeypatch.setattr(
        deployments_module, "build_runner_deployment", _capture, raising=False
    )

    deployments_module.deploy_pipeline(
        flows=("refinement",),
        deployment_name="custom-name",
        schedule="0 5 * * *",
        work_pool="prefect-prod",
    )

    expect(len(captured) == 1, "Expected a single deployment spec to be built.")
    spec = captured.pop()
    expect(spec.name == "custom-name", "Deployment name override should apply.")
    expect(spec.work_pool == "prefect-prod", "Work pool override should apply.")
    expect(spec.schedule is not None, "Schedule override should create metadata.")
    if spec.schedule is not None:
        expect(spec.schedule.kind == "cron", "Override should use cron schedule kind.")
        expect(
            spec.schedule.value == "0 5 * * *",
            "Cron expression should match the override value.",
        )

    deployments_module.deploy_pipeline(flows=("refinement",), disable_schedule=True)

    expect(len(captured) == 1, "Second invocation should build another spec.")
    disabled_spec = captured.pop()
    expect(disabled_spec.schedule is None, "Disabling schedule should clear metadata.")


def test_load_deployment_specs_prefers_nested_manifests(tmp_path: Path) -> None:
    """Nested manifests should override root-level definitions for the same identifier."""

    from hotpass.prefect.deployments import load_deployment_specs

    root_manifest = tmp_path / "refinement.yaml"
    nested_dir = tmp_path / "deployments"
    nested_dir.mkdir()
    nested_manifest = nested_dir / "hotpass-refinement.yaml"

    root_manifest.write_text(
        """\
id: refinement
name: root-deployment
flow: hotpass.orchestration:refinement_pipeline_flow
description: root definition
parameters: {}
""",
        encoding="utf-8",
    )

    nested_manifest.write_text(
        """\
id: refinement
name: nested-deployment
flow: hotpass.orchestration:refinement_pipeline_flow
description: nested definition
parameters: {}
""",
        encoding="utf-8",
    )

    specs = load_deployment_specs(tmp_path)
    expect(len(specs) == 1, "Duplicate identifiers should be de-duplicated.")
    spec = specs[0]
    expect(
        spec.name == "nested-deployment",
        "Nested manifest should override root-level definition.",
    )
    expect(
        spec.description == "nested definition",
        "Nested manifest metadata should be preserved.",
    )
