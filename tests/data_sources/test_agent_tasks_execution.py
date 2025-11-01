"""Regression coverage for acquisition agent task execution helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from hotpass.data_sources import RawRecord
from hotpass.data_sources.agents.base import AgentContext
from hotpass.data_sources.agents.config import (
    AcquisitionPlan,
    AgentDefinition,
    AgentTaskDefinition,
    AgentTaskKind,
    ProviderDefinition,
)
from hotpass.data_sources.agents.tasks import execute_agent_tasks
from hotpass.enrichment.providers import (
    BaseProvider,
    CredentialStore,
    ProviderContext,
    ProviderPayload,
    ProviderRegistry,
)

from tests.helpers.fixtures import fixture


def expect(condition: bool, message: str) -> None:
    """Project helper for expectation-style assertions."""

    if not condition:
        raise AssertionError(message)


class MemoryCredentialStore(CredentialStore):
    """Configurable credential store used to exercise task branches."""

    def __init__(
        self,
        *,
        value: str | None,
        cached: bool,
        reference: str | None,
    ) -> None:
        self._value = value
        self._cached = cached
        self._reference = reference
        self.fetches: list[tuple[str, tuple[str, ...]]] = []

    def fetch(
        self, provider_name: str, aliases: Sequence[str] | None = None
    ) -> tuple[str | None, bool, str | None]:
        alias_tuple = tuple(aliases or ())
        self.fetches.append((provider_name, alias_tuple))
        return self._value, self._cached, self._reference


class FakeProvider(BaseProvider):
    """Provider that always emits a deterministic record for testing."""

    name = "fake"

    def lookup(
        self,
        target_identifier: str,
        target_domain: str | None,
        context: ProviderContext,
    ) -> Sequence[ProviderPayload]:
        record = RawRecord(
            organization_name=target_identifier or target_domain or "Unknown",
            source_dataset="API",
            source_record_id=f"{target_identifier or target_domain}:record",
            website="https://api.example.com",
        )
        provenance = {"source": "fake", "issued_at": context.issued_at.isoformat()}
        return [ProviderPayload(record=record, provenance=provenance, confidence=0.75)]


@fixture
def provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("fake", FakeProvider)
    return registry


def _build_context(agent: AgentDefinition) -> AgentContext:
    plan = AcquisitionPlan(enabled=True, agents=(agent,))
    return AgentContext(
        plan=plan,
        agent=agent,
        credentials={},
        country_code="ZA",
        issued_at=datetime.now(tz=UTC),
    )


def test_execute_agent_tasks_combines_search_crawl_and_api(
    provider_registry: ProviderRegistry,
) -> None:
    search_options = {
        "policies": {"robots_allowed": True, "tos_url": "https://example.com/tos"},
        "results": {
            "acme": [
                {
                    "identifier": "Acme Aviation",
                    "domain": "acme.example.com",
                    "location": "Cape Town",
                    "metadata": {"source": "seed"},
                },
                {"identifier": None, "domain": None, "metadata": {}},
            ]
        },
    }
    crawl_options = {
        "policies": {"robots_allowed": True, "tos_url": "https://example.com/tos"},
        "source_dataset": "Registry",
        "pages": {
            "acme aviation": {
                "organization_name": "Acme Aviation",
                "website": "https://acme.example.com",
                "description": "Gov supplier",
                "notes": "Priority",
                "contacts": [
                    {
                        "name": "Jane Doe",
                        "role": "Director",
                        "email": "jane@acme.com",
                        "phone": "+27 (0)11 555 1234",
                    },
                    {"name": "Support Team", "email": "team@acme.com"},
                ],
            }
        },
    }
    agent = AgentDefinition(
        name="acme",
        search_terms=("Acme",),
        providers=(
            ProviderDefinition(
                name="fake",
                options={"requires_credentials": True},
            ),
        ),
        tasks=(
            AgentTaskDefinition(name="search", kind=AgentTaskKind.SEARCH, options=search_options),
            AgentTaskDefinition(name="crawl", kind=AgentTaskKind.CRAWL, options=crawl_options),
            AgentTaskDefinition(
                name="api",
                kind=AgentTaskKind.API,
                provider="fake",
                options={"requires_credentials": True},
            ),
        ),
    )
    credential_store = MemoryCredentialStore(value="token", cached=True, reference="vault:demo")
    context = _build_context(agent)

    result = execute_agent_tasks(agent, context, provider_registry, credential_store)

    expect(
        any(target.domain == "acme.example.com" for target in result.targets),
        "Search should add targets",
    )
    expect(bool(result.records), "Crawl/API tasks should produce records")
    expect(bool(result.provenance), "Provenance entries should be recorded")
    expect(not result.warnings, "No warnings expected for successful flow")
    expect(bool(credential_store.fetches), "Credential store should be queried")


def test_execute_agent_tasks_handles_policy_warnings(
    provider_registry: ProviderRegistry,
) -> None:
    agent = AgentDefinition(
        name="blocked",
        search_terms=("Restricted",),
        providers=(ProviderDefinition(name="fake"),),
        tasks=(
            AgentTaskDefinition(
                name="search",
                kind=AgentTaskKind.SEARCH,
                options={"policies": {"robots_allowed": False}},
            ),
            AgentTaskDefinition(
                name="crawl",
                kind=AgentTaskKind.CRAWL,
                options={
                    "policies": {"robots_allowed": False, "tos_accepted": False},
                    "pages": {},
                },
            ),
        ),
    )
    credential_store = MemoryCredentialStore(value=None, cached=False, reference=None)
    context = _build_context(agent)

    result = execute_agent_tasks(agent, context, provider_registry, credential_store)

    expect(result.records == [], "Disallowed policies should skip records")
    expect(len(result.warnings) >= 2, "Warnings should capture policy failures")


def test_execute_agent_tasks_falls_back_to_providers_when_no_tasks(
    provider_registry: ProviderRegistry,
) -> None:
    agent = AgentDefinition(
        name="fallback",
        search_terms=("Fallback",),
        providers=(
            ProviderDefinition(
                name="fake",
                options={"requires_credentials": True},
            ),
        ),
        tasks=(),
    )
    credential_store = MemoryCredentialStore(value=None, cached=False, reference="ref-1")
    context = _build_context(agent)

    result = execute_agent_tasks(agent, context, provider_registry, credential_store)

    expect(result.records == [], "Missing credentials should block fallback task records")
    expect(
        bool(result.warnings),
        "Fallback execution should emit missing credential warning",
    )
    expect(
        bool(credential_store.fetches),
        "Fallback should still attempt to resolve credentials",
    )
