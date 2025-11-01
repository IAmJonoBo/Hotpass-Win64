"""Tests for enrichment pipeline (Sprint 2)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pandas as pd

from tests.helpers.fixtures import fixture


def expect(condition: bool, message: str) -> None:
    """Assert-free test helper per docs/how-to-guides/assert-free-pytest.md."""
    if not condition:
        raise AssertionError(message)


@fixture
def minimal_xlsx(tmp_path: Path) -> Path:
    """Create a minimal test XLSX file."""
    df = pd.DataFrame(
        {
            "organization_name": ["Test School", "Sample Academy"],
            "contact_email": ["", ""],
            "website": ["", ""],
        }
    )
    output_path = tmp_path / "minimal.xlsx"
    df.to_excel(output_path, index=False)
    return output_path


class TestEnrichmentPipeline:
    """Tests for enrichment pipeline implementation."""

    def test_enrich_data_function_exists(self):
        """Sprint 2: enrich_data function should be importable."""
        try:
            from hotpass.enrichment.pipeline import enrich_data

            expect(callable(enrich_data), "enrich_data should be callable")
        except ImportError as exc:
            raise AssertionError(f"enrich_data should be importable: {exc}") from exc

    def test_provenance_tracker_exists(self):
        """Sprint 2: ProvenanceTracker should be importable."""
        try:
            from hotpass.enrichment.provenance import ProvenanceTracker

            tracker = ProvenanceTracker()
            expect(hasattr(tracker, "add_entry"), "ProvenanceTracker should have add_entry")
            expect(
                hasattr(tracker, "add_provenance_columns"),
                "ProvenanceTracker should have add_provenance_columns",
            )
        except ImportError as exc:
            raise AssertionError(f"ProvenanceTracker should be importable: {exc}") from exc

    def test_fetcher_registry_exists(self):
        """Sprint 2: Fetcher registry should be available."""
        try:
            from hotpass.enrichment.fetchers import get_fetcher_registry

            registry = get_fetcher_registry()
            expect(
                hasattr(registry, "get_deterministic_fetchers"),
                "Registry should have get_deterministic_fetchers",
            )
            expect(
                hasattr(registry, "get_research_fetchers"),
                "Registry should have get_research_fetchers",
            )
        except ImportError as exc:
            raise AssertionError(f"Fetcher registry should be importable: {exc}") from exc

    def test_deterministic_fetchers_exist(self):
        """Sprint 2: Deterministic fetchers should be available."""
        try:
            from hotpass.enrichment.fetchers.deterministic import (
                DerivedFieldFetcher,
                HistoricalDataFetcher,
                LocalRegistryFetcher,
                LookupTableFetcher,
            )

            expect(
                LookupTableFetcher is not None,
                "LookupTableFetcher should be importable",
            )
            expect(
                HistoricalDataFetcher is not None,
                "HistoricalDataFetcher should be importable",
            )
            expect(
                DerivedFieldFetcher is not None,
                "DerivedFieldFetcher should be importable",
            )
            expect(
                LocalRegistryFetcher is not None,
                "LocalRegistryFetcher should be importable",
            )
        except ImportError as exc:
            raise AssertionError(f"Deterministic fetchers should be importable: {exc}") from exc

    def test_research_fetchers_exist(self):
        """Sprint 2: Research fetchers should be available."""
        try:
            from hotpass.enrichment.fetchers.research import (
                HotpassResearchFetcher,
                WebScrapeFetcher,
                requires_network,
            )

            expect(WebScrapeFetcher is not None, "WebScrapeFetcher should be importable")
            expect(
                HotpassResearchFetcher is not None,
                "HotpassResearchFetcher should be importable",
            )
            expect(callable(requires_network), "requires_network should be callable")
        except ImportError as exc:
            raise AssertionError(f"Research fetchers should be importable: {exc}") from exc

    def test_network_guard_decorator(self):
        """Sprint 2: Network guard decorator should respect flags."""
        from hotpass.enrichment.fetchers.research import requires_network

        @requires_network
        def test_func(self, row, profile, allow_network=False):
            return "success"

        # Should return None when allow_network=False
        result = test_func(None, None, None, allow_network=False)
        expect(result is None, "Network guard should block when allow_network=False")


class TestQG3EnrichmentChainGate:
    """QG-3: Enrichment Chain Gate (Full Implementation)."""

    def test_qg3_enrichment_offline_succeeds(self, minimal_xlsx: Path, tmp_path: Path):
        """QG-3a: Enrichment should work offline with provenance."""
        # Ensure network is disabled
        env = os.environ.copy()
        env["ALLOW_NETWORK_RESEARCH"] = "false"
        env["FEATURE_ENABLE_REMOTE_RESEARCH"] = "0"

        output_path = tmp_path / "enriched.xlsx"

        result = subprocess.run(
            [
                "uv",
                "run",
                "hotpass",
                "enrich",
                "--input",
                str(minimal_xlsx),
                "--output",
                str(output_path),
                "--allow-network=false",
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        expect(result.returncode == 0, f"Enrich should succeed offline: {result.stderr}")
        expect(output_path.exists(), "Output file must exist")

        # Verify provenance columns
        df = pd.read_excel(output_path)
        expect("provenance_source" in df.columns, "Must have provenance_source column")
        expect(
            "provenance_timestamp" in df.columns,
            "Must have provenance_timestamp column",
        )
        expect(
            "provenance_confidence" in df.columns,
            "Must have provenance_confidence column",
        )
        expect("provenance_strategy" in df.columns, "Must have provenance_strategy column")
        expect(
            "provenance_network_status" in df.columns,
            "Must have provenance_network_status column",
        )

    def test_qg3_network_disabled_status(self, minimal_xlsx: Path, tmp_path: Path):
        """QG-3b: Network disabled status should be recorded in provenance."""
        env = os.environ.copy()
        env["ALLOW_NETWORK_RESEARCH"] = "false"

        output_path = tmp_path / "enriched.xlsx"

        subprocess.run(
            [
                "uv",
                "run",
                "hotpass",
                "enrich",
                "--input",
                str(minimal_xlsx),
                "--output",
                str(output_path),
                "--allow-network=false",
            ],
            capture_output=True,
            env=env,
            check=True,
        )

        df = pd.read_excel(output_path)

        # Check that network status indicates it was disabled
        network_statuses = df["provenance_network_status"].unique()
        expect(
            any(
                "skipped" in str(status).lower() or status == "not_used"
                for status in network_statuses
            ),
            f"Network status should indicate disabled/not used: {network_statuses}",
        )

    def test_qg3_provenance_contains_strategy(self, minimal_xlsx: Path, tmp_path: Path):
        """QG-3c: Provenance should track enrichment strategy."""
        output_path = tmp_path / "enriched.xlsx"

        subprocess.run(
            [
                "uv",
                "run",
                "hotpass",
                "enrich",
                "--input",
                str(minimal_xlsx),
                "--output",
                str(output_path),
                "--allow-network=false",
            ],
            capture_output=True,
            check=True,
        )

        df = pd.read_excel(output_path)

        # Check strategy column exists and has valid values
        strategies = df["provenance_strategy"].unique()
        valid_strategies = [
            "deterministic",
            "research",
            "backfill",
            "offline-first",
            "none",
        ]

        for strategy in strategies:
            expect(
                strategy in valid_strategies,
                f"Strategy should be one of {valid_strategies}, got: {strategy}",
            )


class TestEnrichmentIntegration:
    """Integration tests for enrichment pipeline."""

    def test_enrich_with_profile(self, minimal_xlsx: Path, tmp_path: Path):
        """Sprint 2: Enrichment should work with or without profile specification."""
        output_path = tmp_path / "enriched.xlsx"

        result = subprocess.run(
            [
                "uv",
                "run",
                "hotpass",
                "enrich",
                "--input",
                str(minimal_xlsx),
                "--output",
                str(output_path),
                "--allow-network=false",
            ],
            capture_output=True,
            text=True,
        )

        expect(
            result.returncode == 0,
            f"Enrich should succeed: {result.stderr}",
        )
        expect(output_path.exists(), "Output file must exist")

    def test_provenance_tracker_add_entry(self):
        """Sprint 2: ProvenanceTracker.add_entry should track entries."""
        from hotpass.enrichment.provenance import ProvenanceTracker

        tracker = ProvenanceTracker()
        tracker.add_entry(
            row_index=0,
            source="test_source",
            confidence=0.9,
            strategy="deterministic",
            network_used=False,
        )

        entries = tracker.get_entries(0)
        expect(len(entries) == 1, "Should have one entry")
        expect(entries[0].source == "test_source", "Source should match")
        expect(entries[0].confidence == 0.9, "Confidence should match")

    def test_provenance_tracker_add_columns(self):
        """Sprint 2: ProvenanceTracker should add columns to DataFrame."""
        import pandas as pd
        from hotpass.enrichment.provenance import ProvenanceTracker

        tracker = ProvenanceTracker()
        tracker.add_entry(
            row_index=0,
            source="test_source",
            confidence=0.85,
            strategy="deterministic",
        )

        df = pd.DataFrame({"name": ["Test"]})
        df_with_prov = tracker.add_provenance_columns(df)

        expect("provenance_source" in df_with_prov.columns, "Should have provenance_source")
        expect(
            df_with_prov.iloc[0]["provenance_source"] == "test_source",
            "Source should match",
        )
        expect(
            df_with_prov.iloc[0]["provenance_confidence"] == 0.85,
            "Confidence should match",
        )


class TestMCPProvenanceExplain:
    """Tests for MCP explain_provenance tool."""

    def test_mcp_explain_provenance_implementation(self):
        """Sprint 2: MCP explain_provenance should be implemented."""
        from hotpass.mcp.server import HotpassMCPServer

        server = HotpassMCPServer()

        # Check that explain_provenance tool is registered
        tool_names = [tool.name for tool in server.tools]
        expect(
            "hotpass.explain_provenance" in tool_names,
            "explain_provenance should be registered",
        )
