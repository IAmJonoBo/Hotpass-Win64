"""Tests for Sprint 3 - Profiles & Compliance."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


def expect(condition: bool, message: str) -> None:
    """Assert-free test helper per docs/how-to-guides/assert-free-pytest.md."""
    if not condition:
        raise AssertionError(message)


class TestProfileSchema:
    """Tests for complete profile schema (4 blocks)."""

    def test_aviation_profile_has_all_blocks(self):
        """Sprint 3: Aviation profile should have all 4 blocks."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        expect(profile_path.exists(), "Aviation profile should exist")

        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        required_blocks = ["ingest", "refine", "enrich", "compliance"]
        for block in required_blocks:
            expect(block in profile, f"Aviation profile must have {block} block")

    def test_generic_profile_has_all_blocks(self):
        """Sprint 3: Generic profile should have all 4 blocks."""
        profile_path = Path("apps/data-platform/hotpass/profiles/generic.yaml")
        expect(profile_path.exists(), "Generic profile should exist")

        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        required_blocks = ["ingest", "refine", "enrich", "compliance"]
        for block in required_blocks:
            expect(block in profile, f"Generic profile must have {block} block")

    def test_test_profile_exists(self):
        """Sprint 3: Test profile should exist for QA purposes."""
        profile_path = Path("apps/data-platform/hotpass/profiles/test.yaml")
        expect(profile_path.exists(), "Test profile should exist")

        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        expect(profile["name"] == "test", "Test profile should have name 'test'")

    def test_ingest_block_structure(self):
        """Sprint 3: Ingest block should have required fields."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        ingest = profile["ingest"]
        expect("sources" in ingest, "ingest block must have sources")
        expect("chunk_size" in ingest, "ingest block must have chunk_size")
        expect(isinstance(ingest["sources"], list), "sources must be a list")

    def test_refine_block_structure(self):
        """Sprint 3: Refine block should have required fields."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        refine = profile["refine"]
        expect("mappings" in refine, "refine block must have mappings")
        expect("deduplication" in refine, "refine block must have deduplication")
        expect("expectations" in refine, "refine block must have expectations")
        expect(isinstance(refine["mappings"], dict), "mappings must be a dict")

    def test_enrich_block_structure(self):
        """Sprint 3: Enrich block should have required fields."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        enrich = profile["enrich"]
        expect("allow_network" in enrich, "enrich block must have allow_network")
        expect("fetcher_chain" in enrich, "enrich block must have fetcher_chain")
        expect(isinstance(enrich["fetcher_chain"], list), "fetcher_chain must be a list")

    def test_compliance_block_structure(self):
        """Sprint 3: Compliance block should have required fields."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        compliance = profile["compliance"]
        expect("policy" in compliance, "compliance block must have policy")
        expect("pii_fields" in compliance, "compliance block must have pii_fields")
        expect(isinstance(compliance["pii_fields"], list), "pii_fields must be a list")


class TestProfileLinter:
    """Tests for profile linter tool."""

    def test_profile_linter_exists(self):
        """Sprint 3: Profile linter tool should exist."""
        linter_path = Path("tools/profile_lint.py")
        expect(linter_path.exists(), "Profile linter should exist at tools/profile_lint.py")

    def test_profile_linter_runs_successfully(self):
        """Sprint 3: Profile linter should validate all profiles."""
        result = subprocess.run(
            ["python", "tools/profile_lint.py"],
            capture_output=True,
            text=True,
        )

        expect(result.returncode == 0, f"Profile linter should pass: {result.stdout}")
        expect("PASS" in result.stdout, "Linter output should show PASS")

    def test_profile_linter_with_specific_profile(self):
        """Sprint 3: Profile linter should validate specific profiles."""
        result = subprocess.run(
            ["python", "tools/profile_lint.py", "--profile", "aviation"],
            capture_output=True,
            text=True,
        )

        expect(
            result.returncode == 0,
            f"Aviation profile should lint successfully: {result.stdout}",
        )
        expect("aviation: PASS" in result.stdout, "Should show aviation profile passed")


class TestQAProfileValidation:
    """Tests for QA command profile validation."""

    def test_qa_profiles_command(self):
        """Sprint 3: QA command should support profile validation."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "qa", "profiles"],
            capture_output=True,
            text=True,
        )

        expect(result.returncode == 0, f"QA profiles should succeed: {result.stderr}")

    def test_qa_all_includes_profiles(self):
        """Sprint 3: QA all should include profile validation."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "qa", "all"],
            capture_output=True,
            text=True,
        )

        # Should succeed or at least run profile validation
        output = result.stdout.lower()
        expect(
            "profile" in output,
            f"QA all should include profile validation: {result.stdout}",
        )


class TestFitnessFunctionsProfiles:
    """Tests for fitness functions profile checks."""

    def test_fitness_functions_check_profiles(self):
        """Sprint 3: Fitness functions should check profile completeness."""
        result = subprocess.run(
            ["python", "ops/quality/fitness_functions.py"],
            capture_output=True,
            text=True,
        )

        expect(
            result.returncode == 0,
            f"Fitness functions should pass: {result.stdout}",
        )


class TestBackwardsCompatibility:
    """Tests to ensure profile changes are backwards compatible."""

    def test_profiles_still_have_legacy_fields(self):
        """Sprint 3: Profiles should retain legacy fields for backwards compatibility."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        # Check legacy fields still exist
        legacy_fields = [
            "default_country_code",
            "email_validation_threshold",
            "source_priorities",
            "column_synonyms",
        ]

        for field in legacy_fields:
            expect(
                field in profile,
                f"Aviation profile should retain legacy field: {field}",
            )

    def test_column_synonyms_match_mappings(self):
        """Sprint 3: Legacy column_synonyms should match refine.mappings."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        # Both should exist
        expect("column_synonyms" in profile, "Legacy column_synonyms should exist")
        expect(
            "refine" in profile and "mappings" in profile["refine"],
            "New mappings should exist",
        )

        # Keys should match
        legacy_keys = set(profile["column_synonyms"].keys())
        new_keys = set(profile["refine"]["mappings"].keys())

        expect(
            legacy_keys == new_keys,
            f"Legacy and new column keys should match: {legacy_keys} vs {new_keys}",
        )


class TestQG2DataQualityGate:
    """QG-2: Data Quality Gate implementation."""

    def test_qg2_profile_expectations_defined(self):
        """QG-2a: Profiles should define expectations."""
        profile_path = Path("apps/data-platform/hotpass/profiles/aviation.yaml")
        with open(profile_path) as f:
            profile = yaml.safe_load(f)

        refine = profile["refine"]
        expect("expectations" in refine, "Profile should define expectations")
        expect(
            len(refine["expectations"]) > 0,
            "Profile should have at least one expectation",
        )

    def test_qg2_qa_command_exists(self):
        """QG-2b: QA command should exist (full GE integration in future)."""
        result = subprocess.run(
            ["uv", "run", "hotpass", "qa", "--help"],
            capture_output=True,
            text=True,
        )

        expect(result.returncode == 0, "QA command should exist")
        # Note: Full Great Expectations integration would be added here
        # For now, we've established the structure
