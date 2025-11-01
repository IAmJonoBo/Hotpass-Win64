"""Configuration dataclasses describing acquisition agent plans."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    """Describe a provider the acquisition agent should call."""

    name: str
    options: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    weight: float = 1.0

    def merged_options(self, overrides: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        if not overrides:
            return self.options
        merged: dict[str, Any] = dict(self.options)
        merged.update(overrides)
        return merged


@dataclass(frozen=True, slots=True)
class TargetDefinition:
    """Entity the agent should enrich."""

    identifier: str
    domain: str | None = None
    location: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Runtime description of an acquisition agent."""

    name: str
    description: str | None = None
    search_terms: Sequence[str] = field(default_factory=tuple)
    region: str | None = None
    targets: Sequence[TargetDefinition] = field(default_factory=tuple)
    providers: Sequence[ProviderDefinition] = field(default_factory=tuple)
    tasks: Sequence[AgentTaskDefinition] = field(default_factory=tuple)
    concurrency: int = 1
    enabled: bool = True

    def active_providers(self) -> tuple[ProviderDefinition, ...]:
        return tuple(provider for provider in self.providers if provider.enabled)

    def active_targets(self) -> tuple[TargetDefinition, ...]:
        return tuple(target for target in self.targets if target.identifier)

    def active_tasks(self) -> tuple[AgentTaskDefinition, ...]:
        return tuple(task for task in self.tasks if task.enabled)


@dataclass(frozen=True, slots=True)
class AcquisitionPlan:
    """Overall acquisition plan executed prior to spreadsheet ingestion."""

    enabled: bool = False
    agents: Sequence[AgentDefinition] = field(default_factory=tuple)
    deduplicate: bool = True
    provenance_namespace: str = "agent"

    def active_agents(self) -> tuple[AgentDefinition, ...]:
        return tuple(agent for agent in self.agents if agent.enabled and agent.active_providers())


class AgentTaskKind(str, Enum):
    """Supported acquisition task types."""

    SEARCH = "search"
    CRAWL = "crawl"
    API = "api"


@dataclass(frozen=True, slots=True)
class AgentTaskDefinition:
    """Declarative configuration for individual acquisition tasks."""

    name: str
    kind: AgentTaskKind = AgentTaskKind.API
    provider: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
