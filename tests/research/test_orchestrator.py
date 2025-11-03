from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from hotpass.config import IndustryProfile
from hotpass.research import ResearchContext, ResearchOrchestrator
from hotpass.research.searx import SearxQuery, SearxResponse, SearxResult, SearxServiceSettings


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_plan_offline_path(tmp_path):
    cache_root = tmp_path / ".hotpass"
    cache_root.mkdir()
    snapshots_dir = cache_root / "snapshots"
    snapshots_dir.mkdir()

    profile = IndustryProfile.from_dict(
        {
            "name": "test",
            "display_name": "Test Profile",
            "authority_sources": [
                {
                    "name": "Test Registry",
                    "cache_key": "registry",
                }
            ],
            "research_backfill": {
                "fields": ["contact_primary_email", "website"],
                "confidence_threshold": 0.7,
            },
            "research_rate_limit": {
                "min_interval_seconds": 1.0,
            },
        }
    )

    row = pd.Series(
        {
            "organization_name": "Example Flight School",
            "contact_primary_email": "",
            "website": "example.com",
        }
    )

    slug = "example-flight-school"
    snapshot_path = snapshots_dir / f"{slug}.json"
    snapshot_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    authority_dir = cache_root / "authority" / "registry"
    authority_dir.mkdir(parents=True)
    (authority_dir / f"{slug}.json").write_text(
        json.dumps({"registry": "hit"}),
        encoding="utf-8",
    )

    orchestrator = ResearchOrchestrator(cache_root=cache_root, audit_log=cache_root / "audit.log")
    context = ResearchContext(profile=profile, row=row, allow_network=False)
    outcome = orchestrator.plan(context)

    expect(
        outcome.plan.entity_slug == slug,
        "Entity slug should derive from organization name",
    )
    statuses = {step.name: step.status for step in outcome.steps}
    expect(statuses.get("local_snapshot") == "success", "Local snapshot should load")
    expect(statuses.get("authority_sources") == "success", "Authority snapshot should load")
    expect(statuses.get("searx_search") == "skipped", "SearX step skipped without network")
    expect(statuses.get("network_enrichment") == "skipped", "Network step disabled offline")
    expect(statuses.get("native_crawl") == "skipped", "Crawl skipped without network")
    expect(
        statuses.get("backfill") == "success",
        "Backfill step should flag missing fields",
    )
    rate_limit = outcome.plan.rate_limit
    if rate_limit is None:
        raise AssertionError("Plan should carry rate limit details from profile")
    expect(
        rate_limit.min_interval_seconds == 1.0,
        "Rate limit min interval should propagate into the plan",
    )
    artifact_path = outcome.artifact_path
    if artifact_path is None:
        raise AssertionError("Outcome should persist an artefact path")
    expect(Path(artifact_path).exists(), "Artefact file should be written to disk")

    audit_path = cache_root / "audit.log"
    expect(audit_path.exists(), "Audit log should be written")
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    expect(len(lines) == 1, "Audit log should contain a single entry")


def test_crawl_summary_without_network(tmp_path):
    cache_root = tmp_path / ".hotpass"
    cache_root.mkdir()
    profile = IndustryProfile.from_dict({"name": "generic", "display_name": "Generic"})

    orchestrator = ResearchOrchestrator(cache_root=cache_root, audit_log=cache_root / "audit.log")
    outcome = orchestrator.crawl(
        profile=profile,
        query_or_url="https://example.test",
        allow_network=False,
    )

    statuses = {step.name: step.status for step in outcome.steps}
    expect(
        statuses.get("searx_search") == "skipped",
        "SearX search should skip when network disabled",
    )
    expect(
        statuses.get("network_enrichment") == "skipped",
        "Network enrichment should skip when disabled",
    )
    expect(
        statuses.get("native_crawl") == "skipped",
        "Crawl should skip without network access",
    )


def test_intelligent_search_and_crawl_schedule(tmp_path):
    cache_root = tmp_path / ".hotpass"
    cache_root.mkdir()
    orchestrator = ResearchOrchestrator(
        cache_root=cache_root,
        audit_log=cache_root / "audit.log",
        artefact_root=cache_root / "runs",
    )

    profile = IndustryProfile.from_dict(
        {
            "name": "aviation",
            "display_name": "Aviation",
            "authority_sources": [
                {"name": "Civil Aviation Authority", "url": "caa.example"}
            ],
            "research_rate_limit": {"min_interval_seconds": 2.0, "burst": 3},
        }
    )

    row = pd.Series(
        {
            "organization_name": "SkyLift Training",
            "province": "Gauteng",
            "industry": ["Aviation", "Training"],
            "website": "skylift.example",
        }
    )

    context = ResearchContext(
        profile=profile,
        row=row,
        query="SkyLift Training",
        urls=["https://skylift.example", "skylift.example"],
        allow_network=True,
    )

    strategy = orchestrator.intelligent_search(context)
    filters = [query.filters for query in strategy.expanded_queries]
    assert any(mapping.get("field") == "province" for mapping in filters)
    assert any("Aviation" in query.query for query in strategy.expanded_queries)
    assert "https://skylift.example" in strategy.site_hints
    assert "Civil Aviation Authority" in strategy.metadata["authority_sources"]
    assert strategy.metadata["allow_network"] is True

    schedule = orchestrator.coordinate_crawl(context, backend="research")
    assert schedule.backend == "research"
    assert schedule.rate_limit and schedule.rate_limit.min_interval_seconds == 2.0
    assert "enrichment:network" in schedule.follow_up
    assert "qa:linkcheck" in schedule.follow_up
    directive_sources = {directive.metadata["source"] for directive in schedule.directives}
    assert {"target", "authority"}.issubset(directive_sources)


def test_crawl_persists_artifact_and_rate_limit(tmp_path, monkeypatch):
    cache_root = tmp_path / ".hotpass"
    cache_root.mkdir()

    profile = IndustryProfile.from_dict(
        {
            "name": "burst-profile",
            "display_name": "Burst Profile",
            "research_rate_limit": {
                "min_interval_seconds": 0.1,
                "burst": 2,
            },
        }
    )

    orchestrator = ResearchOrchestrator(cache_root=cache_root, audit_log=cache_root / "audit.log")

    class _StubResponse:
        def __init__(self, url: str) -> None:
            self.url = url
            self.status_code = 200
            self.content = b"stub-content"

    class _StubRequests:
        def get(self, url: str, timeout: float):
            return _StubResponse(url)

    monkeypatch.setattr("hotpass.research.orchestrator.CrawlerProcess", None, raising=False)
    monkeypatch.setattr("hotpass.research.orchestrator.requests", _StubRequests(), raising=False)

    outcome = orchestrator.crawl(
        profile=profile,
        query_or_url="https://example.test",
        allow_network=True,
    )

    statuses = {step.name: step.status for step in outcome.steps}
    expect(
        statuses.get("searx_search") == "skipped",
        "SearX step should skip when service disabled",
    )
    expect(
        statuses.get("native_crawl") == "success",
        "Native crawl should succeed under stubbed requests",
    )

    native_crawl_step = next(step for step in outcome.steps if step.name == "native_crawl")
    artifacts = native_crawl_step.artifacts
    if artifacts is None:
        raise AssertionError("Native crawl artifacts should be populated")
    results_path = artifacts.get("results_path")
    if not isinstance(results_path, str):
        raise AssertionError("Native crawl should record results path")
    stored_path = Path(results_path)
    expect(stored_path.exists(), "Stored crawl artefact should exist on disk")

    payload = json.loads(stored_path.read_text(encoding="utf-8"))
    expect(
        payload.get("entity") == outcome.plan.entity_slug,
        "Crawl artefact should capture entity slug",
    )
    expect(payload.get("results"), "Crawl artefact should include crawl results")
    rate_limit = outcome.plan.rate_limit
    if rate_limit is None:
        raise AssertionError("Plan should capture rate limit when configured")
    expect(
        rate_limit.burst == 2,
        "Burst value from profile should be preserved in the plan",
    )


def test_searx_search_enriches_plan(tmp_path, monkeypatch):
    cache_root = tmp_path / ".hotpass"
    cache_root.mkdir()

    profile = IndustryProfile.from_dict({"name": "generic", "display_name": "Generic"})

    class _StubSearxService:
        def __init__(self) -> None:
            self.received_terms: list[str] = []

        def build_queries(self, terms: list[str]) -> list[SearxQuery]:
            self.received_terms.extend(terms)
            return [SearxQuery(term=term) for term in terms]

        def search(self, queries: list[SearxQuery]) -> SearxResponse:
            results = (
                SearxResult(title="Example", url="https://example.test"),
                SearxResult(title="Alt", url="https://example.test/about"),
            )
            return SearxResponse(tuple(queries), results, from_cache=False)

    class _StubResponse:
        def __init__(self, url: str) -> None:
            self.url = url
            self.status_code = 200
            self.content = b"ok"

    class _StubRequests:
        def __init__(self) -> None:
            self.invocations: list[str] = []

        def get(self, url: str, timeout: float) -> _StubResponse:
            self.invocations.append(url)
            return _StubResponse(url)

    stub_requests = _StubRequests()
    monkeypatch.setattr(
        "hotpass.research.orchestrator.requests", stub_requests, raising=False
    )

    stub_service = _StubSearxService()
    orchestrator = ResearchOrchestrator(
        cache_root=cache_root,
        audit_log=cache_root / "audit.log",
        searx_settings=SearxServiceSettings(enabled=True),
        searx_service=stub_service,
    )

    row = pd.Series({"organization_name": "Example Org"})
    context = ResearchContext(profile=profile, row=row, allow_network=True)
    outcome = orchestrator.plan(context)

    statuses = {step.name: step.status for step in outcome.steps}
    expect(statuses.get("searx_search") == "success", "SearX step should succeed")
    native_step = next(step for step in outcome.steps if step.name == "native_crawl")
    expect(native_step.status == "success", "Native crawl should succeed with SearX URLs")
    expect(
        "https://example.test" in outcome.plan.target_urls,
        "SearX results should populate plan target URLs",
    )
    expect(stub_requests.invocations, "Requests fallback should be invoked")


def test_requests_crawl_retries_on_failure(tmp_path, monkeypatch):
    cache_root = tmp_path / ".hotpass"
    cache_root.mkdir()

    profile = IndustryProfile.from_dict({"name": "generic", "display_name": "Generic"})

    class _FlakyRequests:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str, timeout: float) -> _StubResponse:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary failure")
            return _StubResponse(url)

    class _StubResponse:
        def __init__(self, url: str) -> None:
            self.url = url
            self.status_code = 200
            self.content = b"ok"

    flaky = _FlakyRequests()
    monkeypatch.setattr(
        "hotpass.research.orchestrator.requests", flaky, raising=False
    )

    settings = SearxServiceSettings(
        enabled=False,
        crawl_retry_attempts=2,
        crawl_retry_backoff_seconds=0.0,
        timeout=0.1,
    )
    orchestrator = ResearchOrchestrator(
        cache_root=cache_root,
        audit_log=cache_root / "audit.log",
        searx_settings=settings,
    )

    outcome = orchestrator.crawl(
        profile=profile,
        query_or_url="https://example.test/retry",
        allow_network=True,
    )

    native_step = next(step for step in outcome.steps if step.name == "native_crawl")
    expect(native_step.status == "success", "Native crawl should recover after retry")
    artifacts = native_step.artifacts or {}
    results = artifacts.get("results", [])
    expect(results, "Crawl results should be captured")
    expect(flaky.calls == 2, "Crawler should retry once before succeeding")
