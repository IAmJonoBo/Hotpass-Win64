"""Task orchestration utilities for acquisition agents."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, assert_never

from ...enrichment.providers import BaseProvider, CredentialStore, ProviderContext, ProviderRegistry
from ...normalization import clean_string, normalize_email, normalize_phone, normalize_website
from .. import RawRecord
from .base import AgentContext, AgentResult
from .config import (
    AgentDefinition,
    AgentTaskDefinition,
    AgentTaskKind,
    ProviderDefinition,
    TargetDefinition,
)


@dataclass(slots=True)
class _TaskState:
    """Mutable state passed between task stages."""

    targets: list[TargetDefinition] = field(default_factory=list)
    records: list[RawRecord] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def execute_agent_tasks(
    agent: AgentDefinition,
    context: AgentContext,
    registry: ProviderRegistry,
    credential_store: CredentialStore,
) -> AgentResult:
    """Execute configured tasks for an agent returning a consolidated result."""

    result = AgentResult(agent_name=agent.name)
    state = _TaskState(targets=list(_initial_targets(agent)))

    tasks = list(agent.active_tasks())
    if not tasks:
        # Backwards compatibility: treat providers as API tasks when tasks are omitted.
        tasks.extend(
            AgentTaskDefinition(
                name=provider.name,
                kind=AgentTaskKind.API,
                provider=provider.name,
                options=provider.options,
                enabled=provider.enabled,
            )
            for provider in agent.providers
        )

    provider_lookup = {provider.name.lower(): provider for provider in agent.providers}

    for task in tasks:
        if not task.enabled:
            continue
        if task.kind is AgentTaskKind.SEARCH:
            _run_search_task(task, agent, context, state)
        elif task.kind is AgentTaskKind.CRAWL:
            _run_crawl_task(task, context, state)
        elif task.kind is AgentTaskKind.API:
            _run_api_task(
                task,
                context,
                state,
                provider_lookup,
                registry,
                credential_store,
            )
        else:
            assert_never(task.kind)

    result.targets.extend(state.targets)
    result.records.extend(state.records)
    result.provenance.extend(state.provenance)
    result.warnings.extend(state.warnings)
    return result


def _initial_targets(agent: AgentDefinition) -> Iterable[TargetDefinition]:
    active = agent.active_targets()
    if active:
        return list(active)
    seeds: list[TargetDefinition] = []
    for term in agent.search_terms:
        cleaned = clean_string(term)
        if not cleaned:
            continue
        seeds.append(TargetDefinition(identifier=cleaned))
    return seeds


def _policy_allows(policies: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    if not policies:
        return True, []
    reasons: list[str] = []
    if policies.get("robots_allowed") is False:
        reasons.append("robots.txt disallows access")
    tos_ack = policies.get("tos_accepted")
    if tos_ack is False:
        reasons.append("terms of service not accepted")
    return not reasons, reasons


def _append_warning(state: _TaskState, task: AgentTaskDefinition, reasons: Sequence[str]) -> None:
    reason_text = "; ".join(reasons)
    state.warnings.append(f"{task.name}: {reason_text}")


def _run_search_task(
    task: AgentTaskDefinition,
    agent: AgentDefinition,
    context: AgentContext,
    state: _TaskState,
) -> None:
    task_options: Mapping[str, Any] = task.options if isinstance(task.options, Mapping) else {}
    raw_policies = task_options.get("policies")
    policies: Mapping[str, Any] = raw_policies if isinstance(raw_policies, Mapping) else {}
    allowed, reasons = _policy_allows(policies)
    if not allowed:
        _append_warning(state, task, reasons)
        return

    dataset_raw = task_options.get("results", {})
    if not isinstance(dataset_raw, Mapping):
        state.warnings.append(f"{task.name}: search results payload must be a mapping")
        return
    dataset: Mapping[str, Any] = dataset_raw

    query_keys = _search_queries(agent, state.targets)
    seen = {(target.identifier, target.domain) for target in state.targets}
    for key in query_keys:
        matches = dataset.get(key) or dataset.get(key.lower()) or dataset.get(key.upper())
        if not matches:
            state.provenance.append(
                {
                    "task": task.name,
                    "kind": AgentTaskKind.SEARCH.value,
                    "query": key,
                    "result_count": 0,
                    "provider": task.provider or "search",
                    "compliance": {
                        "robots_allowed": policies.get("robots_allowed", True),
                        "terms_of_service": policies.get("tos_url"),
                    },
                }
            )
            continue
        for entry in matches:
            if isinstance(entry, Mapping):
                identifier = clean_string(entry.get("identifier"))
                domain = clean_string(entry.get("domain"))
                location = clean_string(entry.get("location"))
                metadata = dict(entry.get("metadata", {}))
            else:
                identifier = None
                domain = None
                location = None
                metadata = {}
            if not identifier and not domain:
                identifier = key
            candidate = TargetDefinition(
                identifier=identifier or key,
                domain=domain,
                location=location,
                metadata=metadata,
            )
            marker = (candidate.identifier, candidate.domain)
            if marker not in seen:
                seen.add(marker)
                state.targets.append(candidate)
        state.provenance.append(
            {
                "task": task.name,
                "kind": AgentTaskKind.SEARCH.value,
                "query": key,
                "result_count": len(matches),
                "provider": task.provider or "search",
                "compliance": {
                    "robots_allowed": policies.get("robots_allowed", True),
                    "terms_of_service": policies.get("tos_url"),
                },
            }
        )


def _run_crawl_task(
    task: AgentTaskDefinition,
    context: AgentContext,
    state: _TaskState,
) -> None:
    task_options: Mapping[str, Any] = task.options if isinstance(task.options, Mapping) else {}
    raw_policies = task_options.get("policies")
    policies: Mapping[str, Any] = raw_policies if isinstance(raw_policies, Mapping) else {}
    allowed, reasons = _policy_allows(policies)
    if not allowed:
        _append_warning(state, task, reasons)
        return

    pages_raw = task_options.get("pages", {})
    if not isinstance(pages_raw, Mapping):
        state.warnings.append(f"{task.name}: crawl pages payload must be a mapping")
        return
    pages: Mapping[str, Any] = pages_raw

    dataset_name = clean_string(task_options.get("source_dataset"))
    source_dataset = dataset_name or "Web Crawl"

    for target in state.targets:
        lookup_keys = [target.identifier]
        if target.domain:
            lookup_keys.append(target.domain)
        page: Mapping[str, Any] | None = None
        for key in lookup_keys:
            if not key:
                continue
            candidate = pages.get(key)
            if isinstance(candidate, Mapping):
                page = candidate
                break
        if not page:
            continue
        organisation = clean_string(page.get("organization_name")) or target.identifier
        contacts = page.get("contacts", [])
        emails: list[str] = []
        phones: list[str] = []
        names: list[str] = []
        roles: list[str] = []
        for contact in contacts:
            if not isinstance(contact, Mapping):
                continue
            name = clean_string(contact.get("name"))
            if name:
                names.append(name)
            role = clean_string(contact.get("role"))
            if role:
                roles.append(role)
            email_value = normalize_email(contact.get("email")) if contact.get("email") else None
            if email_value:
                emails.append(email_value)
            phone_value = (
                normalize_phone(contact.get("phone"), country_code=context.country_code)
                if contact.get("phone")
                else None
            )
            if phone_value:
                phones.append(phone_value)
        provenance = {
            "task": task.name,
            "kind": AgentTaskKind.CRAWL.value,
            "provider": task.provider or "crawler",
            "source": clean_string(page.get("source")) or source_dataset,
            "retrieved_at": context.issued_at.isoformat(),
            "compliance": {
                "robots_allowed": policies.get("robots_allowed", True),
                "terms_of_service": policies.get("tos_url"),
            },
        }
        website_value = normalize_website(page.get("website"))
        description_value = clean_string(page.get("description"))
        notes_value = clean_string(page.get("notes"))
        record = RawRecord(
            organization_name=organisation,
            source_dataset=source_dataset,
            source_record_id=f"{task.name}:{target.identifier}",
            website=website_value,
            description=description_value,
            notes=notes_value,
            contact_names=names or None,
            contact_roles=roles or None,
            contact_emails=emails or None,
            contact_phones=phones or None,
            provenance=[provenance],
        )
        state.records.append(record)
        state.provenance.append(provenance)


def _run_api_task(
    task: AgentTaskDefinition,
    context: AgentContext,
    state: _TaskState,
    providers: Mapping[str, ProviderDefinition],
    registry: ProviderRegistry,
    credential_store: CredentialStore,
) -> None:
    provider_name = (task.provider or task.name or "").lower()
    provider_definition = providers.get(provider_name)
    if provider_definition is None:
        missing_provider = task.provider or task.name
        state.warnings.append(f"{task.name}: provider '{missing_provider}' is not defined")
        return

    overrides = task.options if isinstance(task.options, Mapping) else {}
    merged_options = provider_definition.merged_options(overrides)
    raw_policies = merged_options.get("policies")
    policies: Mapping[str, Any] = raw_policies if isinstance(raw_policies, Mapping) else {}
    allowed, reasons = _policy_allows(policies)
    if not allowed:
        _append_warning(state, task, reasons)
        return

    credential_value, cached, reference = credential_store.fetch(provider_definition.name)
    requires_credentials = merged_options.get("requires_credentials")
    if requires_credentials and credential_value is None:
        state.warnings.append(
            f"Task '{task.name}': missing credential for provider '{provider_definition.name}'"
        )
        return

    provider = _create_provider(registry, provider_definition.name, merged_options)
    provider_context = ProviderContext(
        country_code=context.country_code,
        credentials=context.credentials,
        issued_at=context.issued_at,
        credential_store=credential_store,
    )
    for target in state.targets:
        identifier = clean_string(getattr(target, "identifier", None)) or ""
        domain = clean_string(getattr(target, "domain", None)) or None
        for payload in provider.lookup(identifier, domain, provider_context):
            provenance = dict(payload.provenance)
            provenance.update(
                {
                    "task": task.name,
                    "kind": AgentTaskKind.API.value,
                    "provider": provider_definition.name,
                }
            )
            provenance.setdefault("confidence", payload.confidence)
            if reference:
                provenance.setdefault("credentials", {}).update(
                    {
                        "reference": reference,
                        "cached": cached,
                        "available": credential_value is not None,
                    }
                )
            record = payload.record
            record.provenance = [provenance]
            state.records.append(record)
            state.provenance.append(provenance)


def _create_provider(
    registry: ProviderRegistry,
    name: str,
    options: Mapping[str, Any] | None,
) -> BaseProvider:
    return registry.create(name, options)


def _search_queries(agent: AgentDefinition, targets: Sequence[TargetDefinition]) -> list[str]:
    queries: list[str] = []
    for target in targets:
        if target.identifier:
            queries.append(target.identifier)
        elif target.domain:
            queries.append(target.domain)
    if not queries:
        queries.extend(agent.search_terms)
    cleaned = []
    seen: set[str] = set()
    for query in queries:
        candidate = clean_string(query)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned


__all__ = [
    "AgentTaskDefinition",
    "AgentTaskKind",
    "execute_agent_tasks",
]
