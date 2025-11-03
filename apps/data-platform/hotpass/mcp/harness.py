from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hotpass.pipeline_supervision import (
    PipelineSnapshot,
    PipelineSupervisor,
    PipelineSupervisionReport,
)
from hotpass.research.orchestrator import (
    ResearchContext,
    ResearchOrchestrator,
    SearchStrategy,
    CrawlSchedule,
)


@dataclass(slots=True)
class AgentWorkflowReport:
    """Bundle the artefacts produced by the autonomous agent harness."""

    search: SearchStrategy
    crawl: CrawlSchedule
    supervision: PipelineSupervisionReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "search": self.search.to_dict(),
            "crawl": self.crawl.to_dict(),
            "supervision": self.supervision.to_dict(),
        }


class AgentWorkflowHarness:
    """Simulate an end-to-end MCP agent workflow offline."""

    def __init__(
        self,
        orchestrator: ResearchOrchestrator | None = None,
        pipeline_supervisor: PipelineSupervisor | None = None,
    ) -> None:
        self._orchestrator = orchestrator or ResearchOrchestrator()
        self._pipeline_supervisor = pipeline_supervisor or PipelineSupervisor()

    def simulate(
        self,
        context: ResearchContext,
        *,
        pipeline_snapshot: PipelineSnapshot | Mapping[str, Any] | None = None,
        crawl_backend: str = "deterministic",
    ) -> AgentWorkflowReport:
        """Execute the harness across search, crawl coordination, and supervision."""

        search_strategy = self._orchestrator.intelligent_search(context)
        crawl_schedule = self._orchestrator.coordinate_crawl(
            context, backend=crawl_backend
        )

        snapshot = self._coerce_snapshot(pipeline_snapshot)
        supervision_report = self._pipeline_supervisor.inspect(snapshot)

        return AgentWorkflowReport(
            search=search_strategy,
            crawl=crawl_schedule,
            supervision=supervision_report,
        )

    def _coerce_snapshot(
        self, snapshot: PipelineSnapshot | Mapping[str, Any] | None
    ) -> PipelineSnapshot:
        if snapshot is None:
            return PipelineSnapshot(name="pipeline", runs=(), tasks=(), metrics={})
        if isinstance(snapshot, PipelineSnapshot):
            return snapshot
        if isinstance(snapshot, Mapping):
            return PipelineSnapshot.from_payload(snapshot)
        raise TypeError("pipeline_snapshot must be a PipelineSnapshot or mapping")
