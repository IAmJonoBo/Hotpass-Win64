"""Provenance tracking for enriched data.

This module tracks the source, timestamp, confidence, and strategy for all
enriched data to enable compliance audits and data lineage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ProvenanceEntry:
    """A single provenance entry for a data point."""

    source: str
    """Name of the data source (e.g., 'lookup_table', 'web_scrape')"""

    timestamp: datetime
    """When the data was obtained"""

    confidence: float
    """Confidence score (0.0 to 1.0)"""

    strategy: str
    """Enrichment strategy used (deterministic, research, backfill)"""

    network_status: str = "not_used"
    """Network access status (not_used, used, skipped: network disabled)"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the enrichment"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with provenance information
        """
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "strategy": self.strategy,
            "network_status": self.network_status,
            "metadata": self.metadata,
        }


class ProvenanceTracker:
    """Tracks provenance for enriched data rows."""

    def __init__(self) -> None:
        """Initialize provenance tracker."""
        self._entries: dict[int, list[ProvenanceEntry]] = {}

    def add_entry(
        self,
        row_index: int,
        source: str,
        confidence: float,
        strategy: str,
        network_used: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a provenance entry for a row.

        Args:
            row_index: Index of the row being enriched
            source: Name of the data source
            confidence: Confidence score (0.0 to 1.0)
            strategy: Enrichment strategy (deterministic, research, backfill)
            network_used: Whether network was accessed
            metadata: Additional metadata
        """
        if row_index not in self._entries:
            self._entries[row_index] = []

        network_status = "used" if network_used else "not_used"

        entry = ProvenanceEntry(
            source=source,
            timestamp=datetime.now(UTC),
            confidence=confidence,
            strategy=strategy,
            network_status=network_status,
            metadata=metadata or {},
        )

        self._entries[row_index].append(entry)
        logger.debug(f"Added provenance entry for row {row_index}: {source}")

    def add_network_disabled_entry(
        self,
        row_index: int,
        source: str = "network_enrichment",
    ) -> None:
        """Add an entry indicating network enrichment was skipped.

        Args:
            row_index: Index of the row
            source: Name of the skipped source
        """
        if row_index not in self._entries:
            self._entries[row_index] = []

        entry = ProvenanceEntry(
            source=source,
            timestamp=datetime.now(UTC),
            confidence=0.0,
            strategy="research",
            network_status="skipped: network disabled",
            metadata={},
        )

        self._entries[row_index].append(entry)

    def get_entries(self, row_index: int) -> list[ProvenanceEntry]:
        """Get all provenance entries for a row.

        Args:
            row_index: Index of the row

        Returns:
            List of provenance entries
        """
        return self._entries.get(row_index, [])

    def add_provenance_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add provenance columns to a DataFrame.

        Args:
            df: The DataFrame to add provenance to

        Returns:
            DataFrame with provenance columns added
        """
        # Initialize provenance columns
        provenance_data: dict[str, list[Any]] = {
            "provenance_source": [],
            "provenance_timestamp": [],
            "provenance_confidence": [],
            "provenance_strategy": [],
            "provenance_network_status": [],
        }

        # For each row, use the highest confidence entry
        for idx in range(len(df)):
            entries = self.get_entries(idx)

            if entries:
                # Sort by confidence and use the best entry
                best_entry = max(entries, key=lambda e: e.confidence)
                provenance_data["provenance_source"].append(best_entry.source)
                provenance_data["provenance_timestamp"].append(best_entry.timestamp.isoformat())
                provenance_data["provenance_confidence"].append(best_entry.confidence)
                provenance_data["provenance_strategy"].append(best_entry.strategy)
                provenance_data["provenance_network_status"].append(best_entry.network_status)
            else:
                # No enrichment for this row
                provenance_data["provenance_source"].append("original")
                provenance_data["provenance_timestamp"].append(datetime.now(UTC).isoformat())
                provenance_data["provenance_confidence"].append(1.0)
                provenance_data["provenance_strategy"].append("none")
                provenance_data["provenance_network_status"].append("not_used")

        # Add columns to DataFrame
        for col, values in provenance_data.items():
            df[col] = values

        return df

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of provenance tracking.

        Returns:
            Dictionary with summary statistics
        """
        total_rows = len(self._entries)
        total_entries = sum(len(entries) for entries in self._entries.values())

        sources: dict[str, int] = {}
        strategies: dict[str, int] = {}
        network_statuses: dict[str, int] = {}

        for entries in self._entries.values():
            for entry in entries:
                sources[entry.source] = sources.get(entry.source, 0) + 1
                strategies[entry.strategy] = strategies.get(entry.strategy, 0) + 1
                network_statuses[entry.network_status] = (
                    network_statuses.get(entry.network_status, 0) + 1
                )

        return {
            "total_rows_enriched": total_rows,
            "total_provenance_entries": total_entries,
            "sources": sources,
            "strategies": strategies,
            "network_statuses": network_statuses,
        }

    def explain_row(self, row_index: int) -> dict[str, Any]:
        """Explain the provenance for a specific row.

        Args:
            row_index: Index of the row to explain

        Returns:
            Dictionary with detailed provenance information
        """
        entries = self.get_entries(row_index)

        if not entries:
            return {
                "row_index": row_index,
                "enriched": False,
                "message": "No enrichment applied to this row",
            }

        return {
            "row_index": row_index,
            "enriched": True,
            "entries": [entry.to_dict() for entry in entries],
            "primary_source": max(entries, key=lambda e: e.confidence).source,
            "confidence_range": [
                min(e.confidence for e in entries),
                max(e.confidence for e in entries),
            ],
        }


__all__ = [
    "ProvenanceEntry",
    "ProvenanceTracker",
]
