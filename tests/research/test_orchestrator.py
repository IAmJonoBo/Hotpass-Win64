from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from hotpass.config import IndustryProfile
from hotpass.research import ResearchContext, ResearchOrchestrator


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
        statuses.get("network_enrichment") == "skipped",
        "Network enrichment should skip when disabled",
    )
    expect(
        statuses.get("native_crawl") == "skipped",
        "Crawl should skip without network access",
    )
    if outcome.artifact_path:
        expect(Path(outcome.artifact_path).exists(), "Crawl artefact should be written")


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
