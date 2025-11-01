"""Enrichment fetchers module.

This module provides deterministic and network-based data enrichment fetchers.
Fetchers follow a deterministic-first pattern, only using network sources when
explicitly enabled.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import pandas as pd

from hotpass.config import IndustryProfile

logger = logging.getLogger(__name__)


class FetcherResult:
    """Result from a fetcher operation."""

    def __init__(
        self,
        data: dict[str, Any],
        source: str,
        confidence: float,
        strategy: str,
        network_used: bool = False,
    ):
        """Initialize a fetcher result.

        Args:
            data: The enriched data
            source: Name of the data source
            confidence: Confidence score (0.0 to 1.0)
            strategy: Enrichment strategy used (deterministic, research, backfill)
            network_used: Whether network was accessed
        """
        self.data = data
        self.source = source
        self.confidence = confidence
        self.strategy = strategy
        self.network_used = network_used


class Fetcher(Protocol):
    """Protocol for enrichment fetchers."""

    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment data for a row.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Whether network access is allowed

        Returns:
            FetcherResult if enrichment found, None otherwise
        """
        ...


class FetcherRegistry:
    """Registry of available fetchers."""

    def __init__(self) -> None:
        """Initialize the fetcher registry."""
        self._deterministic_fetchers: list[Fetcher] = []
        self._research_fetchers: list[Fetcher] = []

    def register_deterministic(self, fetcher: Fetcher) -> None:
        """Register a deterministic fetcher.

        Args:
            fetcher: The fetcher to register
        """
        self._deterministic_fetchers.append(fetcher)

    def register_research(self, fetcher: Fetcher) -> None:
        """Register a research (network) fetcher.

        Args:
            fetcher: The fetcher to register
        """
        self._research_fetchers.append(fetcher)

    def get_deterministic_fetchers(self) -> list[Fetcher]:
        """Get all deterministic fetchers.

        Returns:
            List of deterministic fetchers
        """
        return self._deterministic_fetchers.copy()

    def get_research_fetchers(self) -> list[Fetcher]:
        """Get all research fetchers.

        Returns:
            List of research fetchers
        """
        return self._research_fetchers.copy()

    def get_all_fetchers(self, allow_network: bool = False) -> list[Fetcher]:
        """Get all available fetchers based on network permission.

        Args:
            allow_network: Whether to include network fetchers

        Returns:
            List of available fetchers
        """
        fetchers = self._deterministic_fetchers.copy()
        if allow_network:
            fetchers.extend(self._research_fetchers)
        return fetchers


# Global registry instance
_registry = FetcherRegistry()


def get_fetcher_registry() -> FetcherRegistry:
    """Get the global fetcher registry.

    Returns:
        The global FetcherRegistry instance
    """
    return _registry


__all__ = [
    "FetcherResult",
    "Fetcher",
    "FetcherRegistry",
    "get_fetcher_registry",
]
