"""Tests for agent-gated Prefect orchestration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast
from unittest.mock import patch

import pytest

pytest.importorskip("frictionless")

import hotpass.orchestration as orchestration

AgenticRequest = orchestration.AgenticRequest
AgentToolPolicy = orchestration.AgentToolPolicy
AgentApprovalDecision = orchestration.AgentApprovalDecision
AgentApprovalError = orchestration.AgentApprovalError
PipelineRunSummary = orchestration.PipelineRunSummary


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_request(
    *,
    tool: str = "prefect",
    role: str = "analyst",
    action: str = "run_pipeline",
    pipeline_overrides: dict[str, Any] | None = None,
) -> AgenticRequest:
    payload = {
        "pipeline": {
            "input_dir": "./data/inbox",
            "output_path": "./dist/from-agent.xlsx",
            "profile_name": "aviation",
            "excel_chunk_size": None,
            "archive": False,
        }
    }
    if pipeline_overrides:
        payload["pipeline"].update(pipeline_overrides)

    return AgenticRequest(
        request_id="req-123",
        agent_name="hotpass-agent",
        role=role,
        tool=tool,
        action=action,
        parameters=payload,
    )


def test_broker_agent_run_denies_unlisted_tool() -> None:
    """Requests for tools that are not permitted for the role are rejected."""

    policy = AgentToolPolicy(
        allowed_tools_by_role={"analyst": frozenset({"prefect", "github"})},
        auto_approved_roles=frozenset({"analyst"}),
    )
    request = _make_request(tool="drive")
    log_sink: list[orchestration.AgentAuditRecord] = []

    with pytest.raises(AgentApprovalError, match="not permitted"):
        orchestration.broker_agent_run(
            request,
            policy,
            log_sink=log_sink,
        )

    expect(bool(log_sink), "a denial should be logged")
    denial_entry = log_sink[0]
    expect(denial_entry.status == "denied", "Denial status should be recorded")
    expect(denial_entry.approved is False, "Approval flag should be False on denial")
    expect(
        "not permitted" in (denial_entry.notes or ""),
        "Denial notes should mention policy",
    )


def test_broker_agent_run_requires_manual_approval() -> None:
    """Roles that require manual approval cannot proceed automatically."""

    policy = AgentToolPolicy(
        allowed_tools_by_role={"operator": frozenset({"prefect"})},
        auto_approved_roles=frozenset(),
    )
    request = _make_request(role="operator")
    log_sink: list[orchestration.AgentAuditRecord] = []

    with pytest.raises(AgentApprovalError, match="Manual approval"):
        orchestration.broker_agent_run(
            request,
            policy,
            log_sink=log_sink,
        )

    expect(bool(log_sink), "a manual approval denial should be logged")
    denial_entry = log_sink[0]
    expect(denial_entry.status == "denied", "Manual denial should be recorded")
    expect(denial_entry.approver == "manual", "Manual approver should be captured")


def test_broker_agent_run_executes_pipeline_with_approval() -> None:
    """Approved requests invoke the pipeline and record audit entries."""

    policy = AgentToolPolicy(
        allowed_tools_by_role={"operator": frozenset({"prefect"})},
        auto_approved_roles=frozenset(),
    )
    request = _make_request(role="operator")
    approval = AgentApprovalDecision(
        approved=True,
        approver="ops.lead",
        notes="Change ticket CHG-42",
    )
    summary = PipelineRunSummary(
        success=True,
        total_records=12,
        elapsed_seconds=1.5,
        output_path=Path("./dist/from-agent.xlsx"),
        quality_report={"expectations_passed": True},
        archive_path=None,
    )
    log_sink: list[orchestration.AgentAuditRecord] = []

    with patch("hotpass.orchestration.run_pipeline_once", return_value=summary) as mock_runner:
        result = orchestration.broker_agent_run(
            request,
            policy,
            approval=approval,
            log_sink=log_sink,
        )

    expect(result is summary, "Broker should return pipeline summary")
    mock_runner.assert_called_once()
    options_arg = mock_runner.call_args[0][0]
    expect(options_arg.profile_name == "aviation", "Profile name should propagate")
    expect(
        options_arg.config.pipeline.input_dir == Path("./data/inbox"),
        "Pipeline input dir should reflect request payload",
    )

    expect(len(log_sink) >= 2, "Log sink should include approval and execution entries")
    expect(log_sink[0].status == "approved", "First log entry should show approval")
    expect(log_sink[0].approved is True, "Approval entry should mark approved")
    expect(log_sink[1].status == "executed", "Execution entry should be recorded")
    result_payload = log_sink[1].result
    if result_payload is None:  # pragma: no cover - defensive guard for mypy
        pytest.fail("Execution entry should include a result payload")
    payload = dict(cast(Mapping[str, Any], result_payload))
    expect(payload.get("success") is True, "Execution result should indicate success")
