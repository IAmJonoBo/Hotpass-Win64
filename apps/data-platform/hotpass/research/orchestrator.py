"""Adaptive research orchestrator coordinating deterministic and network passes."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Mapping, cast

import pandas as pd

from hotpass import observability
from hotpass.config import IndustryProfile
from hotpass.enrichment.pipeline import enrich_row
from hotpass.normalization import slugify
from hotpass.research.searx import (
    SearxQuery,
    SearxService,
    SearxServiceError,
    SearxServiceSettings,
)

try:  # pragma: no cover - optional dependency
    from scrapy.crawler import CrawlerProcess as _CrawlerProcess
except ImportError:  # pragma: no cover - optional dependency
    _CrawlerProcess = None

CrawlerProcess: Any | None = _CrawlerProcess

if TYPE_CHECKING:  # pragma: no cover - types only
    from scrapy.spiders import Spider as _SpiderProto
else:
    _SpiderProto = type("Spider", (), {})

try:  # pragma: no cover - optional dependency
    from scrapy.spiders import Spider as _SpiderRuntime
except ImportError:  # pragma: no cover - optional dependency
    _SpiderRuntime = _SpiderProto

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)

StepStatus = Literal["success", "skipped", "error"]


@dataclass(slots=True)
class AuthoritySnapshot:
    """Snapshot describing an authority source defined by the active profile."""

    name: str
    cache_key: str | None = None
    url: str | None = None
    description: str | None = None


@dataclass(slots=True)
class RateLimitPolicy:
    """Rate limit policy derived from the active profile."""

    min_interval_seconds: float
    burst: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_interval_seconds": self.min_interval_seconds,
            "burst": self.burst,
        }


@dataclass(slots=True)
class ResearchPlan:
    """Execution plan derived from the entity context and profile configuration."""

    entity_name: str
    entity_slug: str
    query: str | None
    target_urls: tuple[str, ...]
    row: pd.Series | None
    profile: IndustryProfile
    allow_network: bool
    authority_sources: tuple[AuthoritySnapshot, ...]
    backfill_fields: tuple[str, ...]
    rate_limit: RateLimitPolicy | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_name": self.entity_name,
            "entity_slug": self.entity_slug,
            "query": self.query,
            "target_urls": list(self.target_urls),
            "allow_network": self.allow_network,
            "authority_sources": [
                {
                    "name": snapshot.name,
                    "cache_key": snapshot.cache_key,
                    "url": snapshot.url,
                    "description": snapshot.description,
                }
                for snapshot in self.authority_sources
            ],
            "backfill_fields": list(self.backfill_fields),
            "rate_limit": self.rate_limit.to_dict() if self.rate_limit else None,
        }


@dataclass(slots=True)
class SearchQuery:
    """Describe an individual search query the agent should execute."""

    query: str
    rationale: str
    weight: float = 1.0
    filters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "rationale": self.rationale,
            "weight": self.weight,
            "filters": self.filters,
        }


@dataclass(slots=True)
class SearchStrategy:
    """Aggregate strategy returned for intelligent search orchestration."""

    primary_query: SearchQuery
    expanded_queries: tuple[SearchQuery, ...]
    site_hints: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_query": self.primary_query.to_dict(),
            "expanded_queries": [query.to_dict() for query in self.expanded_queries],
            "site_hints": list(self.site_hints),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class CrawlDirective:
    """Instruction defining how a crawl should proceed for a given URL."""

    url: str
    priority: int = 1
    depth: int = 1
    respect_robots: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "priority": self.priority,
            "depth": self.depth,
            "respect_robots": self.respect_robots,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class CrawlSchedule:
    """Schedule describing crawl directives and downstream expectations."""

    backend: str
    directives: tuple[CrawlDirective, ...]
    follow_up: tuple[str, ...]
    rate_limit: RateLimitPolicy | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "directives": [directive.to_dict() for directive in self.directives],
            "follow_up": list(self.follow_up),
            "rate_limit": self.rate_limit.to_dict() if self.rate_limit else None,
        }


@dataclass(slots=True)
class ResearchContext:
    """Inputs supplied by the CLI or MCP caller."""

    profile: IndustryProfile
    row: pd.Series | None = None
    entity_name: str | None = None
    query: str | None = None
    urls: Sequence[str] = ()
    allow_network: bool = False
    backfill_fields: Sequence[str] = ()


@dataclass(slots=True)
class ResearchStepResult:
    """Outcome of a single orchestrator step."""

    name: str
    status: StepStatus
    message: str
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResearchOutcome:
    """Aggregate result produced by the orchestrator."""

    plan: ResearchPlan
    steps: tuple[ResearchStepResult, ...]
    enriched_row: dict[str, Any] | None
    provenance: dict[str, Any] | None
    elapsed_seconds: float
    artifact_path: str | None = None

    @property
    def success(self) -> bool:
        return all(step.status != "error" for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "steps": [
                {
                    "name": step.name,
                    "status": step.status,
                    "message": step.message,
                    "artifacts": step.artifacts,
                }
                for step in self.steps
            ],
            "enriched_row": self.enriched_row,
            "provenance": self.provenance,
            "elapsed_seconds": self.elapsed_seconds,
            "success": self.success,
            "artifact_path": self.artifact_path,
        }


class ResearchOrchestrator:
    """Coordinate adaptive research loops across local, deterministic, and network passes."""

    def __init__(
        self,
        *,
        cache_root: Path | None = None,
        audit_log: Path | None = None,
        artefact_root: Path | None = None,
        searx_settings: Any | None = None,
        searx_service: SearxService | None = None,
    ) -> None:
        self.cache_root = cache_root or Path(".hotpass")
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.audit_log = audit_log or (self.cache_root / "mcp-audit.log")
        self.artefact_root = artefact_root or (self.cache_root / "research_runs")
        self.artefact_root.mkdir(parents=True, exist_ok=True)
        self._last_network_call: float | None = None
        self._rate_limit_policy: RateLimitPolicy | None = None
        self._burst_tokens: int | None = None
        self._metrics: Any | None = None
        self._searx_settings = SearxServiceSettings.from_payload(searx_settings)
        env_settings = SearxServiceSettings.from_environment()
        if env_settings.enabled:
            self._searx_settings = env_settings
        self._searx_service = searx_service

    def plan(self, context: ResearchContext) -> ResearchOutcome:
        """Build and execute a research plan."""

        plan = self._build_plan(context)
        outcome = self._execute(plan)
        self._write_audit_entry("plan", outcome)
        return outcome

    def intelligent_search(self, context: ResearchContext) -> SearchStrategy:
        """Derive an intelligent search strategy without executing the pipeline."""

        plan = self._build_plan(context)
        strategy = self._build_search_strategy(plan)
        self._write_structured_audit("search.strategy", strategy.to_dict())
        return strategy

    def coordinate_crawl(
        self,
        context: ResearchContext,
        *,
        backend: str = "deterministic",
    ) -> CrawlSchedule:
        """Build a crawl schedule that agents can execute incrementally."""

        plan = self._build_plan(context)
        schedule = self._build_crawl_schedule(plan, backend=backend)
        self._write_structured_audit("crawl.schedule", schedule.to_dict())
        return schedule

    def crawl(
        self,
        *,
        profile: IndustryProfile,
        query_or_url: str,
        allow_network: bool,
    ) -> ResearchOutcome:
        """Execute a crawl-only flow for MCP and CLI surfaces."""

        urls: list[str] = []
        query: str | None = None
        if query_or_url.startswith(("http://", "https://")):
            urls.append(query_or_url)
        else:
            query = query_or_url
        context = ResearchContext(
            profile=profile,
            query=query,
            urls=urls,
            allow_network=allow_network,
        )
        plan = self._build_plan(context)
        outcome = self._execute(plan, crawl_only=True)
        self._write_audit_entry("crawl", outcome)
        return outcome

    # --------------------------------------------------------------------- #
    # Plan construction
    # --------------------------------------------------------------------- #

    def _build_plan(self, context: ResearchContext) -> ResearchPlan:
        row = context.row
        entity_name = (
            context.entity_name
            or (
                str(row["organization_name"])
                if row is not None and "organization_name" in row
                else None
            )
            or context.query
            or "unknown-entity"
        )
        entity_slug = slugify(entity_name) or "entity"

        urls = list(_filter_blank(context.urls))
        if row is not None:
            website_value = row.get("website")
            if isinstance(website_value, str) and website_value.strip():
                urls.append(self._ensure_protocol(website_value.strip()))

        profile_backfill_fields = getattr(
            context.profile,
            "backfill_fields",
            tuple(context.profile.optional_fields),
        )

        authority_sources = tuple(
            AuthoritySnapshot(
                name=source.name,
                cache_key=source.cache_key,
                url=source.url,
                description=source.description,
            )
            for source in getattr(context.profile, "authority_sources", tuple())
        )

        backfill_fields = tuple(_filter_blank(context.backfill_fields or profile_backfill_fields))

        rate_limit_policy: RateLimitPolicy | None = None
        profile_rate_limit = getattr(context.profile, "research_rate_limit", None)
        if profile_rate_limit is not None:
            candidate = getattr(profile_rate_limit, "min_interval_seconds", None)
            burst_candidate = getattr(profile_rate_limit, "burst", None)
            if isinstance(candidate, (int, float)) and candidate > 0:
                burst_value: int | None = None
                if isinstance(burst_candidate, int) and burst_candidate > 0:
                    burst_value = burst_candidate
                rate_limit_policy = RateLimitPolicy(
                    min_interval_seconds=float(candidate),
                    burst=burst_value,
                )

        return ResearchPlan(
            entity_name=entity_name,
            entity_slug=entity_slug,
            query=context.query,
            target_urls=tuple(dict.fromkeys(urls)),  # preserve order while removing duplicates
            row=row,
            profile=context.profile,
            allow_network=context.allow_network,
            authority_sources=authority_sources,
            backfill_fields=backfill_fields,
            rate_limit=rate_limit_policy,
        )

    def _build_search_strategy(self, plan: ResearchPlan) -> SearchStrategy:
        base_query = plan.query or plan.entity_name
        primary = SearchQuery(
            query=base_query,
            rationale="Entity context provided by pipeline inputs",
            weight=1.0,
        )

        expanded: list[SearchQuery] = []
        seen = {primary.query.casefold()}

        for field_name, values in self._derive_row_tokens(plan.row).items():
            for value in values:
                query = f"{base_query} {value}".strip()
                key = query.casefold()
                if key in seen:
                    continue
                seen.add(key)
                expanded.append(
                    SearchQuery(
                        query=query,
                        rationale=f"Add {field_name} context from source row",
                        weight=0.85,
                        filters={"field": field_name},
                    )
                )

        for source in plan.authority_sources:
            if not source.name:
                continue
            query = f"{base_query} {source.name}".strip()
            key = query.casefold()
            if key in seen:
                continue
            seen.add(key)
            expanded.append(
                SearchQuery(
                    query=query,
                    rationale="Cross-reference authority source",
                    weight=0.7,
                    filters={"authority": source.name},
                )
            )

        site_hints = self._normalise_site_hints(plan)
        metadata = {
            "entity": plan.entity_slug,
            "profile": getattr(plan.profile, "name", "unknown"),
            "allow_network": plan.allow_network,
            "rate_limit": plan.rate_limit.to_dict() if plan.rate_limit else None,
            "authority_sources": [snapshot.name for snapshot in plan.authority_sources],
            "backfill_fields": list(plan.backfill_fields),
        }

        return SearchStrategy(
            primary_query=primary,
            expanded_queries=tuple(expanded),
            site_hints=site_hints,
            metadata=metadata,
        )

    def _build_crawl_schedule(self, plan: ResearchPlan, *, backend: str) -> CrawlSchedule:
        base_hints = list(self._normalise_site_hints(plan))
        authority_urls = [
            self._ensure_protocol(source.url)
            for source in plan.authority_sources
            if source.url
        ]
        seeds = list(dict.fromkeys(base_hints + authority_urls))

        directives: list[CrawlDirective] = []
        target_index = {
            self._ensure_protocol(url): index for index, url in enumerate(plan.target_urls)
        }
        for index, url in enumerate(seeds):
            directives.append(
                CrawlDirective(
                    url=url,
                    priority=1 if index == 0 else 2,
                    depth=3 if backend == "research" else 1,
                    respect_robots=backend != "research",
                    metadata={
                        "source": self._classify_seed(url, target_index, authority_urls),
                        "entity": plan.entity_slug,
                        "backend": backend,
                    },
                )
            )

        follow_up: list[str] = ["qa:linkcheck"]
        if plan.allow_network:
            follow_up.append("enrichment:network")
        if plan.backfill_fields:
            follow_up.append("backfill:fields")

        return CrawlSchedule(
            backend=backend,
            directives=tuple(directives),
            follow_up=tuple(dict.fromkeys(follow_up)),
            rate_limit=plan.rate_limit,
        )

    # --------------------------------------------------------------------- #
    # Execution
    # --------------------------------------------------------------------- #

    def _execute(self, plan: ResearchPlan, *, crawl_only: bool = False) -> ResearchOutcome:
        start = time.perf_counter()
        steps: list[ResearchStepResult] = []
        enriched_row: dict[str, Any] | None = None
        provenance: dict[str, Any] | None = None

        self._rate_limit_policy = plan.rate_limit
        if plan.rate_limit and plan.rate_limit.burst is not None:
            self._burst_tokens = plan.rate_limit.burst
        else:
            self._burst_tokens = None
        self._last_network_call = None

        if not crawl_only:
            steps.append(self._run_local_snapshot(plan))
            steps.append(self._run_authority_pass(plan))
            deterministic_step = self._run_deterministic_enrichment(plan)
            steps.append(deterministic_step)
            if deterministic_step.artifacts.get("enriched_row"):
                enriched_row = deterministic_step.artifacts["enriched_row"]
                provenance = deterministic_step.artifacts.get("provenance")

        searx_step = self._run_searx_search(plan)
        steps.append(searx_step)

        network_step = self._run_network_enrichment(plan, enriched_row=enriched_row)
        steps.append(network_step)
        if network_step.status == "success" and network_step.artifacts.get("enriched_row"):
            enriched_row = network_step.artifacts["enriched_row"]
            provenance = network_step.artifacts.get("provenance", provenance)

        steps.append(self._run_native_crawl(plan))
        if not crawl_only:
            steps.append(self._run_backfill_plan(plan, enriched_row=enriched_row))

        elapsed = time.perf_counter() - start
        outcome = ResearchOutcome(
            plan=plan,
            steps=tuple(steps),
            enriched_row=enriched_row,
            provenance=provenance,
            elapsed_seconds=elapsed,
        )
        self._persist_outcome(outcome)
        return outcome

    # --------------------------------------------------------------------- #
    # Individual steps
    # --------------------------------------------------------------------- #

    def _run_local_snapshot(self, plan: ResearchPlan) -> ResearchStepResult:
        slug = plan.entity_slug
        snapshot_path = self.cache_root / "snapshots" / f"{slug}.json"
        if snapshot_path.exists():
            try:
                payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:  # pragma: no cover - corrupted cache
                LOGGER.warning("Failed to parse cached snapshot for %s: %s", slug, exc)
                return ResearchStepResult(
                    name="local_snapshot",
                    status="error",
                    message=f"Cached snapshot exists but is invalid: {snapshot_path}",
                    artifacts={"path": str(snapshot_path)},
                )
            return ResearchStepResult(
                name="local_snapshot",
                status="success",
                message="Loaded cached snapshot",
                artifacts={
                    "path": str(snapshot_path),
                    "snapshot": payload,
                },
            )
        return ResearchStepResult(
            name="local_snapshot",
            status="skipped",
            message="No cached snapshot available",
            artifacts={"path": str(snapshot_path)},
        )

    def _run_authority_pass(self, plan: ResearchPlan) -> ResearchStepResult:
        slug = plan.entity_slug
        authority_hits: list[dict[str, Any]] = []
        for source in plan.authority_sources:
            cache_key = source.cache_key or slugify(source.name) or "default"
            path = self.cache_root / "authority" / cache_key / f"{slug}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:  # pragma: no cover - corrupted cache
                LOGGER.warning("Unable to parse authority snapshot %s: %s", path, exc)
                continue
            authority_hits.append(
                {
                    "source": source.name,
                    "path": str(path),
                    "snapshot": payload,
                }
            )

        if not authority_hits:
            return ResearchStepResult(
                name="authority_sources",
                status="skipped",
                message="No authority snapshots found for entity",
                artifacts={
                    "authority_sources": [snapshot.name for snapshot in plan.authority_sources],
                },
            )

        return ResearchStepResult(
            name="authority_sources",
            status="success",
            message=f"Loaded {len(authority_hits)} authority snapshots",
            artifacts={"snapshots": authority_hits},
        )

    def _run_deterministic_enrichment(self, plan: ResearchPlan) -> ResearchStepResult:
        if plan.row is None:
            return ResearchStepResult(
                name="deterministic_enrichment",
                status="skipped",
                message="No dataset row supplied – skipping deterministic enrichment",
            )

        try:
            enriched_row, provenance = enrich_row(
                plan.row,
                plan.profile,
                allow_network=False,
                confidence_threshold=0.7,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            LOGGER.error("Deterministic enrichment failed: %s", exc, exc_info=True)
            return ResearchStepResult(
                name="deterministic_enrichment",
                status="error",
                message=f"Deterministic enrichment failed: {exc}",
            )

        updated = _diff_row(plan.row, enriched_row)
        message = "Deterministic enrichment executed without updates"
        status: StepStatus = "skipped"
        if updated:
            message = f"Deterministic enrichment updated {len(updated)} fields"
            status = "success"

        return ResearchStepResult(
            name="deterministic_enrichment",
            status=status,
            message=message,
            artifacts={
                "updated_fields": updated,
                "enriched_row": enriched_row.to_dict(),
                "provenance": provenance,
            },
        )

    def _run_searx_search(self, plan: ResearchPlan) -> ResearchStepResult:
        service = self._resolve_searx_service()
        if service is None:
            return ResearchStepResult(
                name="searx_search",
                status="skipped",
                message="SearXNG integration disabled",
            )

        if not plan.allow_network:
            return ResearchStepResult(
                name="searx_search",
                status="skipped",
                message="Network access disabled; skipping SearXNG search",
            )

        terms = self._build_search_terms(plan)
        if not terms:
            return ResearchStepResult(
                name="searx_search",
                status="skipped",
                message="No search terms available for SearXNG",
            )

        queries = service.build_queries(terms)
        if not queries:
            return ResearchStepResult(
                name="searx_search",
                status="skipped",
                message="Unable to build SearXNG queries from supplied terms",
            )

        try:
            response = service.search(queries)
        except SearxServiceError as exc:  # pragma: no cover - defensive guard
            LOGGER.warning("SearXNG query failed: %s", exc)
            return ResearchStepResult(
                name="searx_search",
                status="error",
                message=f"SearXNG query failed: {exc}",
            )

        artifacts = {
            "queries": [query.term for query in response.queries],
            "from_cache": response.from_cache,
            "results": [result.to_dict() for result in response.results],
        }

        if not response.results:
            return ResearchStepResult(
                name="searx_search",
                status="skipped",
                message="SearXNG returned no candidate results",
                artifacts=artifacts,
            )

        merged_urls = list(plan.target_urls)
        for result in response.results:
            candidate = self._ensure_protocol(result.url)
            if candidate not in merged_urls:
                merged_urls.append(candidate)
        plan.target_urls = tuple(dict.fromkeys(merged_urls))

        message = f"SearXNG returned {len(response.results)} candidate result(s)"
        if response.from_cache:
            message += " (cache hit)"

        return ResearchStepResult(
            name="searx_search",
            status="success",
            message=message,
            artifacts=artifacts,
        )

    def _run_network_enrichment(
        self,
        plan: ResearchPlan,
        *,
        enriched_row: dict[str, Any] | None,
    ) -> ResearchStepResult:
        if not plan.allow_network:
            return ResearchStepResult(
                name="network_enrichment",
                status="skipped",
                message="Network enrichment disabled via flags",
            )

        if plan.row is None:
            return ResearchStepResult(
                name="network_enrichment",
                status="skipped",
                message="No dataset row supplied – skipping network enrichment",
            )

        self._maybe_throttle(plan.rate_limit)
        try:
            enriched_series, provenance = enrich_row(
                plan.row,
                plan.profile,
                allow_network=True,
                confidence_threshold=0.8,
            )
        except Exception as exc:  # pragma: no cover - network failure
            LOGGER.warning("Network enrichment failed: %s", exc)
            self._last_network_call = time.monotonic()
            return ResearchStepResult(
                name="network_enrichment",
                status="error",
                message=f"Network enrichment failed: {exc}",
            )

        self._last_network_call = time.monotonic()

        updated = _diff_row(plan.row, enriched_series)
        message = "Network enrichment executed without updates"
        status: StepStatus = "skipped"
        if updated:
            message = f"Network enrichment updated {len(updated)} fields"
            status = "success"

        return ResearchStepResult(
            name="network_enrichment",
            status=status,
            message=message,
            artifacts={
                "updated_fields": updated,
                "enriched_row": enriched_series.to_dict(),
                "provenance": provenance,
            },
        )

    def _run_native_crawl(self, plan: ResearchPlan) -> ResearchStepResult:
        if not plan.allow_network:
            return ResearchStepResult(
                name="native_crawl",
                status="skipped",
                message="Network disabled; crawler not executed",
            )

        if not plan.target_urls and not plan.query:
            return ResearchStepResult(
                name="native_crawl",
                status="skipped",
                message="No URLs or query provided for crawl step",
            )

        if CrawlerProcess is None:
            if requests is None or not plan.target_urls:
                return ResearchStepResult(
                    name="native_crawl",
                    status="skipped",
                    message="Scrapy not installed; emit plan for external crawler",
                    artifacts={
                        "urls": list(plan.target_urls),
                        "query": plan.query,
                    },
                )
            results: list[dict[str, Any]] = []
            failures: list[str] = []
            timeout = self._searx_settings.timeout
            for target_url in plan.target_urls:
                try:
                    self._maybe_throttle(plan.rate_limit)
                    metadata = self._fetch_with_retries(target_url, timeout=timeout)
                except Exception as exc:  # pragma: no cover - network failure
                    LOGGER.warning("Requests crawl failed for %s: %s", target_url, exc)
                    failures.append(str(exc))
                    continue
                else:
                    results.append(metadata)

            if not results:
                self._last_network_call = time.monotonic()
                return ResearchStepResult(
                    name="native_crawl",
                    status="skipped",
                    message="Requests crawl failed for all targets",
                    artifacts={"urls": list(plan.target_urls), "errors": failures},
                )

            self._last_network_call = time.monotonic()
            crawl_payload = {"results": results, "query": plan.query}
            crawl_artifact = self._persist_crawl_results(plan, crawl_payload)
            artifacts: dict[str, Any] = {"results": results, "query": plan.query}
            if crawl_artifact:
                artifacts["results_path"] = crawl_artifact
            if failures:
                artifacts["errors"] = failures
            message = "Fetched metadata via requests fallback"
            if failures:
                message += f" ({len(failures)} target(s) failed)"
            return ResearchStepResult(
                name="native_crawl",
                status="success",
                message=message,
                artifacts=artifacts,
            )

        # Construct a minimal spider when Scrapy is available. The spider gathers basic metadata
        # (status code, content length) so downstream steps can reason about completeness.
        results: list[dict[str, Any]] = []

        if TYPE_CHECKING:  # pragma: no cover - typing helper

            class _MetadataSpiderBase:  # pylint: disable=too-few-public-methods
                def make_requests_from_url(self, url: str) -> Any: ...

        else:
            _MetadataSpiderBase = cast(type[Any], _SpiderRuntime)

        class MetadataSpider(_MetadataSpiderBase):
            name = "hotpass_metadata_spider"

            def start_requests(self_inner) -> Iterable[Any]:
                for url in plan.target_urls:
                    yield self_inner.make_requests_from_url(url)

            def parse(self_inner, response: Any) -> None:
                results.append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "content_length": len(response.body),
                    }
                )

        process = CrawlerProcess(settings={"LOG_ENABLED": False})
        try:
            self._maybe_throttle(plan.rate_limit)
            process.crawl(MetadataSpider)
            process.start()
            self._last_network_call = time.monotonic()
        except Exception as exc:  # pragma: no cover - defensive guard
            LOGGER.warning("Scrapy crawl failed: %s", exc)
            self._last_network_call = time.monotonic()
            return ResearchStepResult(
                name="native_crawl",
                status="skipped",
                message=f"Scrapy crawl failed (non-fatal): {exc}",
                artifacts={"urls": list(plan.target_urls)},
            )

        message = "Scrapy crawl completed with metadata snapshots"
        if not results:
            message = "Scrapy crawl executed but yielded no metadata"

        crawl_artifact = self._persist_crawl_results(
            plan,
            {
                "results": results,
                "query": plan.query,
            },
        )

        artifacts = {
            "results": results,
            "query": plan.query,
        }
        if crawl_artifact:
            artifacts["results_path"] = crawl_artifact

        return ResearchStepResult(
            name="native_crawl",
            status="success",
            message=message,
            artifacts=artifacts,
        )

    def _run_backfill_plan(
        self,
        plan: ResearchPlan,
        *,
        enriched_row: dict[str, Any] | None,
    ) -> ResearchStepResult:
        if not plan.backfill_fields:
            return ResearchStepResult(
                name="backfill",
                status="skipped",
                message="Profile does not declare backfillable fields",
            )

        if plan.row is None:
            return ResearchStepResult(
                name="backfill",
                status="skipped",
                message="No dataset row supplied – skipping backfill planning",
            )

        missing = _fields_requiring_backfill(plan.row, plan.backfill_fields)
        if not missing:
            return ResearchStepResult(
                name="backfill",
                status="skipped",
                message="No backfillable fields require action",
            )

        return ResearchStepResult(
            name="backfill",
            status="success",
            message=f"Identified {len(missing)} fields for backfill attempts",
            artifacts={
                "fields": sorted(missing),
                "allow_network": plan.allow_network,
                "enriched_row": enriched_row,
            },
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _resolve_searx_service(self) -> SearxService | None:
        if not self._searx_settings.enabled:
            return None
        if self._searx_service is None:
            metrics = None
            try:
                metrics = self._get_metrics()
            except Exception:  # pragma: no cover - defensive guard
                metrics = None
            self._searx_service = SearxService(
                self._searx_settings,
                cache_root=self.cache_root,
                metrics=metrics,
            )
        return self._searx_service

    def _build_search_terms(self, plan: ResearchPlan) -> list[str]:
        terms: list[str] = []

        def _append(candidate: Any) -> None:
            if candidate is None:
                return
            value = str(candidate).strip()
            if value and value not in terms:
                terms.append(value)

        _append(plan.query)
        _append(plan.entity_name)
        if plan.entity_slug is not None:
            _append(plan.entity_slug.replace("-", " "))
        if plan.row is not None:
            _append(plan.row.get("organization_name"))
            website_value = plan.row.get("website")
            if isinstance(website_value, str) and website_value.strip():
                _append(website_value.strip())
        return terms

    def _get_metrics(self) -> Any:
        if self._metrics is None:
            self._metrics = observability.get_pipeline_metrics()
        return self._metrics

    def _fetch_with_retries(self, url: str, *, timeout: float) -> dict[str, Any]:
        if requests is None:  # pragma: no cover - defensive guard
            raise RuntimeError("requests is required for crawl retries")

        attempts = max(1, int(self._searx_settings.crawl_retry_attempts))
        backoff = max(0.0, float(self._searx_settings.crawl_retry_backoff_seconds))
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            start = time.perf_counter()
            try:
                response = requests.get(url, timeout=timeout)
            except Exception as exc:  # pragma: no cover - network failure
                duration = time.perf_counter() - start
                self._record_crawl_retry(url, attempt, exc, duration)
                last_exc = exc
                if attempt < attempts and backoff > 0:
                    time.sleep(backoff * attempt)
                continue
            duration = time.perf_counter() - start
            metadata = {
                "url": getattr(response, "url", url),
                "status": getattr(response, "status_code", None),
                "content_length": len(getattr(response, "content", b"")),
            }
            self._record_crawl_success(metadata["url"], duration, attempt)
            return metadata

        if last_exc is None:
            last_exc = RuntimeError(f"Failed to crawl {url}")
        self._record_crawl_failure(url, last_exc)
        raise last_exc

    def _record_crawl_success(self, url: str, duration: float, attempts: int) -> None:
        if not self._searx_settings.metrics_enabled:
            return
        metrics = self._get_metrics()
        metrics.record_research_crawl(
            duration,
            url=url,
            status="success",
            attempts=attempts,
        )

    def _record_crawl_retry(
        self, url: str, attempt: int, exc: Exception, duration: float
    ) -> None:
        if not self._searx_settings.metrics_enabled:
            return
        metrics = self._get_metrics()
        metrics.record_research_crawl_retry(url=url, attempt=attempt)
        metrics.record_research_crawl(
            duration,
            url=url,
            status="retry",
            attempts=attempt,
        )

    def _record_crawl_failure(self, url: str, exc: Exception) -> None:
        if not self._searx_settings.metrics_enabled:
            return
        metrics = self._get_metrics()
        metrics.record_research_crawl_failure(url=url, reason=str(exc))

    def _derive_row_tokens(self, row: pd.Series | None) -> dict[str, list[str]]:
        tokens: dict[str, list[str]] = {}
        if row is None:
            return tokens
        candidate_fields = {
            "province": "province",
            "state": "state",
            "region": "region",
            "country": "country",
            "city": "city",
            "industry": "industry",
            "segment": "segment",
        }
        for column, label in candidate_fields.items():
            value = row.get(column)
            values: list[Any] = []
            if isinstance(value, str):
                values = [value]
            elif isinstance(value, Mapping):
                values = [str(item) for item in value.values()]
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                values = list(value)
            elif value not in (None, ""):
                values = [value]

            for candidate in values:
                candidate_str = str(candidate).strip()
                if not candidate_str:
                    continue
                bucket = tokens.setdefault(label, [])
                if candidate_str not in bucket:
                    bucket.append(candidate_str)
        return tokens

    def _normalise_site_hints(self, plan: ResearchPlan) -> tuple[str, ...]:
        hints: list[str] = []
        for url in plan.target_urls:
            hints.append(self._ensure_protocol(url))
        row = plan.row
        if row is not None:
            website = row.get("website")
            if isinstance(website, str) and website.strip():
                hints.append(self._ensure_protocol(website.strip()))
        return tuple(dict.fromkeys(hints))

    def _classify_seed(
        self,
        url: str,
        target_index: Mapping[str, int],
        authority_urls: Sequence[str],
    ) -> str:
        normalised = self._ensure_protocol(url)
        if normalised in target_index:
            return "target"
        if normalised in authority_urls:
            return "authority"
        return "derived"

    def _write_audit_entry(self, action: str, outcome: ResearchOutcome) -> None:
        try:
            entry = {
                "action": action,
                "timestamp": time.time(),
                "entity": outcome.plan.entity_slug,
                "success": outcome.success,
                "steps": [
                    {"name": step.name, "status": step.status, "message": step.message}
                    for step in outcome.steps
                ],
            }
            with self.audit_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry))
                handle.write("\n")
        except Exception:  # pragma: no cover - audit logging is best effort
            LOGGER.debug("Failed to persist research audit entry", exc_info=True)

    def _write_structured_audit(self, action: str, payload: Mapping[str, Any]) -> None:
        try:
            entry = {
                "action": action,
                "timestamp": time.time(),
                "payload": payload,
            }
            with self.audit_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry))
                handle.write("\n")
        except Exception:  # pragma: no cover - audit logging is best effort
            LOGGER.debug("Failed to persist research audit entry", exc_info=True)

    def _persist_crawl_results(self, plan: ResearchPlan, payload: dict[str, Any]) -> str | None:
        try:
            timestamp = datetime.now(UTC)
            directory = self.artefact_root / plan.entity_slug / "crawl"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}.json"
            enriched_payload = {
                "entity": plan.entity_slug,
                "profile": getattr(plan.profile, "name", "unknown"),
                "query": plan.query,
                "target_urls": list(plan.target_urls),
                "recorded_at": timestamp.isoformat(),
            }
            enriched_payload.update(payload)
            path.write_text(json.dumps(enriched_payload, indent=2), encoding="utf-8")
            return str(path)
        except Exception:  # pragma: no cover - best effort persistence
            LOGGER.debug("Failed to persist crawl artefact", exc_info=True)
            return None

    def _persist_outcome(self, outcome: ResearchOutcome) -> None:
        try:
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            filename = f"{outcome.plan.entity_slug}-{timestamp}.json"
            path = self.artefact_root / filename
            path.write_text(json.dumps(outcome.to_dict(), indent=2), encoding="utf-8")
            outcome.artifact_path = str(path)
        except Exception:  # pragma: no cover - best effort persistence
            LOGGER.debug("Failed to persist research artefact", exc_info=True)

    def _maybe_throttle(self, rate_limit: RateLimitPolicy | None) -> None:
        if rate_limit is None:
            return

        min_interval = rate_limit.min_interval_seconds
        if min_interval <= 0:
            return

        now = time.monotonic()

        if rate_limit.burst is not None:
            if self._rate_limit_policy is not rate_limit:
                self._rate_limit_policy = rate_limit
                self._burst_tokens = rate_limit.burst
                self._last_network_call = None

            if self._burst_tokens is None:
                self._burst_tokens = rate_limit.burst

            if self._last_network_call is not None:
                elapsed = now - self._last_network_call
                if elapsed >= min_interval:
                    self._burst_tokens = rate_limit.burst

            if self._burst_tokens > 0:
                self._burst_tokens -= 1
                self._last_network_call = time.monotonic()
                return

            wait_for = min_interval
            if self._last_network_call is not None:
                elapsed = now - self._last_network_call
                if elapsed < min_interval:
                    wait_for = min_interval - elapsed
            if wait_for > 0:
                time.sleep(wait_for)
                now = time.monotonic()
            self._burst_tokens = rate_limit.burst - 1 if rate_limit.burst > 0 else 0
            self._last_network_call = now
            return

        if self._last_network_call is not None:
            elapsed = now - self._last_network_call
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
                now = time.monotonic()
        self._last_network_call = now

    @staticmethod
    def _ensure_protocol(url: str) -> str:
        if url.startswith(("http://", "https://")):
            return url
        return f"https://{url}"


def _filter_blank(values: Iterable[str]) -> Iterable[str]:
    for value in values:
        if value:
            candidate = str(value).strip()
            if candidate:
                yield candidate


def _diff_row(original: pd.Series, enriched: pd.Series) -> dict[str, tuple[Any, Any]]:
    updated: dict[str, tuple[Any, Any]] = {}
    for key, original_value in original.items():
        enriched_value = enriched.get(key)
        if pd.isna(original_value) and pd.isna(enriched_value):
            continue
        if original_value != enriched_value:
            updated[key] = (original_value, enriched_value)
    return updated


def _fields_requiring_backfill(row: pd.Series, fields: Sequence[str]) -> set[str]:
    missing: set[str] = set()
    for field_name in fields:
        if field_name not in row:
            continue
        value = row[field_name]
        if (
            value is None
            or (isinstance(value, float) and pd.isna(value))
            or (isinstance(value, str) and not value.strip())
        ):
            missing.add(field_name)
    return missing
