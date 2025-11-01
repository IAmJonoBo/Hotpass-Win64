#!/usr/bin/env python
"""Profile migration tool - migrate profiles from old to new schema.

This tool automates the migration of industry profiles from legacy format
to the new 4-block schema (ingest, refine, enrich, compliance).

Usage:
    python ops/migrate_profile.py <profile_path>
    python ops/migrate_profile.py apps/data-platform/hotpass/profiles/aviation.yaml --validate
    python ops/migrate_profile.py --check-all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def migrate_profile(profile_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    """
    Migrate a profile from old format to new 4-block schema.

    Args:
        profile_path: Path to the profile YAML file to migrate
        output_path: Optional path for migrated output (defaults to overwrite)

    Returns:
        The migrated profile dictionary
    """
    # Load existing profile
    with profile_path.open("r", encoding="utf-8") as f:
        profile: dict[str, Any] = yaml.safe_load(f)

    # Check if already migrated
    if all(block in profile for block in ["ingest", "refine", "enrich", "compliance"]):
        print(f"✓ Profile already uses new schema: {profile_path}")
        return profile

    migrated = {
        "name": profile.get("name", profile_path.stem),
        "display_name": profile.get("display_name", profile.get("name", profile_path.stem)),
    }

    # Migrate Block 1: Ingest
    if "ingest" not in profile:
        migrated["ingest"] = {
            "sources": [],
            "chunk_size": profile.get("chunk_size", 5000),
            "staging_enabled": profile.get("staging_enabled", True),
            "staging_format": profile.get("staging_format", "parquet"),
        }

        # Migrate source priorities if they exist
        source_priorities = profile.get("source_priorities", {})
        for source_name, priority in source_priorities.items():
            migrated["ingest"]["sources"].append(
                {
                    "name": source_name,
                    "format": "xlsx",
                    "path_pattern": f"data/*{source_name.lower().replace(' ', '_')}*.xlsx",
                    "priority": priority,
                }
            )
    else:
        migrated["ingest"] = profile["ingest"]

    # Migrate Block 2: Refine
    if "refine" not in profile:
        migrated["refine"] = {}

        # Migrate column mappings/synonyms
        if "column_synonyms" in profile or "mappings" in profile.get("refine", {}):
            migrated["refine"]["mappings"] = profile.get("column_synonyms", {})

        # Migrate deduplication
        if "deduplication" in profile:
            migrated["refine"]["deduplication"] = profile["deduplication"]
        else:
            migrated["refine"]["deduplication"] = {
                "strategy": "entity_resolution",
                "threshold": 0.85,
                "blocking_keys": ["organization_name_normalized"],
            }

        # Migrate normalization rules
        if "normalization" in profile:
            migrated["refine"]["normalization"] = profile["normalization"]
        else:
            migrated["refine"]["normalization"] = {
                "phone_format": "E164",
                "country_code": profile.get("default_country_code", "ZA"),
            }

        # Migrate expectations
        migrated["refine"]["expectations"] = profile.get("expectations", [])

        # Migrate quality thresholds
        if any(
            key in profile
            for key in [
                "email_validation_threshold",
                "phone_validation_threshold",
                "website_validation_threshold",
            ]
        ):
            migrated["refine"]["quality_thresholds"] = {
                "email": profile.get("email_validation_threshold", 0.85),
                "phone": profile.get("phone_validation_threshold", 0.85),
                "website": profile.get("website_validation_threshold", 0.75),
            }

        # Migrate required and optional fields
        migrated["refine"]["required_fields"] = profile.get(
            "required_fields", ["organization_name"]
        )
        migrated["refine"]["optional_fields"] = profile.get(
            "optional_fields",
            [
                "contact_primary_email",
                "contact_primary_phone",
                "website",
                "province",
                "address_primary",
            ],
        )
    else:
        migrated["refine"] = profile["refine"]

    # Migrate Block 3: Enrich
    if "enrich" not in profile:
        migrated["enrich"] = {
            "allow_network": False,
            "fetcher_chain": ["deterministic", "lookup_tables", "research"],
            "backfillable_fields": [
                "contact_email",
                "contact_phone",
                "website",
                "province",
            ],
            "confidence_threshold": 0.7,
            "provenance_required": True,
        }
    else:
        migrated["enrich"] = profile["enrich"]

    # Migrate Block 4: Compliance
    if "compliance" not in profile:
        migrated["compliance"] = {
            "policy": "POPIA",
            "jurisdiction": profile.get("default_country_code", "ZA"),
            "consent_required": True,
            "pii_fields": ["contact_email", "contact_phone", "contact_name"],
            "retention_days": 365,
            "anonymization_on_request": True,
            "audit_trail_required": True,
        }
    else:
        migrated["compliance"] = profile["compliance"]

    # Preserve legacy fields for backwards compatibility
    legacy_fields = {}
    for key in [
        "default_country_code",
        "organization_term",
        "organization_type_term",
        "organization_category_term",
        "email_validation_threshold",
        "phone_validation_threshold",
        "website_validation_threshold",
        "source_priorities",
        "column_synonyms",
    ]:
        if key in profile:
            legacy_fields[key] = profile[key]

    migrated.update(legacy_fields)

    # Write migrated profile
    output = output_path or profile_path
    with output.open("w", encoding="utf-8") as f:
        yaml.safe_dump(migrated, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Migrated profile: {output}")
    return migrated


def validate_profile(profile_path: Path) -> tuple[bool, list[str]]:
    """
    Validate that a profile has all required blocks.

    Args:
        profile_path: Path to the profile YAML file

    Returns:
        Tuple of (is_valid, missing_blocks)
    """
    with profile_path.open("r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)

    required_blocks = ["ingest", "refine", "enrich", "compliance"]
    missing = [block for block in required_blocks if block not in profile]

    return len(missing) == 0, missing


def check_all_profiles(profiles_dir: Path) -> int:
    """
    Check all profiles in a directory for completeness.

    Args:
        profiles_dir: Directory containing profile YAML files

    Returns:
        Exit code (0 if all valid, 1 if any invalid)
    """
    profiles = list(profiles_dir.glob("*.yaml"))

    if not profiles:
        print(f"No profiles found in {profiles_dir}")
        return 1

    print(f"Checking {len(profiles)} profiles...\n")

    all_valid = True
    for profile_path in profiles:
        is_valid, missing = validate_profile(profile_path)

        if is_valid:
            print(f"✓ {profile_path.name}: Complete")
        else:
            print(f"✗ {profile_path.name}: Missing blocks - {', '.join(missing)}")
            all_valid = False

    print()
    if all_valid:
        print("✓ All profiles are valid")
        return 0
    else:
        print("✗ Some profiles need migration")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Migrate industry profiles to new schema")
    parser.add_argument(
        "profile",
        type=str,
        nargs="?",
        help="Path to profile YAML file to migrate",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for migrated profile (default: overwrite)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate profile completeness without migration",
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Check all profiles in apps/data-platform/hotpass/profiles/",
    )

    args = parser.parse_args()

    if args.check_all:
        profiles_dir = Path("apps/data-platform/hotpass/profiles")
        return check_all_profiles(profiles_dir)

    if not args.profile:
        parser.error("profile argument is required unless --check-all is specified")

    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"Error: Profile not found: {profile_path}", file=sys.stderr)
        return 1

    if args.validate:
        is_valid, missing = validate_profile(profile_path)
        if is_valid:
            print(f"✓ Profile is complete: {profile_path}")
            return 0
        else:
            print(f"✗ Profile missing blocks: {', '.join(missing)}")
            return 1

    # Migrate profile
    output_path = Path(args.output) if args.output else None
    migrate_profile(profile_path, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
