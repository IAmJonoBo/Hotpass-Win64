"""Acquisition agent protocol and helper dataclasses."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from .. import RawRecord
from .config import AcquisitionPlan, AgentDefinition, TargetDefinition


@dataclass(slots=True)
class AgentContext:
    """Runtime parameters provided to each agent run."""

    plan: AcquisitionPlan
    agent: AgentDefinition
    credentials: Mapping[str, str]
    country_code: str
    issued_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass(slots=True)
class AgentResult:
    """Standardised payload emitted by an acquisition agent."""

    agent_name: str
    targets: list[TargetDefinition] = field(default_factory=list)
    records: list[RawRecord] = field(default_factory=list)
    provenance: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: AgentResult) -> None:
        self.records.extend(other.records)
        self.provenance.extend(other.provenance)
        self.warnings.extend(other.warnings)


class AcquisitionAgent(Protocol):
    """Protocol implemented by acquisition agent runtimes."""

    name: str

    def collect(self, context: AgentContext) -> AgentResult:  # pragma: no cover - protocol
        """Collect records for the provided context."""


class TargetResolver(Protocol):
    """Protocol that resolves runtime targets for an agent."""

    def resolve(self, agent: AgentDefinition) -> Sequence[TargetDefinition]:  # pragma: no cover
        """Return the targets that should be processed for the agent."""


def normalise_records(records: Iterable[RawRecord]) -> list[RawRecord]:
    """Deduplicate raw records by source identifier preserving order."""

    seen: set[tuple[str, str]] = set()
    normalised: list[RawRecord] = []
    for record in records:
        source_key = (record.source_dataset, record.source_record_id)
        if source_key in seen:
            continue
        seen.add(source_key)
        normalised.append(record)
    return normalised
