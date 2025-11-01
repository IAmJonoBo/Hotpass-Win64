"""Enrichment pipeline orchestration.

This module orchestrates the enrichment process, coordinating deterministic
and network-based fetchers with provenance tracking.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from hotpass.config import IndustryProfile

from .fetchers import FetcherResult, get_fetcher_registry
from .fetchers.deterministic import (
    DerivedFieldFetcher,
    HistoricalDataFetcher,
    LocalRegistryFetcher,
    LookupTableFetcher,
)
from .fetchers.research import (
    APILookupFetcher,
    DomainCrawlerFetcher,
    HotpassResearchFetcher,
    WebScrapeFetcher,
)
from .provenance import ProvenanceTracker

logger = logging.getLogger(__name__)


def _initialize_fetchers() -> None:
    """Initialize and register all available fetchers."""
    registry = get_fetcher_registry()

    # Register deterministic fetchers
    registry.register_deterministic(LookupTableFetcher())
    registry.register_deterministic(HistoricalDataFetcher())
    registry.register_deterministic(DerivedFieldFetcher())
    registry.register_deterministic(LocalRegistryFetcher())

    # Register research fetchers
    registry.register_research(WebScrapeFetcher())
    registry.register_research(APILookupFetcher())
    registry.register_research(HotpassResearchFetcher())
    registry.register_research(DomainCrawlerFetcher())

    logger.info(
        f"Initialized {len(registry.get_deterministic_fetchers())} deterministic "
        f"and {len(registry.get_research_fetchers())} research fetchers"
    )


# Initialize fetchers on module import
_initialize_fetchers()


def enrich_data(
    input_path: Path,
    profile: IndustryProfile,
    allow_network: bool = False,
    confidence_threshold: float = 0.7,
    provenance_tracker: ProvenanceTracker | None = None,
) -> pd.DataFrame:
    """Enrich data from an input file.

    This function follows a deterministic-first approach:
    1. Try all deterministic fetchers
    2. If network allowed and no high-confidence result, try network fetchers
    3. Track provenance for all enrichments

    Args:
        input_path: Path to the input file (XLSX)
        profile: Industry profile configuration
        allow_network: Whether to allow network-based enrichment
        confidence_threshold: Minimum confidence for accepting enrichment
        provenance_tracker: Optional provenance tracker (created if not provided)

    Returns:
        Enriched DataFrame
    """
    # Load input data
    logger.info(f"Loading input data from {input_path}")
    df = pd.read_excel(input_path)
    logger.info(f"Loaded {len(df)} rows")

    # Initialize provenance tracker
    if provenance_tracker is None:
        provenance_tracker = ProvenanceTracker()

    # Get available fetchers
    registry = get_fetcher_registry()
    fetchers = registry.get_all_fetchers(allow_network=allow_network)
    logger.info(f"Using {len(fetchers)} fetchers (network={allow_network})")

    # Enrich each row
    enriched_rows = []
    for idx, row in df.iterrows():
        enriched_row = row.copy()
        best_result: FetcherResult | None = None

        # Try fetchers in order until we get a high-confidence result
        for fetcher in fetchers:
            try:
                result = fetcher.fetch(row, profile, allow_network)

                if result is None:
                    continue

                # Track provenance
                provenance_tracker.add_entry(
                    row_index=idx,
                    source=result.source,
                    confidence=result.confidence,
                    strategy=result.strategy,
                    network_used=result.network_used,
                )

                # Keep track of best result
                if best_result is None or result.confidence > best_result.confidence:
                    best_result = result

                # If we have a high-confidence result, stop trying fetchers
                if result.confidence >= confidence_threshold:
                    logger.debug(
                        f"Row {idx}: High-confidence enrichment from {result.source} "
                        f"(confidence={result.confidence})"
                    )
                    break

            except Exception as e:
                logger.warning(f"Fetcher {fetcher.__class__.__name__} failed for row {idx}: {e}")

        # Apply best enrichment if found
        if best_result is not None:
            for key, value in best_result.data.items():
                # Only update if field is empty or null
                if pd.isna(enriched_row.get(key)) or not enriched_row.get(key):
                    enriched_row[key] = value

        # Track if network was disabled
        if not allow_network:
            provenance_tracker.add_network_disabled_entry(row_index=idx)

        enriched_rows.append(enriched_row)

    # Create enriched DataFrame
    enriched_df = pd.DataFrame(enriched_rows)

    # Log summary
    summary = provenance_tracker.get_summary()
    logger.info(f"Enrichment complete: {summary}")

    return enriched_df


def enrich_row(
    row: pd.Series,
    profile: IndustryProfile,
    allow_network: bool = False,
    confidence_threshold: float = 0.7,
) -> tuple[pd.Series, dict[str, Any]]:
    """Enrich a single row.

    Args:
        row: The data row to enrich
        profile: Industry profile configuration
        allow_network: Whether to allow network-based enrichment
        confidence_threshold: Minimum confidence for accepting enrichment

    Returns:
        Tuple of (enriched row, provenance information)
    """
    registry = get_fetcher_registry()
    fetchers = registry.get_all_fetchers(allow_network=allow_network)

    enriched_row = row.copy()
    best_result: FetcherResult | None = None
    provenance: dict[str, Any] = {
        "sources_tried": [],
        "network_allowed": allow_network,
    }

    for fetcher in fetchers:
        try:
            result = fetcher.fetch(row, profile, allow_network)

            if result is None:
                continue

            provenance["sources_tried"].append(
                {
                    "source": result.source,
                    "confidence": result.confidence,
                    "strategy": result.strategy,
                    "network_used": result.network_used,
                }
            )

            if best_result is None or result.confidence > best_result.confidence:
                best_result = result

            if result.confidence >= confidence_threshold:
                break

        except Exception as e:
            logger.warning(f"Fetcher {fetcher.__class__.__name__} failed: {e}")

    # Apply best enrichment
    if best_result is not None:
        for key, value in best_result.data.items():
            if pd.isna(enriched_row.get(key)) or not enriched_row.get(key):
                enriched_row[key] = value

        provenance["applied_source"] = best_result.source
        provenance["applied_confidence"] = best_result.confidence
        provenance["applied_strategy"] = best_result.strategy
    else:
        provenance["applied_source"] = None

    return enriched_row, provenance


__all__ = [
    "enrich_data",
    "enrich_row",
]
