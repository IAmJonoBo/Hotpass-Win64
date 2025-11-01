"""Unit tests for CLI configuration helpers and profile loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hotpass.cli import configuration, shared
from hotpass.config_schema import HotpassConfig


def test_load_profile_from_toml(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles" / "aviation.toml"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        """
name = "aviation"
summary = "Test profile"
expectation_suite = "aviation"
country_code = "ZA"
qa_mode = "strict"
log_format = "json"
observability = true
intent = ["Enable compliance"]

config_files = ["../shared/config.toml"]
options = {party_store_path = "dist/party.json"}

[features]
entity_resolution = true
compliance = true
"""
    )

    search_path = profile_path.parent
    profile = configuration.load_profile("aviation", search_paths=[search_path])

    assert profile.name == "aviation"
    assert profile.expectation_suite == "aviation"
    assert profile.features.entity_resolution is True
    assert profile.features.compliance is True
    assert profile.observability is True
    resolved = profile.resolved_config_files()
    assert resolved == [profile_path.parent.parent / "shared" / "config.toml"]


def test_load_profile_requires_intent_for_sensitive_features(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles" / "enrichment.toml"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        """
name = "enrichment"

[features]
enrichment = true
"""
    )

    with pytest.raises(configuration.ProfileIntentError):
        configuration.load_profile("enrichment", search_paths=[profile_path.parent])


def test_normalise_sensitive_fields_deduplicates_and_lowercases() -> None:
    values = shared.normalise_sensitive_fields(["Email", "", "PHONE", "email"], ("contact",))
    assert values == ("contact", "email", "phone")


def test_infer_report_format_handles_unknown_suffix(tmp_path: Path) -> None:
    html_path = tmp_path / "report.html"
    markdown_path = tmp_path / "report.md"
    other_path = tmp_path / "report.txt"

    assert shared.infer_report_format(html_path) == "html"
    assert shared.infer_report_format(markdown_path) == "markdown"
    assert shared.infer_report_format(other_path) is None


def test_load_config_supports_json(tmp_path: Path) -> None:
    json_path = tmp_path / "config.json"
    json_path.write_text(json.dumps({"archive": True}))

    payload = shared.load_config(json_path)
    assert payload == {"archive": True}


def test_profile_apply_to_config_merges_pipeline_defaults() -> None:
    profile = configuration.CLIProfile(
        name="demo",
        expectation_suite="aviation",
        country_code="GB",
        qa_mode="strict",
    )

    base = HotpassConfig()
    merged = profile.apply_to_config(base)

    assert merged.pipeline.expectation_suite == "aviation"
    assert merged.pipeline.country_code == "GB"
    assert merged.pipeline.qa_mode == "strict"
