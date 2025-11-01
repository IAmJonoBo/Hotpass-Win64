#!/usr/bin/env python
"""Profile linter for Hotpass industry profiles.

This tool validates that all profiles follow the complete 4-block schema:
- Block 1: ingest (data source configuration)
- Block 2: refine (normalization and validation)
- Block 3: enrich (enrichment configuration)
- Block 4: compliance (POPIA and data governance)

Usage:
    python tools/profile_lint.py                    # Lint all profiles
    python tools/profile_lint.py --profile aviation # Lint specific profile
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


class ProfileLintError(Exception):
    """Raised when a profile fails validation."""


def load_profile(profile_path: Path) -> dict[str, Any]:
    """Load a profile YAML file.

    Args:
        profile_path: Path to the profile file

    Returns:
        Parsed profile dictionary

    Raises:
        ProfileLintError: If profile cannot be loaded
    """
    try:
        with open(profile_path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise ProfileLintError(f"Failed to load profile {profile_path}: {e}") from e


def validate_profile_structure(profile: dict[str, Any], profile_name: str) -> list[str]:
    """Validate that a profile has all required blocks and fields.

    Args:
        profile: The profile dictionary
        profile_name: Name of the profile for error messages

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required top-level fields
    required_fields = ["name", "display_name"]
    for field in required_fields:
        if field not in profile:
            errors.append(f"Missing required field: {field}")

    # Check Block 1: ingest
    if "ingest" not in profile:
        errors.append("Missing Block 1: ingest")
    else:
        ingest = profile["ingest"]
        required_ingest_fields = ["sources", "chunk_size"]
        for field in required_ingest_fields:
            if field not in ingest:
                errors.append(f"ingest block missing required field: {field}")

        # Validate sources structure
        if "sources" in ingest and not isinstance(ingest["sources"], list):
            errors.append("ingest.sources must be a list")

    # Check Block 2: refine
    if "refine" not in profile:
        errors.append("Missing Block 2: refine")
    else:
        refine = profile["refine"]
        required_refine_fields = ["mappings", "deduplication", "expectations"]
        for field in required_refine_fields:
            if field not in refine:
                errors.append(f"refine block missing required field: {field}")

        # Validate mappings structure
        if "mappings" in refine and not isinstance(refine["mappings"], dict):
            errors.append("refine.mappings must be a dictionary")

        # Validate deduplication structure
        if "deduplication" in refine:
            dedupe = refine["deduplication"]
            if not isinstance(dedupe, dict):
                errors.append("refine.deduplication must be a dictionary")
            else:
                if "strategy" not in dedupe:
                    errors.append("refine.deduplication missing 'strategy' field")
                if "threshold" not in dedupe:
                    errors.append("refine.deduplication missing 'threshold' field")

    # Check Block 3: enrich
    if "enrich" not in profile:
        errors.append("Missing Block 3: enrich")
    else:
        enrich = profile["enrich"]
        required_enrich_fields = ["allow_network", "fetcher_chain"]
        for field in required_enrich_fields:
            if field not in enrich:
                errors.append(f"enrich block missing required field: {field}")

        # Validate fetcher_chain
        if "fetcher_chain" in enrich:
            if not isinstance(enrich["fetcher_chain"], list):
                errors.append("enrich.fetcher_chain must be a list")

    # Check Block 4: compliance
    if "compliance" not in profile:
        errors.append("Missing Block 4: compliance")
    else:
        compliance = profile["compliance"]
        required_compliance_fields = ["policy", "pii_fields"]
        for field in required_compliance_fields:
            if field not in compliance:
                errors.append(f"compliance block missing required field: {field}")

        # Validate pii_fields
        if "pii_fields" in compliance and not isinstance(compliance["pii_fields"], list):
            errors.append("compliance.pii_fields must be a list")

    # Check authority sources (optional)
    authority_sources = profile.get("authority_sources")
    if authority_sources is not None:
        if not isinstance(authority_sources, list):
            errors.append("authority_sources must be a list when present")
        else:
            for index, source in enumerate(authority_sources):
                if not isinstance(source, dict):
                    errors.append(f"authority_sources[{index}] must be a mapping")
                    continue
                if "name" not in source:
                    errors.append(f"authority_sources[{index}] missing 'name'")
                cache_key = source.get("cache_key")
                if cache_key is not None and not isinstance(cache_key, str):
                    errors.append(f"authority_sources[{index}].cache_key must be a string")
                category = source.get("category", "registry")
                if category not in {"registry", "directory", "dataset"}:
                    errors.append(
                        f"authority_sources[{index}].category must be registry|directory|dataset"
                    )

    # Check research backfill configuration (optional)
    research_backfill = profile.get("research_backfill")
    if research_backfill is not None:
        if not isinstance(research_backfill, dict):
            errors.append("research_backfill must be a mapping when present")
        else:
            fields = research_backfill.get("fields")
            if fields is not None and not isinstance(fields, list):
                errors.append("research_backfill.fields must be a list")
            threshold = research_backfill.get("confidence_threshold")
            if threshold is not None and not isinstance(threshold, (int, float)):
                errors.append("research_backfill.confidence_threshold must be numeric")
            elif isinstance(threshold, (int, float)):
                if not 0 <= threshold <= 1:
                    errors.append("research_backfill.confidence_threshold must be between 0 and 1")

    research_rate_limit = profile.get("research_rate_limit")
    if research_rate_limit is not None:
        if not isinstance(research_rate_limit, dict):
            errors.append("research_rate_limit must be a mapping when present")
        else:
            min_interval = research_rate_limit.get("min_interval_seconds")
            if min_interval is not None and not isinstance(min_interval, (int, float)):
                errors.append("research_rate_limit.min_interval_seconds must be numeric")
            elif isinstance(min_interval, (int, float)) and min_interval < 0:
                errors.append("research_rate_limit.min_interval_seconds must be >= 0")
            burst = research_rate_limit.get("burst")
            if burst is not None and (not isinstance(burst, int) or burst <= 0):
                errors.append("research_rate_limit.burst must be a positive integer when provided")

    return errors


def lint_profile(profile_path: Path) -> tuple[bool, list[str]]:
    """Lint a single profile.

    Args:
        profile_path: Path to the profile file

    Returns:
        Tuple of (success, errors)
    """
    try:
        profile = load_profile(profile_path)
        errors = validate_profile_structure(profile, profile_path.stem)
        return len(errors) == 0, errors
    except ProfileLintError as e:
        return False, [str(e)]


def lint_all_profiles(profiles_dir: Path) -> dict[str, tuple[bool, list[str]]]:
    """Lint all profiles in a directory.

    Args:
        profiles_dir: Directory containing profile YAML files

    Returns:
        Dictionary mapping profile names to (success, errors) tuples
    """
    results = {}

    for profile_path in profiles_dir.glob("*.yaml"):
        success, errors = lint_profile(profile_path)
        results[profile_path.stem] = (success, errors)

    return results


def main() -> int:
    """Main entry point for profile linter.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(description="Lint Hotpass industry profiles for completeness")
    parser.add_argument(
        "--profile",
        type=str,
        help="Specific profile name to lint (e.g., 'aviation')",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("apps/data-platform/hotpass/profiles"),
        help="Directory containing profiles",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit lint results as JSON instead of human-readable output",
    )
    parser.add_argument(
        "--schema-json",
        action="store_true",
        help="Print the expected profile schema structure as JSON and exit",
    )

    args = parser.parse_args()

    if args.schema_json:
        schema = {
            "required": [
                "name",
                "display_name",
                "ingest",
                "refine",
                "enrich",
                "compliance",
            ],
            "optional": [
                "authority_sources",
                "research_backfill",
                "research_rate_limit",
            ],
            "ingest": {
                "required": ["sources", "chunk_size"],
            },
            "refine": {
                "required": ["mappings", "deduplication", "expectations"],
                "deduplication": {
                    "required": ["strategy", "threshold"],
                },
            },
            "enrich": {
                "required": ["allow_network", "fetcher_chain"],
            },
            "compliance": {
                "required": ["policy", "pii_fields"],
            },
            "authority_sources": (
                "list[{'name': str, 'category': 'registry|directory|dataset', 'cache_key': str?}]"
            ),
            "research_backfill": {
                "fields": "list[str]",
                "confidence_threshold": "float between 0 and 1",
            },
            "research_rate_limit": {
                "min_interval_seconds": "float >= 0",
                "burst": "int > 0",
            },
        }
        print(json.dumps(schema, indent=2))
        return 0

    if not args.profiles_dir.exists():
        print(f"Error: Profiles directory not found: {args.profiles_dir}", file=sys.stderr)
        return 1

    # Lint specific profile or all profiles
    if args.profile:
        profile_path = args.profiles_dir / f"{args.profile}.yaml"
        if not profile_path.exists():
            print(f"Error: Profile not found: {profile_path}", file=sys.stderr)
            return 1

        if not args.json:
            print(f"Linting profile: {args.profile}")
        success, errors = lint_profile(profile_path)
        summary = {
            "profiles": [
                {
                    "name": args.profile,
                    "passed": success,
                    "errors": errors,
                }
            ],
            "summary": {
                "total": 1,
                "passed": 1 if success else 0,
                "failed": 0 if success else 1,
                "all_passed": success,
            },
        }

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            if success:
                print(f"✓ {args.profile}: PASS")
            else:
                print(f"✗ {args.profile}: FAIL")
                for error in errors:
                    print(f"  - {error}")

        return 0 if success else 1
    else:
        # Lint all profiles
        results = lint_all_profiles(args.profiles_dir)

        all_passed = True
        if not args.json:
            print(f"Linting all profiles in {args.profiles_dir}")

        profile_entries = []
        for profile_name, (success, errors) in sorted(results.items()):
            profile_entries.append(
                {
                    "name": profile_name,
                    "passed": success,
                    "errors": errors,
                }
            )
            if not success:
                all_passed = False
            if not args.json:
                if success:
                    print(f"✓ {profile_name}: PASS")
                else:
                    print(f"✗ {profile_name}: FAIL")
                    for error in errors:
                        print(f"  - {error}")

        summary = {
            "profiles": profile_entries,
            "summary": {
                "total": len(results),
                "passed": sum(1 for s, _ in results.values() if s),
                "failed": sum(1 for s, _ in results.values() if not s),
                "all_passed": all_passed,
            },
        }

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print()
            print(f"Total profiles: {summary['summary']['total']}")
            print(f"Passed: {summary['summary']['passed']}")
            print(f"Failed: {summary['summary']['failed']}")

        return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
