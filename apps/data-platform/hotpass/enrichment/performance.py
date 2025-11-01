"""Performance optimizations for enrichment pipeline.

This module provides:
- Fetcher result caching with configurable TTL
- Parallel enrichment with thread/process pools
- Performance monitoring and benchmarks
"""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
from hotpass.enrichment import CacheManager
from hotpass.enrichment.fetchers import Fetcher

logger = logging.getLogger(__name__)


class FetcherCache:
    """Cache layer for fetcher results with automatic expiration."""

    def __init__(
        self,
        cache_manager: CacheManager | None = None,
        ttl_hours: int = 24,
        enabled: bool = True,
    ):
        """
        Initialize fetcher cache.

        Args:
            cache_manager: Optional existing cache manager (creates new if None)
            ttl_hours: Time-to-live for cache entries in hours
            enabled: Whether caching is enabled
        """
        self.enabled = enabled
        self.ttl_hours = ttl_hours
        self.cache: CacheManager | None

        if enabled:
            self.cache = cache_manager or CacheManager(
                db_path="data/.cache/fetcher_cache.db", ttl_hours=ttl_hours
            )
        else:
            self.cache = None

    def _make_cache_key(self, fetcher_name: str, row_data: dict[str, Any]) -> str:
        """
        Generate a cache key for fetcher + row combination.

        Args:
            fetcher_name: Name of the fetcher
            row_data: Row data dictionary

        Returns:
            Cache key string
        """
        # Create a deterministic hash of row data
        row_str = "|".join(f"{k}:{v}" for k, v in sorted(row_data.items()) if v is not None)
        row_hash = hashlib.sha256(row_str.encode()).hexdigest()[:16]
        return f"fetcher:{fetcher_name}:{row_hash}"

    def get(self, fetcher_name: str, row_data: dict[str, Any]) -> Any | None:
        """
        Retrieve cached fetcher result.

        Args:
            fetcher_name: Name of the fetcher
            row_data: Row data dictionary

        Returns:
            Cached result or None if not found/expired
        """
        if not self.enabled or self.cache is None:
            return None

        key = self._make_cache_key(fetcher_name, row_data)
        cached_value = self.cache.get(key)

        if cached_value is not None:
            logger.debug(f"Cache hit for {fetcher_name}")

        return cached_value

    def set(self, fetcher_name: str, row_data: dict[str, Any], result: Any) -> None:
        """
        Store fetcher result in cache.

        Args:
            fetcher_name: Name of the fetcher
            row_data: Row data dictionary
            result: Result to cache
        """
        if not self.enabled or self.cache is None:
            return

        key = self._make_cache_key(fetcher_name, row_data)
        self.cache.set(key, result)
        logger.debug(f"Cached result for {fetcher_name}")

    def clear_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        if not self.enabled or self.cache is None:
            return 0

        return self.cache.clear_expired()

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self.enabled or self.cache is None:
            return {"enabled": False}

        stats = self.cache.stats()
        stats["enabled"] = True
        return stats


def enrich_parallel(
    df: pd.DataFrame,
    fetchers: list[Fetcher],
    max_workers: int = 4,
    cache: FetcherCache | None = None,
    progress_callback: Any = None,
) -> pd.DataFrame:
    """
    Enrich DataFrame using parallel fetcher execution.

    Args:
        df: Input DataFrame to enrich
        fetchers: List of fetcher instances to run
        max_workers: Maximum number of parallel workers
        cache: Optional fetcher cache for result caching
        progress_callback: Optional callback function for progress updates

    Returns:
        Enriched DataFrame
    """
    if df.empty:
        return df

    enriched = df.copy()

    # Create cache if not provided
    if cache is None:
        cache = FetcherCache(enabled=True)

    def process_row_fetcher(row_idx: int, fetcher: Fetcher, row: pd.Series) -> tuple[int, str, Any]:
        """Process a single row with a single fetcher."""
        fetcher_name = fetcher.__class__.__name__

        # Convert row to dict for caching
        row_data = row.to_dict()

        # Check cache first
        cached_result = cache.get(fetcher_name, row_data)
        if cached_result is not None:
            return row_idx, fetcher_name, cached_result

        # Fetch result
        try:
            result = fetcher.fetch(row, profile=None, allow_network=False)  # type: ignore[arg-type]

            # Cache result
            cache.set(fetcher_name, row_data, result)

            return row_idx, fetcher_name, result
        except Exception as e:
            logger.warning(f"Fetcher {fetcher_name} failed for row {row_idx}: {e}")
            return row_idx, fetcher_name, None

    # Create work items: (row_idx, fetcher, row)
    work_items = []
    for idx, row in df.iterrows():
        for fetcher in fetchers:
            work_items.append((idx, fetcher, row))

    # Process in parallel
    results: dict[int, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_row_fetcher, row_idx, fetcher, row): (
                row_idx,
                fetcher,
            )
            for row_idx, fetcher, row in work_items
        }

        completed = 0
        total = len(work_items)

        for future in as_completed(futures):
            row_idx, fetcher_name, result = future.result()

            if row_idx not in results:
                results[row_idx] = {}

            results[row_idx][fetcher_name] = result

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    # Apply results to DataFrame
    for row_idx, fetcher_results in results.items():
        for result in fetcher_results.values():
            if result is not None:
                # Apply result to row (implementation depends on result structure)
                # This is a simplified version - actual implementation would depend
                # on fetcher-specific result handling
                for key, value in result.items() if isinstance(result, dict) else []:
                    if key in enriched.columns:
                        enriched.at[row_idx, key] = value

    return enriched


def benchmark_enrichment(
    df: pd.DataFrame,
    fetchers: list[Fetcher],
    parallel: bool = True,
    max_workers: int = 4,
) -> dict[str, Any]:
    """
    Benchmark enrichment performance with and without parallel execution.

    Args:
        df: Sample DataFrame to enrich
        fetchers: List of fetchers to benchmark
        parallel: Whether to test parallel execution
        max_workers: Number of parallel workers for testing

    Returns:
        Benchmark results dictionary
    """
    import time

    results: dict[str, Any] = {
        "rows": len(df),
        "fetchers": len(fetchers),
        "max_workers": max_workers,
    }

    # Benchmark sequential execution
    start = time.time()
    for _, row in df.iterrows():
        for fetcher in fetchers:
            try:
                fetcher.fetch(row, profile=None, allow_network=False)  # type: ignore[arg-type]
            except Exception:
                pass
    sequential_time = time.time() - start
    results["sequential_time"] = sequential_time

    # Benchmark parallel execution
    if parallel:
        start = time.time()
        enrich_parallel(df, fetchers, max_workers=max_workers)
        parallel_time = time.time() - start
        results["parallel_time"] = parallel_time
        results["speedup"] = sequential_time / parallel_time if parallel_time > 0 else 0.0

    return results
