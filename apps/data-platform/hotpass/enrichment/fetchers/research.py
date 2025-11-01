"""Network-based research enrichment fetchers.

This module provides fetchers that require network access for data enrichment.
All fetchers include guards to respect network permission flags and environment
variables. Network fetchers should only be used when deterministic methods fail.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

import pandas as pd
from hotpass.config import IndustryProfile

from . import FetcherResult

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None  # type: ignore[assignment]

try:
    import trafilatura

    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    trafilatura = None


def requires_network(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to guard network operations.

    This decorator ensures that:
    1. Network access is explicitly allowed via the allow_network parameter
    2. Environment variables permit network research
    3. Required dependencies are available

    Args:
        func: The function to decorate

    Returns:
        Decorated function that checks network permissions
    """

    @wraps(func)
    def wrapper(
        self: Any, row: pd.Series, profile: IndustryProfile, allow_network: bool = False
    ) -> Any:
        # Check if network is allowed by parameter
        if not allow_network:
            logger.debug("Network fetch skipped: allow_network=False")
            return None

        # Check environment variables
        feature_enabled = os.getenv("FEATURE_ENABLE_REMOTE_RESEARCH", "0") == "1"
        if not feature_enabled:
            logger.debug("Network fetch skipped: FEATURE_ENABLE_REMOTE_RESEARCH not enabled")
            return None

        runtime_allowed = os.getenv("ALLOW_NETWORK_RESEARCH", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        if not runtime_allowed:
            logger.debug("Network fetch skipped: ALLOW_NETWORK_RESEARCH not set")
            return None

        # Check if required dependencies are available
        if not REQUESTS_AVAILABLE:
            logger.warning("Network fetch skipped: requests library not available")
            return None

        # All checks passed, proceed with network operation
        return func(self, row, profile, allow_network)

    return wrapper


class WebScrapeFetcher:
    """Fetcher that scrapes data from organization websites."""

    @requires_network
    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment by scraping organization website.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Whether network access is allowed

        Returns:
            FetcherResult if scraping successful, None otherwise
        """
        if not TRAFILATURA_AVAILABLE:
            logger.debug("Web scraping skipped: trafilatura not available")
            return None

        website = row.get("website", "").strip()
        if not website:
            return None

        # Ensure website has protocol
        if not website.startswith(("http://", "https://")):
            website = f"https://{website}"

        try:
            # Fetch and extract content
            response = requests.get(website, timeout=10, allow_redirects=True)
            response.raise_for_status()

            # Extract text content
            text = trafilatura.extract(response.text)
            if not text:
                return None

            # Basic enrichment from scraped content
            enriched_data: dict[str, Any] = {
                "website_accessible": True,
                "website_content_length": len(text),
            }

            # Try to extract contact information from text
            if "@" in text:
                # Very basic email extraction
                words = text.split()
                for word in words:
                    if "@" in word and "." in word:
                        enriched_data["scraped_email"] = word.strip()
                        break

            return FetcherResult(
                data=enriched_data,
                source="web_scrape",
                confidence=0.70,  # Lower confidence for scraped data
                strategy="research",
                network_used=True,
            )

        except Exception as e:
            logger.debug(f"Web scraping failed for {website}: {e}")
            return None


class APILookupFetcher:
    """Fetcher that queries external APIs for enrichment."""

    @requires_network
    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment from external APIs.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Whether network access is allowed

        Returns:
            FetcherResult if API lookup successful, None otherwise
        """
        # This is a placeholder for API integrations
        # In production, would integrate with services like:
        # - Company information APIs
        # - Address validation APIs
        # - Contact verification APIs

        logger.debug("API lookup fetcher: placeholder implementation")
        return None


class HotpassResearchFetcher:
    """Fetcher that uses Hotpass research service for enrichment."""

    def __init__(self, research_base_url: str | None = None):
        """Initialize Hotpass research fetcher.

        Args:
            research_base_url: Base URL for Hotpass research service
        """
        self.base_url = research_base_url or os.getenv(
            "HOTPASS_RESEARCH_BASE_URL", "https://research.hotpass.io"
        )

    @requires_network
    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment from Hotpass research service.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Whether network access is allowed

        Returns:
            FetcherResult if research successful, None otherwise
        """
        org_name = row.get("organization_name", "").strip()
        if not org_name:
            return None

        try:
            # Call Hotpass research service
            response = requests.post(
                f"{self.base_url}/api/v1/search",
                json={
                    "query": org_name,
                    "categories": ["research"],
                    "profile": profile.name,
                    "limit": 5,
                },
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                return None

            # Use first result
            result = results[0]
            enriched_data = {
                "research_source": result.get("source"),
                "research_url": result.get("url"),
                "research_snippet": result.get("snippet"),
            }

            return FetcherResult(
                data=enriched_data,
                source="hotpass_research",
                confidence=result.get("confidence", 0.75),
                strategy="research",
                network_used=True,
            )

        except Exception as e:
            logger.debug(f"Hotpass research failed for {org_name}: {e}")
            return None


class DomainCrawlerFetcher:
    """Fetcher that crawls specific domains for structured data."""

    @requires_network
    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment by crawling relevant domains.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Whether network access is allowed

        Returns:
            FetcherResult if crawling successful, None otherwise
        """
        # This would implement domain-specific crawling strategies
        # For example, for aviation profile:
        # - SACAA website
        # - Flight school directories
        # - Aviation industry portals

        logger.debug("Domain crawler fetcher: placeholder implementation")
        return None


__all__ = [
    "requires_network",
    "WebScrapeFetcher",
    "APILookupFetcher",
    "HotpassResearchFetcher",
    "DomainCrawlerFetcher",
]
