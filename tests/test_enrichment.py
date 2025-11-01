"""Tests for enrichment module."""

from __future__ import annotations

import json
import tempfile
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from tests.helpers.fixtures import fixture
from tests.helpers.pytest_marks import parametrize

pytest.importorskip("frictionless")

import hotpass.enrichment as enrichment  # noqa: E402
from hotpass.enrichment import (
    CacheManager,
    enrich_dataframe_with_registries,
    enrich_dataframe_with_websites,
    enrich_dataframe_with_websites_concurrent,
    extract_website_content,
)
from hotpass.enrichment.intent import (
    IntentCollectorDefinition,
    IntentPlan,
    IntentTargetDefinition,
    run_intent_plan,
)

from tests.helpers.assertions import expect


@fixture(autouse=True)
def reset_enrichment_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure optional dependency flags start from a clean slate."""

    monkeypatch.setattr(enrichment, "REQUESTS_AVAILABLE", True, raising=False)
    monkeypatch.setattr(enrichment, "TRAFILATURA_AVAILABLE", True, raising=False)


@fixture
def temp_cache() -> Iterator[CacheManager]:
    """Create temporary cache for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = CacheManager(db_path=f"{tmpdir}/test_cache.db", ttl_hours=1)
        yield cache


def test_cache_manager_init(temp_cache):
    """Test cache manager initialization."""
    expect(temp_cache.db_path.exists(), "Cache database path should exist after init")
    stats = temp_cache.stats()
    expect(stats["total_entries"] == 0, "Cache should start with zero entries")
    expect(stats["total_hits"] == 0, "Cache should start without any hits")


def test_cache_set_and_get(temp_cache):
    """Test setting and getting cache values."""
    temp_cache.set("test_key", "test_value")
    value = temp_cache.get("test_key")
    expect(value == "test_value", "Cache should return stored value for key")


def test_cache_get_nonexistent(temp_cache):
    """Test getting nonexistent key returns None."""
    value = temp_cache.get("nonexistent")
    expect(value is None, "Unknown cache key should return None")


def test_cache_delete(temp_cache):
    """Test deleting cache entries."""
    temp_cache.set("test_key", "test_value")
    temp_cache.delete("test_key")
    value = temp_cache.get("test_key")
    expect(value is None, "Deleted cache key should return None")


def test_cache_hit_count(temp_cache):
    """Test cache hit counting."""
    temp_cache.set("test_key", "test_value")

    # Access the key multiple times
    for _ in range(5):
        temp_cache.get("test_key")

    stats = temp_cache.stats()
    expect(stats["total_hits"] == 5, "Cache should count five hits after repeated access")


def test_cache_stats(temp_cache):
    """Test cache statistics."""
    temp_cache.set("key1", "value1")
    temp_cache.set("key2", "value2")
    temp_cache.get("key1")
    temp_cache.get("key1")

    stats = temp_cache.stats()
    expect(stats["total_entries"] == 2, "Cache should track two stored entries")
    expect(stats["total_hits"] == 2, "Cache should count two total hits across entries")
    expect(
        stats["avg_hits_per_entry"] == 1.0,
        "Average hits per entry should equal 1.0 after two hits on two entries",
    )


def test_cache_clear_expired(temp_cache):
    """Test clearing expired entries."""
    # Set TTL to 0 hours for testing
    temp_cache.ttl = temp_cache.ttl.__class__(hours=0)
    temp_cache.set("test_key", "test_value")

    # Clear expired entries
    count = temp_cache.clear_expired()
    expect(count == 1, "Clear expired should remove a single entry with zero TTL")

    # Verify key is gone
    value = temp_cache.get("test_key")
    expect(value is None, "Expired cache entry should be removed")


@patch("hotpass.enrichment.TRAFILATURA_AVAILABLE", True)
@patch("hotpass.enrichment.REQUESTS_AVAILABLE", True)
@patch("hotpass.enrichment.requests", create=True)
@patch("hotpass.enrichment.trafilatura", create=True)
def test_extract_website_content_success(mock_trafilatura, mock_requests, temp_cache):
    """Test successful website content extraction."""
    # Mock response
    mock_response = Mock()
    mock_response.text = "<html><body>Test content</body></html>"
    mock_response.raise_for_status = Mock()
    mock_requests.get.return_value = mock_response

    # Mock trafilatura
    mock_trafilatura.extract.return_value = "Extracted text content"
    mock_metadata = Mock()
    mock_metadata.title = "Test Title"
    mock_metadata.author = "Test Author"
    mock_metadata.date = "2025-01-01"
    mock_metadata.description = "Test Description"
    mock_trafilatura.extract_metadata.return_value = mock_metadata

    result = extract_website_content("https://example.com", cache=temp_cache)

    expect(result["success"] is True, "Successful extraction should flag success")
    expect(result["title"] == "Test Title", "Metadata title should match extractor output")
    expect(
        result["text"] == "Extracted text content",
        "Extracted text should match payload",
    )
    expect(result["url"] == "https://example.com", "Result URL should echo the request URL")


@patch("hotpass.enrichment.TRAFILATURA_AVAILABLE", True)
@patch("hotpass.enrichment.REQUESTS_AVAILABLE", True)
@patch("hotpass.enrichment.requests", create=True)
def test_extract_website_content_error(mock_requests, temp_cache):
    """Test website content extraction with error."""
    mock_requests.get.side_effect = Exception("Connection timeout")

    result = extract_website_content("https://example.com", cache=temp_cache)

    expect(result["success"] is False, "Failure should flag success=False")
    expect("error" in result, "Failure payload should include an error field")
    expect(
        "Connection timeout" in result["error"],
        "Error message should include original exception text",
    )


@patch("hotpass.enrichment.TRAFILATURA_AVAILABLE", False)
def test_extract_website_content_no_trafilatura():
    """Test website extraction when trafilatura is not available."""
    result = extract_website_content("https://example.com")

    expect("error" in result, "Unavailable trafilatura should return error payload")
    expect(
        "Trafilatura not installed" in result["error"],
        "Error should indicate missing trafilatura dependency",
    )


def test_extract_website_content_caching(temp_cache):
    """Test that website content is cached."""
    with (
        patch("hotpass.enrichment.TRAFILATURA_AVAILABLE", True),
        patch("hotpass.enrichment.REQUESTS_AVAILABLE", True),
        patch("hotpass.enrichment.requests", create=True) as mock_requests,
        patch("hotpass.enrichment.trafilatura", create=True) as mock_trafilatura,
    ):
        mock_response = Mock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = Mock()
        mock_requests.get.return_value = mock_response

        mock_trafilatura.extract.return_value = "Test text"
        mock_trafilatura.extract_metadata.return_value = None

        # First call should hit the API
        result1 = extract_website_content("https://example.com", cache=temp_cache)
        expect(
            result1["success"] is True,
            "First extraction should succeed via HTTP request",
        )

        # Second call should use cache
        result2 = extract_website_content("https://example.com", cache=temp_cache)
        expect(
            result2["success"] is True,
            "Second extraction should succeed via cache reuse",
        )

        # Verify only one API call was made
        expect(
            mock_requests.get.call_count == 1,
            "HTTP request should only be executed once when cache is provided",
        )


@patch("hotpass.enrichment.extract_website_content")
def test_enrich_dataframe_with_websites(mock_extract, temp_cache):
    """Test enriching dataframe with website content."""
    # Create test dataframe
    df = pd.DataFrame(
        {
            "organization_name": ["Company A", "Company B"],
            "organization_website": ["https://companya.com", "https://companyb.com"],
        }
    )

    # Mock successful extraction
    mock_extract.side_effect = [
        {
            "success": True,
            "title": "Company A Website",
            "description": "Company A description",
            "text": "Lorem ipsum dolor sit amet",
        },
        {
            "success": True,
            "title": "Company B Website",
            "description": "Company B description",
            "text": "Consectetur adipiscing elit",
        },
    ]

    result_df = enrich_dataframe_with_websites(df, cache=temp_cache)

    expect(
        "website_title" in result_df.columns,
        "Website enrichment should add title column",
    )
    expect(
        "website_description" in result_df.columns,
        "Website enrichment should add description column",
    )
    expect(
        "website_enriched" in result_df.columns,
        "Website enrichment flag column should exist",
    )
    expect(
        result_df["website_enriched"].sum() == 2,
        "Both rows should be marked enriched when extraction succeeds",
    )
    expect(
        result_df.loc[0, "website_title"] == "Company A Website",
        "Enriched title should match mock return value",
    )


@patch("hotpass.enrichment.extract_website_content")
def test_enrich_dataframe_with_websites_missing_column(mock_extract):
    """Test website enrichment with missing column."""
    df = pd.DataFrame(
        {
            "organization_name": ["Company A"],
        }
    )

    result_df = enrich_dataframe_with_websites(df, website_column="nonexistent")

    # Should return original dataframe
    expect(
        "website_title" not in result_df.columns,
        "Missing website column should leave dataframe unchanged",
    )


@patch("hotpass.enrichment.extract_website_content")
def test_enrich_dataframe_with_websites_null_urls(mock_extract, temp_cache):
    """Test website enrichment with null URLs."""
    df = pd.DataFrame(
        {
            "organization_name": ["Company A", "Company B"],
            "organization_website": ["https://companya.com", None],
        }
    )

    mock_extract.return_value = {
        "success": True,
        "title": "Company A Website",
        "description": "Test",
        "text": "Test text",
    }

    result_df = enrich_dataframe_with_websites(df, cache=temp_cache)

    # Only one should be enriched
    expect(
        result_df["website_enriched"].sum() == 1,
        "Only rows with valid URLs should be enriched",
    )
    expect(mock_extract.call_count == 1, "Extractor should run once for non-null URLs")


def test_enrich_dataframe_with_websites_concurrent_runs_tasks_in_parallel(monkeypatch):
    """Ensure the concurrent enrichment path executes website fetches in parallel."""

    df = pd.DataFrame(
        {
            "organization_name": ["A", "B", "C", "D"],
            "website": [
                "https://a.example",
                "https://b.example",
                "https://c.example",
                "https://d.example",
            ],
        }
    )

    active = 0
    peak_active = 0
    lock = threading.Lock()

    def fake_extract(url: str, cache=None):
        nonlocal active, peak_active
        with lock:
            active += 1
            peak_active = max(peak_active, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return {
            "success": True,
            "title": f"Title for {url}",
            "description": "",
            "text": "content",
        }

    monkeypatch.setattr(enrichment, "extract_website_content", fake_extract)

    result = enrich_dataframe_with_websites_concurrent(df, website_column="website", concurrency=4)

    expect(
        peak_active >= 2,
        "Concurrency helper should perform at least two requests in parallel",
    )
    expect(result["website_enriched"].sum() == 4, "All rows should be marked enriched")
    expect(
        (
            result["website_title"]
            == [
                "Title for https://a.example",
                "Title for https://b.example",
                "Title for https://c.example",
                "Title for https://d.example",
            ]
        ).all(),
        "Concurrent enrichment should retain titles from the extractor results",
    )


@patch("hotpass.enrichment.enrich_from_registry")
def test_enrich_dataframe_with_registries(mock_enrich_registry, temp_cache):
    """Test enriching dataframe with registry data."""
    df = pd.DataFrame(
        {
            "organization_name": ["Company A", "Company B"],
            "location": ["City A", "City B"],
        }
    )

    # Mock registry responses
    mock_enrich_registry.side_effect = [
        {
            "success": True,
            "registry": "cipc",
            "payload": {"status": "found", "registration_number": "REG123"},
        },
        {
            "success": False,
            "registry": "cipc",
            "payload": {"status": "not_found", "registration_number": None},
        },
    ]

    result_df = enrich_dataframe_with_registries(df, registry_type="cipc", cache=temp_cache)

    expect(
        "registry_type" in result_df.columns,
        "Registry enrichment should add type column",
    )
    expect(
        "registry_status" in result_df.columns,
        "Registry enrichment should add status column",
    )
    expect(
        "registry_number" in result_df.columns,
        "Registry enrichment should add number column",
    )
    expect(
        result_df.loc[0, "registry_number"] == "REG123",
        "Registry number should reflect successful lookup payload",
    )


@patch("hotpass.enrichment.enrich_from_registry")
def test_enrich_dataframe_with_registries_missing_column(mock_enrich_registry):
    """Test registry enrichment with missing column."""
    df = pd.DataFrame(
        {
            "company": ["Company A"],
        }
    )

    result_df = enrich_dataframe_with_registries(df, org_name_column="nonexistent")

    # Should return original dataframe
    expect(
        "registry_type" not in result_df.columns,
        "Registry enrichment should skip when organization column is missing",
    )


@patch("hotpass.enrichment.enrich_from_registry")
def test_enrich_dataframe_with_registries_null_names(mock_enrich_registry, temp_cache):
    """Test registry enrichment with null organization names."""
    df = pd.DataFrame(
        {
            "organization_name": ["Company A", None, ""],
        }
    )

    mock_enrich_registry.return_value = {
        "success": True,
        "registry": "cipc",
        "payload": {"status": "active", "registration_number": "REG456"},
    }

    result_df = enrich_dataframe_with_registries(df, cache=temp_cache)

    # Only one organisation should result in a lookup
    mock_enrich_registry.assert_called_once_with("Company A", "cipc", cache=temp_cache)
    expect(
        result_df["registry_enriched"].sum() == 1,
        "Only rows with organization names should be flagged enriched",
    )


@parametrize("collector_name", ["news", "hiring", "traffic", "tech-adoption"])
def test_run_intent_plan_registers_collectors(collector_name: str) -> None:
    """Each built-in collector should emit at least one signal."""

    issued = datetime(2025, 10, 27, tzinfo=UTC)
    plan = IntentPlan(
        enabled=True,
        collectors=(
            IntentCollectorDefinition(
                name=collector_name,
                options={
                    "events": {
                        "aero-school": [
                            {
                                "headline": "Aero School expands fleet",
                                "technology": "Prefect Cloud",
                                "magnitude": 2.5,
                                "role": "Automation Lead",
                                "intent": 0.9,
                                "timestamp": (issued - timedelta(days=1)).isoformat(),
                                "url": "https://example.test/aero/expands",
                            }
                        ]
                    }
                },
            ),
        ),
        targets=(IntentTargetDefinition(identifier="Aero School", slug="aero-school"),),
    )

    result = run_intent_plan(
        plan,
        country_code="ZA",
        credentials={},
        issued_at=issued,
    )

    expect(not result.signals.empty, "Intent plan should emit at least one signal")
    summary = result.summary["aero-school"]
    expect(summary.score > 0, "Summary score should be positive when signals exist")
    expect(
        collector_name in summary.signal_types,
        "Summary should record originating collector name",
    )


def test_run_intent_plan_generates_digest() -> None:
    issued = datetime(2025, 10, 27, 12, tzinfo=UTC)
    plan = IntentPlan(
        enabled=True,
        collectors=(
            IntentCollectorDefinition(
                name="news",
                options={
                    "events": {
                        "aero-school": [
                            {
                                "headline": "Aero School wins defence training deal",
                                "intent": 0.9,
                                "timestamp": (issued - timedelta(hours=3)).isoformat(),
                                "url": "https://example.test/aero/deal",
                                "sentiment": 0.8,
                            }
                        ],
                        "heli-ops": [
                            {
                                "headline": "Heli Ops launches medivac division",
                                "intent": 0.7,
                                "timestamp": (issued - timedelta(days=2)).isoformat(),
                                "url": "https://example.test/heli/medivac",
                            }
                        ],
                    }
                },
            ),
            IntentCollectorDefinition(
                name="hiring",
                options={
                    "events": {
                        "aero-school": [
                            {
                                "role": "Chief Flight Instructor",
                                "intent": 0.8,
                                "timestamp": (issued - timedelta(days=1)).isoformat(),
                            }
                        ]
                    }
                },
            ),
        ),
        targets=(
            IntentTargetDefinition(identifier="Aero School", slug="aero-school"),
            IntentTargetDefinition(identifier="Heli Ops", slug="heli-ops"),
        ),
    )

    result = run_intent_plan(
        plan,
        country_code="ZA",
        credentials={"token": "dummy"},
        issued_at=issued,
    )

    expect(
        set(result.signals.columns)
        >= {
            "target_slug",
            "signal_type",
            "score",
            "observed_at",
            "retrieved_at",
            "provenance",
        },
        "Signals dataframe should expose provenance columns",
    )

    summary = result.summary["aero-school"]
    expect(summary.signal_count == 2, "Aero School should emit two signals in summary")
    assert summary.last_observed_at is not None, "Summary should include last observed timestamp"
    expect(
        summary.last_observed_at.date().isoformat() == issued.date().isoformat(),
        "Last observed date should align with issued date for most recent event",
    )
    expect("hiring" in summary.signal_types, "Summary should include hiring signal type")

    digest = result.digest
    expect(isinstance(digest, pd.DataFrame), "Digest should materialise as a DataFrame")
    expect(not digest.empty, "Digest should contain aggregated signal rows")
    expect(
        "intent_signal_score" in digest.columns,
        "Digest should include intent score column",
    )
    aero_score = digest.loc[digest["target_slug"] == "aero-school", "intent_signal_score"].iloc[0]
    heli_score = digest.loc[digest["target_slug"] == "heli-ops", "intent_signal_score"].iloc[0]
    expect(aero_score > heli_score, "Aero School score should exceed Heli Ops score")


def test_intent_plan_persists_signals_and_reuses_cache(tmp_path: Path) -> None:
    issued = datetime(2025, 10, 27, 8, tzinfo=UTC)
    storage_path = tmp_path / "intent-signals.json"

    base_plan = IntentPlan(
        enabled=True,
        storage_path=storage_path,
        collectors=(
            IntentCollectorDefinition(
                name="news",
                options={
                    "cache_ttl_minutes": 180,
                    "events": {
                        "aero-school": [
                            {
                                "headline": "Aero School expands fleet",
                                "intent": 0.85,
                                "timestamp": (issued - timedelta(hours=4)).isoformat(),
                                "url": "https://example.test/aero/expands",
                            }
                        ]
                    },
                },
            ),
        ),
        targets=(IntentTargetDefinition(identifier="Aero School", slug="aero-school"),),
    )

    run_intent_plan(
        base_plan,
        country_code="ZA",
        credentials={},
        issued_at=issued,
    )

    expect(storage_path.exists(), "Intent plan should persist signals to storage path")
    stored_records = json.loads(storage_path.read_text(encoding="utf-8"))
    expect(len(stored_records) == 1, "Initial run should persist a single record")
    record = stored_records[0]
    expect(
        record["target_slug"] == "aero-school",
        "Stored record should target Aero School",
    )
    expect("retrieved_at" in record, "Stored record should include retrieval timestamp")
    expect(
        record["provenance"]["collector"] == "news",
        "Stored record should capture provenance collector name",
    )

    refreshed_plan = IntentPlan(
        enabled=True,
        storage_path=storage_path,
        collectors=(
            IntentCollectorDefinition(
                name="news",
                options={
                    "cache_ttl_minutes": 180,
                    "events": {
                        "aero-school": [
                            {
                                "headline": "Aero School modernises ops",
                                "intent": 0.4,
                                "timestamp": (issued + timedelta(minutes=5)).isoformat(),
                                "url": "https://example.test/aero/modern",
                            }
                        ]
                    },
                },
            ),
        ),
        targets=(IntentTargetDefinition(identifier="Aero School", slug="aero-school"),),
    )

    second_result = run_intent_plan(
        refreshed_plan,
        country_code="ZA",
        credentials={},
        issued_at=issued + timedelta(minutes=10),
    )

    expect(
        second_result.summary["aero-school"].signal_count == 1,
        "Cache should prevent duplicate signal accumulation",
    )
    cached_headline = second_result.signals.iloc[0]["metadata"].get("headline")
    expect(
        cached_headline == "Aero School expands fleet",
        "Cached headline should match original persisted signal",
    )
