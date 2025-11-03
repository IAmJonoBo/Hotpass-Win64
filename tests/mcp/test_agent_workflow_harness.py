from datetime import UTC, datetime

import pandas as pd

from hotpass.config import IndustryProfile
from hotpass.mcp.harness import AgentWorkflowHarness
from hotpass.pipeline_supervision import PipelineSnapshot
from hotpass.research import ResearchContext, ResearchOrchestrator


def test_agent_workflow_harness_reports_all_stages(tmp_path):
    orchestrator = ResearchOrchestrator(
        cache_root=tmp_path / ".hotpass",
        audit_log=tmp_path / "audit.log",
        artefact_root=tmp_path / "runs",
    )
    harness = AgentWorkflowHarness(orchestrator=orchestrator)

    profile = IndustryProfile.from_dict(
        {
            "name": "generic",
            "display_name": "Generic",
            "authority_sources": [{"name": "Registry", "url": "registry.example"}],
        }
    )

    row = pd.Series({"organization_name": "Example Org", "province": "Western Cape"})
    context = ResearchContext(profile=profile, row=row, allow_network=False)

    snapshot = PipelineSnapshot.from_payload(
        {
            "name": "research-pipeline",
            "runs": [
                {
                    "run_id": "latest",
                    "state": "failed",
                    "ended_at": datetime.now(UTC).isoformat(),
                }
            ],
            "tasks": [{"name": "crawl", "state": "failed", "attempts": 1}],
            "metrics": {"latency_seconds": 900},
        }
    )

    report = harness.simulate(context, pipeline_snapshot=snapshot)

    assert report.search.primary_query.query == "Example Org"
    assert report.crawl.backend == "deterministic"
    assert report.supervision.latest_state == "failed"
    assert any("Review" in recommendation for recommendation in report.supervision.recommendations)
