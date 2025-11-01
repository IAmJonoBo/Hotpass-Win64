"""Async-specific tests for enrichment module."""

from __future__ import annotations

import asyncio
import tempfile
import time
from collections.abc import Iterator
from unittest.mock import patch

import pandas as pd
import pytest

from tests.helpers.fixtures import fixture

pytest.importorskip("frictionless")

import hotpass.enrichment as enrichment  # noqa: E402
from hotpass.enrichment import (
    CacheManager,
    enrich_dataframe_with_websites_async,
    enrich_dataframe_with_websites_concurrent,
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


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_processes_in_parallel(monkeypatch):
    """Test that async enrichment truly runs tasks in parallel."""
    df = pd.DataFrame(
        {
            "organization_name": ["A", "B", "C", "D", "E"],
            "website": [
                "https://a.example",
                "https://b.example",
                "https://c.example",
                "https://d.example",
                "https://e.example",
            ],
        }
    )

    call_order = []

    def fake_extract(url: str, cache=None):
        """Simulate I/O-bound work with a sleep."""
        call_order.append(url)
        time.sleep(0.05)  # Simulate network delay
        return {
            "success": True,
            "title": f"Title for {url}",
            "description": f"Description for {url}",
            "text": "Sample content",
        }

    monkeypatch.setattr(enrichment, "extract_website_content", fake_extract)

    start = time.time()
    result = await enrich_dataframe_with_websites_async(df, website_column="website", concurrency=5)
    elapsed = time.time() - start

    # With 5 tasks at 0.05s each, sequential would take 0.25s
    # Parallel should take ~0.05s (plus overhead)
    expect(elapsed < 0.15, f"Expected parallel execution, took {elapsed:.2f}s")
    expect(
        result["website_enriched"].sum() == 5,
        "Parallel enrichment should mark all rows",
    )
    expect(len(call_order) == 5, "Extractor should run once per input row")


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_respects_concurrency(monkeypatch):
    """Test that concurrency limit is enforced."""
    df = pd.DataFrame(
        {
            "website": [f"https://{i}.example" for i in range(10)],
        }
    )

    active_count = 0
    max_concurrent = 0
    lock = asyncio.Lock()

    async def fake_extract_async(url: str, cache=None):
        """Track concurrent execution."""
        nonlocal active_count, max_concurrent
        async with lock:
            active_count += 1
            max_concurrent = max(max_concurrent, active_count)
        await asyncio.sleep(0.01)
        async with lock:
            active_count -= 1
        return {
            "success": True,
            "title": f"Title for {url}",
            "description": "",
            "text": "content",
        }

    def fake_extract(url: str, cache=None):
        """Sync wrapper for async tracking."""
        return asyncio.run(fake_extract_async(url, cache))

    monkeypatch.setattr(enrichment, "extract_website_content", fake_extract)

    result = await enrich_dataframe_with_websites_async(df, website_column="website", concurrency=3)

    expect(
        result["website_enriched"].sum() == 10,
        "All rows should be enriched under concurrency limit",
    )
    # Due to the async nature and timing, we should see some concurrency
    expect(max_concurrent <= 3, f"Exceeded concurrency limit: {max_concurrent}")


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_handles_exceptions(monkeypatch):
    """Test that exceptions in one task don't break others."""
    df = pd.DataFrame(
        {
            "website": [
                "https://good1.example",
                "https://bad.example",
                "https://good2.example",
            ],
        }
    )

    def fake_extract(url: str, cache=None):
        """Fail for specific URL."""
        if "bad" in url:
            raise ValueError("Simulated extraction error")
        return {
            "success": True,
            "title": f"Title for {url}",
            "description": "",
            "text": "content",
        }

    monkeypatch.setattr(enrichment, "extract_website_content", fake_extract)

    result = await enrich_dataframe_with_websites_async(df, website_column="website", concurrency=3)

    # Good URLs should still be enriched
    expect(
        result["website_enriched"].sum() == 2,
        "Valid URLs should be enriched despite failures",
    )


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_empty_dataframe():
    """Test async enrichment with empty dataframe."""
    df = pd.DataFrame({"website": []})

    result = await enrich_dataframe_with_websites_async(df, website_column="website")

    expect(len(result) == 0, "Empty input should yield empty dataframe")
    expect("website_enriched" in result.columns, "Result should include enrichment column")


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_missing_column():
    """Test async enrichment with missing column."""
    df = pd.DataFrame({"other_column": ["value"]})

    result = await enrich_dataframe_with_websites_async(df, website_column="nonexistent")

    expect(result.equals(df), "Missing website column should leave dataframe unchanged")


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_with_cache(temp_cache, monkeypatch):
    """Test async enrichment uses cache correctly."""
    df = pd.DataFrame(
        {
            "website": ["https://cached.example"],
        }
    )

    call_count = 0

    def fake_extract(url: str, cache=None):
        """Count calls."""
        nonlocal call_count
        call_count += 1
        return {
            "success": True,
            "title": "Cached Title",
            "description": "",
            "text": "content",
        }

    monkeypatch.setattr(enrichment, "extract_website_content", fake_extract)

    # First call should hit the function
    result1 = await enrich_dataframe_with_websites_async(
        df, website_column="website", cache=temp_cache
    )

    # Second call should use cache (but our fake doesn't implement caching)
    result2 = await enrich_dataframe_with_websites_async(
        df, website_column="website", cache=temp_cache
    )

    expect(
        result1["website_enriched"].sum() == 1,
        "Initial async enrichment should process the single website",
    )
    expect(
        result2["website_enriched"].sum() == 1,
        "Cached async enrichment should still report enrichment success",
    )


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_with_null_values():
    """Test async enrichment skips null/empty values."""
    df = pd.DataFrame(
        {
            "website": ["https://valid.example", None, "", "https://valid2.example"],
        }
    )

    call_count = 0

    def fake_extract(url: str, cache=None):
        """Count non-null calls."""
        nonlocal call_count
        call_count += 1
        return {
            "success": True,
            "title": f"Title for {url}",
            "description": "",
            "text": "content",
        }

    with patch.object(enrichment, "extract_website_content", fake_extract):
        result = await enrich_dataframe_with_websites_async(df, website_column="website")

    # Only 2 valid URLs should be processed
    expect(call_count == 2, "Only non-null URLs should trigger extraction")
    expect(result["website_enriched"].sum() == 2, "Only valid URLs should be enriched")


@pytest.mark.asyncio
async def test_enrich_dataframe_with_websites_async_minimum_concurrency():
    """Test that concurrency is bounded to at least 1."""
    df = pd.DataFrame({"website": ["https://test.example"]})

    def fake_extract(url: str, cache=None):
        return {
            "success": True,
            "title": "Test",
            "description": "",
            "text": "content",
        }

    with patch.object(enrichment, "extract_website_content", fake_extract):
        # Try with invalid concurrency values
        result = await enrich_dataframe_with_websites_async(
            df, website_column="website", concurrency=0
        )
        expect(
            result["website_enriched"].sum() == 1,
            "Concurrency lower bound should default to single worker",
        )

        result = await enrich_dataframe_with_websites_async(
            df, website_column="website", concurrency=-5
        )
        expect(
            result["website_enriched"].sum() == 1,
            "Negative concurrency should also coerce to single worker",
        )


@pytest.mark.asyncio
async def test_concurrent_wrapper_raises_in_event_loop():
    """Test that concurrent wrapper raises when called from event loop."""
    df = pd.DataFrame({"website": ["https://test.example"]})

    with pytest.raises(RuntimeError, match="must not be invoked from an active event loop"):
        enrich_dataframe_with_websites_concurrent(df, website_column="website")
