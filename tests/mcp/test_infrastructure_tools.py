from __future__ import annotations

from typing import Any

import pytest

from hotpass.mcp.server import HotpassMCPServer

pytestmark = pytest.mark.asyncio


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _patch_run_command(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    recorded: list[list[str]] = []

    async def fake_run_command(
        self: HotpassMCPServer,
        cmd: list[str],
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        recorded.append(cmd)
        return {"returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(HotpassMCPServer, "_run_command", fake_run_command)
    return recorded


async def test_setup_tool_builds_expected_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_commands = _patch_run_command(monkeypatch)
    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.setup",
        {
            "preset": "staging",
            "extras": ["dev", "orchestration"],
            "host": "bastion.internal",
            "via": "ssh-bastion",
            "label": "staging-auto",
            "skip_steps": ["prereqs", "aws", "ctx", "env", "arc"],
            "dry_run": True,
            "assume_yes": False,
        },
    )

    expect(result["success"], "Setup command should report success")
    expect(bool(record_commands), "Run command should be invoked")
    cmd = record_commands[0]
    expect(cmd[:3] == ["uv", "run", "hotpass"], "hotpass command prefix missing")
    expect("--preset" in cmd and "staging" in cmd, "Preset flag missing")
    expect("--skip-aws" in cmd, "Skip AWS flag missing")
    expect("--skip-ctx" in cmd, "Skip ctx flag missing")
    expect("--skip-env" in cmd, "Skip env flag missing")
    expect("--dry-run" in cmd, "Dry-run flag should be present")
    expect("--assume-yes" not in cmd, "Assume-yes should be omitted when false")


async def test_net_tool_supports_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_commands = _patch_run_command(monkeypatch)
    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.net",
        {"action": "status"},
    )
    expect(result["success"], "net status should succeed")
    cmd = record_commands[0]
    expect(cmd[-2:] == ["net", "status"], "Command should call hotpass net status")


async def test_aws_tool_formats_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_commands = _patch_run_command(monkeypatch)
    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.aws",
        {
            "profile": "staging",
            "region": "eu-west-1",
            "eks_cluster": "hotpass-staging",
            "verify_kubeconfig": True,
            "output": "json",
            "dry_run": True,
        },
    )
    expect(result["success"], "AWS tool should succeed in dry-run mode")
    cmd = record_commands[0]
    expect("--profile" in cmd and "staging" in cmd, "Profile flag missing")
    expect("--region" in cmd and "eu-west-1" in cmd, "Region flag missing")
    expect("--eks-cluster" in cmd and "hotpass-staging" in cmd, "Cluster flag missing")
    expect("--verify-kubeconfig" in cmd, "verify-kubeconfig flag missing")
    expect("--output" in cmd and "json" in cmd, "output flag missing")
    expect("--dry-run" in cmd, "dry-run flag missing")


async def test_ctx_tool_builds_expected_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_commands = _patch_run_command(monkeypatch)
    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.ctx",
        {
            "action": "init",
            "prefect_profile": "hotpass-staging",
            "prefect_url": "http://127.0.0.1:4200/api",
            "eks_cluster": "hotpass-staging",
            "kube_context": "hotpass-staging",
            "namespace": "hotpass",
            "dry_run": True,
        },
    )

    expect(result["success"], "ctx init should succeed in dry-run mode")
    cmd = record_commands[0]
    expect(cmd[:3] == ["uv", "run", "hotpass"], "hotpass prefix missing")
    expect(cmd[3:5] == ["ctx", "init"], "ctx init invocation missing")
    expect("--prefect-profile" in cmd, "prefect profile flag missing")
    expect("--prefect-url" in cmd, "prefect url flag missing")
    expect("--eks-cluster" in cmd, "eks cluster flag missing")
    expect("--kube-context" in cmd, "kube context flag missing")
    expect("--namespace" in cmd, "namespace flag missing")
    expect("--dry-run" in cmd, "dry-run flag missing")


async def test_env_tool_generates_expected_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_commands = _patch_run_command(monkeypatch)
    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.env",
        {
            "target": "staging",
            "prefect_url": "http://127.0.0.1:4200/api",
            "openlineage_url": "http://127.0.0.1:5000/api/v1",
            "allow_network": True,
            "force": True,
            "dry_run": True,
        },
    )

    expect(result["success"], "env tool should succeed")
    cmd = record_commands[0]
    expect(cmd[:3] == ["uv", "run", "hotpass"], "hotpass prefix missing")
    expect(cmd[3] == "env", "env command missing")
    expect("--target" in cmd and "staging" in cmd, "target flag missing")
    expect("--prefect-url" in cmd, "prefect url flag missing")
    expect("--openlineage-url" in cmd, "openlineage url flag missing")
    expect("--allow-network" in cmd, "allow-network flag missing")
    expect("--force" in cmd, "force flag missing")
    expect("--dry-run" in cmd, "dry-run flag missing")


async def test_arc_tool_captures_required_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_commands = _patch_run_command(monkeypatch)
    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.arc",
        {
            "owner": "ExampleOrg",
            "repository": "Hotpass",
            "scale_set": "hotpass-arc",
            "namespace": "arc-runners",
            "verify_oidc": True,
            "store_summary": True,
            "dry_run": True,
        },
    )
    expect(result["success"], "ARC tool should succeed")
    cmd = record_commands[0]
    expect("--owner" in cmd and "ExampleOrg" in cmd, "Owner flag missing")
    expect("--repository" in cmd and "Hotpass" in cmd, "Repository flag missing")
    expect("--scale-set" in cmd and "hotpass-arc" in cmd, "Scale-set flag missing")
    expect("--verify-oidc" in cmd, "verify-oidc flag missing")
    expect("--store-summary" in cmd, "store-summary flag missing")
    expect("--dry-run" in cmd, "dry-run flag missing")
