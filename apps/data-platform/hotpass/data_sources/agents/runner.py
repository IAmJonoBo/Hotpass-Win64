"""Utilities to orchestrate acquisition agents."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING

import pandas as pd

from ...enrichment.providers import REGISTRY as provider_registry
from ...enrichment.providers import BaseProvider, ProviderContext, ProviderPayload
from ...normalization import clean_string
from .. import RawRecord
from .base import AgentContext, AgentResult, normalise_records
from .config import AcquisitionPlan, AgentDefinition, ProviderDefinition, TargetDefinition

if TYPE_CHECKING:
    from ...telemetry.metrics import PipelineMetrics


@dataclass(slots=True)
class AgentTiming:
    """Capture timing metadata for agent execution."""

    agent_name: str
    seconds: float
    record_count: int


class AcquisitionManager:
    """Instantiate providers and execute configured agents."""

    def __init__(
        self,
        plan: AcquisitionPlan,
        *,
        credentials: Mapping[str, str] | None = None,
    ) -> None:
        self.plan = plan
        self.credentials = dict(credentials or {})
        self._metrics: PipelineMetrics | None = None

    @staticmethod
    def _observability() -> ModuleType:
        from ... import observability

        return observability

    def _get_metrics(self) -> PipelineMetrics:
        if self._metrics is None:
            observability = self._observability()
            self._metrics = observability.get_pipeline_metrics()
        return self._metrics

    def run(self, *, country_code: str) -> tuple[pd.DataFrame, list[AgentTiming], list[str]]:
        all_records: list[RawRecord] = []
        timings: list[AgentTiming] = []
        warnings: list[str] = []
        active_agents = self.plan.active_agents()
        metrics = self._get_metrics()
        observability = self._observability()

        plan_attributes = {
            "hotpass.acquisition.scope": "plan",
            "hotpass.acquisition.country": country_code,
            "hotpass.acquisition.agent_count": len(active_agents),
            "hotpass.acquisition.deduplicate": self.plan.deduplicate,
        }

        with observability.trace_operation("acquisition.plan", plan_attributes) as plan_span:
            plan_start = time.perf_counter()

            for agent in active_agents:
                result, duration = self._run_agent(agent, country_code=country_code)
                timings.append(
                    AgentTiming(
                        agent_name=agent.name,
                        seconds=duration,
                        record_count=len(result.records),
                    )
                )
                all_records.extend(result.records)
                warnings.extend(result.warnings)

            if all_records:
                records = (
                    normalise_records(all_records) if self.plan.deduplicate else list(all_records)
                )
                frame = pd.DataFrame([record.as_dict() for record in records])
            else:
                records = []
                frame = pd.DataFrame()

            plan_duration = time.perf_counter() - plan_start
            total_warnings = len(warnings)
            metrics.record_acquisition_duration(
                plan_duration,
                scope="plan",
                extra_attributes={
                    "country": country_code,
                    "agent_count": len(active_agents),
                },
            )
            metrics.record_acquisition_records(
                len(records),
                scope="plan",
                extra_attributes={"country": country_code},
            )
            if total_warnings:
                metrics.record_acquisition_warnings(
                    total_warnings,
                    scope="plan",
                    extra_attributes={"country": country_code},
                )

            plan_span.set_attribute("hotpass.acquisition.duration_ms", plan_duration * 1000)
            plan_span.set_attribute("hotpass.acquisition.records", len(records))
            if total_warnings:
                plan_span.set_attribute("hotpass.acquisition.warnings", total_warnings)

        return frame, timings, warnings

    def _run_agent(self, agent: AgentDefinition, *, country_code: str) -> tuple[AgentResult, float]:
        context = AgentContext(
            plan=self.plan,
            agent=agent,
            credentials=self.credentials,
            country_code=country_code,
        )
        result = AgentResult(agent_name=agent.name)
        targets = agent.active_targets()
        if not targets:
            fallback_targets = [
                TargetDefinition(identifier=term)
                for term in agent.search_terms
                if clean_string(term)
            ]
            targets = tuple(fallback_targets)
        provider_definitions = agent.active_providers()
        agent_attributes = {
            "hotpass.acquisition.scope": "agent",
            "hotpass.acquisition.agent": agent.name,
            "hotpass.acquisition.provider_count": len(provider_definitions),
            "hotpass.acquisition.target_count": len(targets),
        }

        observability = self._observability()
        with observability.trace_operation("acquisition.agent", agent_attributes) as agent_span:
            agent_start = time.perf_counter()

            for provider_definition in provider_definitions:
                provider = self._create_provider(provider_definition)
                payloads = self._execute_provider(
                    provider,
                    provider_definition,
                    targets,
                    context,
                )
                for payload in payloads:
                    self._apply_provenance(payload, agent, result)

            duration = time.perf_counter() - agent_start
            metrics = self._get_metrics()
            metrics.record_acquisition_duration(
                duration,
                scope="agent",
                agent=agent.name,
                extra_attributes={
                    "provider_count": len(provider_definitions),
                    "target_count": len(targets),
                },
            )
            metrics.record_acquisition_records(
                len(result.records),
                scope="agent",
                agent=agent.name,
            )
            if result.warnings:
                metrics.record_acquisition_warnings(
                    len(result.warnings),
                    scope="agent",
                    agent=agent.name,
                )

            agent_span.set_attribute("hotpass.acquisition.duration_ms", duration * 1000)
            agent_span.set_attribute("hotpass.acquisition.records", len(result.records))
            if result.warnings:
                agent_span.set_attribute("hotpass.acquisition.warnings", len(result.warnings))

        return result, duration

    def _execute_provider(
        self,
        provider: BaseProvider,
        definition: ProviderDefinition,
        targets: Sequence[object],
        context: AgentContext,
    ) -> Iterable[ProviderPayload]:
        provider_context = ProviderContext(
            country_code=context.country_code,
            credentials=context.credentials,
            issued_at=context.issued_at,
        )
        payloads: list[ProviderPayload] = []
        provider_attributes = {
            "hotpass.acquisition.scope": "provider",
            "hotpass.acquisition.agent": context.agent.name,
            "hotpass.acquisition.provider": definition.name,
            "hotpass.acquisition.targets": len(targets),
        }

        observability = self._observability()
        with observability.trace_operation(
            "acquisition.provider", provider_attributes
        ) as provider_span:
            provider_start = time.perf_counter()

            for target in targets:
                identifier = clean_string(getattr(target, "identifier", ""))
                domain = clean_string(getattr(target, "domain", None)) or None
                if not identifier and not domain:
                    continue
                for payload in provider.lookup(
                    identifier or domain or "",
                    domain,
                    provider_context,
                ):
                    payloads.append(payload)

            duration = time.perf_counter() - provider_start
            metrics = self._get_metrics()
            metrics.record_acquisition_duration(
                duration,
                scope="provider",
                agent=context.agent.name,
                provider=definition.name,
                extra_attributes={"target_count": len(targets)},
            )
            metrics.record_acquisition_records(
                len(payloads),
                scope="provider",
                agent=context.agent.name,
                provider=definition.name,
            )

            provider_span.set_attribute("hotpass.acquisition.duration_ms", duration * 1000)
            provider_span.set_attribute("hotpass.acquisition.records", len(payloads))

        return payloads

    def _apply_provenance(
        self,
        payload: ProviderPayload,
        agent: AgentDefinition,
        result: AgentResult,
    ) -> None:
        record = payload.record
        provenance = dict(payload.provenance)
        provenance.update(
            {
                "agent": agent.name,
                "confidence": payload.confidence,
            }
        )
        record.provenance = [provenance]
        result.records.append(record)
        result.provenance.append(provenance)

    def _create_provider(self, definition: ProviderDefinition) -> BaseProvider:
        return provider_registry.create(definition.name, definition.options)


def run_plan(
    plan: AcquisitionPlan,
    *,
    country_code: str,
    credentials: Mapping[str, str] | None = None,
) -> tuple[pd.DataFrame, list[AgentTiming], list[str]]:
    """Execute the acquisition plan and return a dataframe with collected records."""

    manager = AcquisitionManager(plan, credentials=credentials)
    return manager.run(country_code=country_code)
