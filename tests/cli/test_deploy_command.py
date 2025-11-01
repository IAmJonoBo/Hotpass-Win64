"""Tests for the `hotpass deploy` CLI command."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.fixtures import fixture


def expect(condition: bool, message: str) -> None:
    """Raise a descriptive failure when the condition is not met."""

    if not condition:
        pytest.fail(message)


def _ensure_optional_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    for module_name in ("duckdb", "pyarrow", "polars"):
        if module_name not in sys.modules:
            monkeypatch.setitem(sys.modules, module_name, types.ModuleType(module_name))
    pyarrow_stub = sys.modules["pyarrow"]
    if not hasattr(pyarrow_stub, "bool_"):
        pyarrow_stub.bool_ = lambda: object()  # type: ignore[attr-defined]


@fixture()
def cli_environment(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    """Load CLI and Prefect deployment modules with optional dependencies stubbed."""

    _ensure_optional_dependencies(monkeypatch)
    cli_main = importlib.import_module("hotpass.cli.main")
    prefect_deployments = importlib.import_module("hotpass.prefect.deployments")
    return cli_main, prefect_deployments


@fixture()
def cli_parser(cli_environment: tuple[Any, Any]) -> Any:
    """Build the Hotpass CLI parser for deployment tests."""

    cli_main, _ = cli_environment
    return cli_main.build_parser()


@fixture()
def deployments_module(cli_environment: tuple[Any, Any]) -> Any:
    """Expose the Prefect deployments helper module for monkeypatching."""

    _, prefect_deployments = cli_environment
    return prefect_deployments


def test_deploy_command_invokes_prefect_with_overrides(
    cli_parser: Any,
    deployments_module: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The deploy command should forward overrides to the Prefect helper."""

    recorded: dict[str, Any] = {}

    def _record(**kwargs: Any) -> list[str]:
        recorded.update(kwargs)
        return ["deployment-123"]

    monkeypatch.setattr(deployments_module, "deploy_pipeline", _record)

    manifest_dir = tmp_path / "prefect-manifests"

    args = cli_parser.parse_args(
        [
            "deploy",
            "--flow",
            "refinement",
            "--manifest-dir",
            str(manifest_dir),
            "--build-image",
            "--push-image",
            "--name",
            "custom-deployment",
            "--schedule",
            "0 6 * * *",
            "--work-pool",
            "prefect-pool",
            "--log-format",
            "json",
        ]
    )

    exit_code = args.handler(args, None)

    expect(exit_code == 0, "Deploy command should exit successfully.")
    expect(
        recorded.get("flows") == ("refinement",),
        "Expected selected flow to be forwarded.",
    )
    expect(
        recorded.get("base_dir") == manifest_dir,
        "Manifest directory override should be passed to the Prefect helper.",
    )
    expect(
        recorded.get("build_image") is True,
        "Build flag should propagate to deploy helper.",
    )
    expect(
        recorded.get("push_image") is True,
        "Push flag should propagate to deploy helper.",
    )
    expect(
        recorded.get("deployment_name") == "custom-deployment",
        "Deployment name override should be forwarded.",
    )
    expect(
        recorded.get("schedule") == "0 6 * * *",
        "Schedule override should be forwarded.",
    )
    expect(recorded.get("disable_schedule") is False, "Schedule should remain enabled.")
    expect(
        recorded.get("work_pool") == "prefect-pool",
        "Work pool override should be forwarded.",
    )


def test_deploy_command_disables_schedule(
    monkeypatch: pytest.MonkeyPatch,
    deployments_module: Any,
    cli_parser: Any,
) -> None:
    """`--schedule none` should disable schedules without raising errors."""

    recorded: dict[str, Any] = {}

    def _record(**kwargs: Any) -> list[str]:
        recorded.update(kwargs)
        return []

    monkeypatch.setattr(deployments_module, "deploy_pipeline", _record)

    args = cli_parser.parse_args(["deploy", "--schedule", "none", "--log-format", "json"])

    exit_code = args.handler(args, None)

    expect(
        exit_code == 0,
        "Deploy command should still exit successfully when disabling schedule.",
    )
    expect(
        recorded.get("flows") is None,
        "No flow selection should forward `None` to deploy helper.",
    )
    expect(recorded.get("schedule") is None, "Schedule override should be cleared.")
    expect(
        recorded.get("disable_schedule") is True,
        "Schedule should be disabled when passing 'none'.",
    )
    expect(
        recorded.get("work_pool") is None,
        "No work pool override should be forwarded by default.",
    )
