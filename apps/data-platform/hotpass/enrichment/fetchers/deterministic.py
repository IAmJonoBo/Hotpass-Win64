"""Deterministic enrichment fetchers.

This module provides offline/local enrichment fetchers that do not require
network access. These include lookup tables, historical data, derived calculations,
and local registry queries.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from hotpass.config import IndustryProfile

from . import FetcherResult

logger = logging.getLogger(__name__)


class LookupTableFetcher:
    """Fetcher that enriches data from lookup tables."""

    def __init__(self, lookup_dir: Path | None = None):
        """Initialize lookup table fetcher.

        Args:
            lookup_dir: Directory containing lookup tables
        """
        self.lookup_dir = lookup_dir or Path(".hotpass/lookups")
        self._tables: dict[str, pd.DataFrame] = {}

    def _load_table(self, table_name: str) -> pd.DataFrame | None:
        """Load a lookup table.

        Args:
            table_name: Name of the lookup table

        Returns:
            DataFrame if table exists, None otherwise
        """
        if table_name in self._tables:
            return self._tables[table_name]

        table_path = self.lookup_dir / f"{table_name}.parquet"
        if not table_path.exists():
            # Try CSV fallback
            table_path = self.lookup_dir / f"{table_name}.csv"
            if not table_path.exists():
                return None

        try:
            if table_path.suffix == ".parquet":
                df = pd.read_parquet(table_path)
            else:
                df = pd.read_csv(table_path)
            self._tables[table_name] = df
            return df
        except Exception as e:
            logger.warning(f"Failed to load lookup table {table_name}: {e}")
            return None

    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment from lookup tables.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Ignored for deterministic fetcher

        Returns:
            FetcherResult if match found, None otherwise
        """
        # Extract key fields for lookup
        org_name = row.get("organization_name", "").strip()
        if not org_name:
            return None

        # Try to load organization lookup table
        lookup_table = self._load_table("organizations")
        if lookup_table is None:
            return None

        # Search for match
        matches = lookup_table[lookup_table["organization_name"].str.lower() == org_name.lower()]

        if matches.empty:
            return None

        # Use first match
        match = matches.iloc[0]
        enriched_data = match.to_dict()

        return FetcherResult(
            data=enriched_data,
            source="lookup_table",
            confidence=0.95,  # High confidence for exact matches
            strategy="deterministic",
            network_used=False,
        )


class HistoricalDataFetcher:
    """Fetcher that enriches from historical pipeline runs."""

    def __init__(self, history_dir: Path | None = None):
        """Initialize historical data fetcher.

        Args:
            history_dir: Directory containing historical outputs
        """
        self.history_dir = history_dir or Path(".hotpass/history")
        self._history: pd.DataFrame | None = None

    def _load_history(self) -> pd.DataFrame | None:
        """Load historical data.

        Returns:
            DataFrame of historical data if available, None otherwise
        """
        if self._history is not None:
            return self._history

        # Find most recent historical output
        if not self.history_dir.exists():
            return None

        parquet_files = list(self.history_dir.glob("*.parquet"))
        if not parquet_files:
            return None

        # Load most recent
        latest_file = max(parquet_files, key=lambda p: p.stat().st_mtime)
        try:
            self._history = pd.read_parquet(latest_file)
            return self._history
        except Exception as e:
            logger.warning(f"Failed to load historical data: {e}")
            return None

    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment from historical data.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Ignored for deterministic fetcher

        Returns:
            FetcherResult if historical record found, None otherwise
        """
        history = self._load_history()
        if history is None:
            return None

        # Try to match by organization name
        org_name = row.get("organization_name", "").strip()
        if not org_name:
            return None

        matches = history[history["organization_name"].str.lower() == org_name.lower()]

        if matches.empty:
            return None

        # Use most complete record
        match = matches.iloc[0]
        enriched_data = match.to_dict()

        return FetcherResult(
            data=enriched_data,
            source="historical_data",
            confidence=0.85,  # Slightly lower confidence than lookup tables
            strategy="deterministic",
            network_used=False,
        )


class DerivedFieldFetcher:
    """Fetcher that computes derived fields from existing data."""

    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Compute derived fields.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Ignored for deterministic fetcher

        Returns:
            FetcherResult with derived fields
        """
        derived_data: dict[str, Any] = {}

        # Derive domain from email if available
        email = row.get("contact_email", "")
        if email and "@" in email:
            domain = email.split("@")[1].lower()
            derived_data["email_domain"] = domain
            # Infer website if not present
            if not row.get("website"):
                derived_data["website"] = f"https://www.{domain}"

        # Derive province from address if available
        address = row.get("address", "")
        if address:
            # Simple province extraction (can be enhanced)
            provinces = [
                "gauteng",
                "western cape",
                "eastern cape",
                "kwazulu-natal",
                "free state",
                "limpopo",
                "mpumalanga",
                "north west",
                "northern cape",
            ]
            address_lower = address.lower()
            for province in provinces:
                if province in address_lower:
                    derived_data["province"] = province.title()
                    break

        if not derived_data:
            return None

        return FetcherResult(
            data=derived_data,
            source="derived_computation",
            confidence=0.90,
            strategy="deterministic",
            network_used=False,
        )


class LocalRegistryFetcher:
    """Fetcher that queries local copies of registry data."""

    def __init__(self, registry_dir: Path | None = None):
        """Initialize local registry fetcher.

        Args:
            registry_dir: Directory containing local registry snapshots
        """
        self.registry_dir = registry_dir or Path(".hotpass/registries")
        self._registries: dict[str, pd.DataFrame] = {}

    def _load_registry(self, registry_name: str) -> pd.DataFrame | None:
        """Load a local registry.

        Args:
            registry_name: Name of the registry

        Returns:
            DataFrame if registry exists, None otherwise
        """
        if registry_name in self._registries:
            return self._registries[registry_name]

        registry_path = self.registry_dir / f"{registry_name}.parquet"
        if not registry_path.exists():
            return None

        try:
            df = pd.read_parquet(registry_path)
            self._registries[registry_name] = df
            return df
        except Exception as e:
            logger.warning(f"Failed to load registry {registry_name}: {e}")
            return None

    def fetch(
        self,
        row: pd.Series,
        profile: IndustryProfile,
        allow_network: bool = False,
    ) -> FetcherResult | None:
        """Fetch enrichment from local registries.

        Args:
            row: The data row to enrich
            profile: Industry profile configuration
            allow_network: Ignored for deterministic fetcher

        Returns:
            FetcherResult if registry match found, None otherwise
        """
        # Try SACAA registry for aviation profile
        if profile.name == "aviation":
            registry = self._load_registry("sacaa")
            if registry is not None:
                org_name = row.get("organization_name", "").strip()
                if org_name:
                    matches = registry[
                        registry["organization_name"].str.lower() == org_name.lower()
                    ]
                    if not matches.empty:
                        match = matches.iloc[0]
                        return FetcherResult(
                            data=match.to_dict(),
                            source="sacaa_registry",
                            confidence=0.98,  # High confidence for official registry
                            strategy="deterministic",
                            network_used=False,
                        )

        return None


__all__ = [
    "LookupTableFetcher",
    "HistoricalDataFetcher",
    "DerivedFieldFetcher",
    "LocalRegistryFetcher",
]
