"""Industry profile configuration regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from hotpass.config import (IndustryProfile, get_default_profile,
                            load_industry_profile, save_industry_profile)

import pytest

from tests.helpers.assertions import expect

pytestmark = pytest.mark.bandwidth("smoke")


def test_load_industry_profile_prefers_yaml(tmp_path: Path) -> None:
    config_dir = tmp_path / "profiles"
    config_dir.mkdir()
    (config_dir / "custom.yaml").write_text(
        dedent(
            """
            name: custom
            display_name: Custom
            default_country_code: ZA
            column_synonyms:
              organization_name:
                - company
            required_fields:
              - organization_name
            optional_fields: []
            """
        ),
        encoding="utf-8",
    )
    (config_dir / "custom.json").write_text(json.dumps({"name": "should_not_load"}))

    profile = load_industry_profile("custom", config_dir)

    expect(profile.name == "custom", "YAML file should take precedence over JSON")
    expect(
        profile.column_synonyms["organization_name"] == ["company"],
        "YAML content should parse",
    )


def test_load_industry_profile_falls_back_to_default(tmp_path: Path) -> None:
    profile = load_industry_profile("missing", tmp_path)
    expect(profile.name == "generic", "Missing profile should use generic fallback")


def test_save_industry_profile_round_trips(tmp_path: Path) -> None:
    profile = get_default_profile("aviation")
    save_industry_profile(profile, tmp_path)

    saved = load_industry_profile("aviation", tmp_path)
    expect(
        saved.display_name == profile.display_name,
        "Saved profile should reload with same data",
    )


def test_industry_profile_from_dict_validation() -> None:
    valid = IndustryProfile.from_dict({"name": "example", "display_name": "Example"})
    expect(valid.name == "example", "Minimal payload should validate")

    try:
        IndustryProfile.from_dict({"name": "broken", "required_fields": "not-a-list"})
    except ValueError as exc:
        expect(
            "required_fields" in str(exc),
            "Validation error should mention invalid type",
        )
    else:  # pragma: no cover - defensive guard
        raise AssertionError("ValueError expected for invalid required_fields type")
