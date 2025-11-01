"""Entity resolution behaviour tests covering fallback paths."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from hotpass.entity_resolution import (
    _derive_slug_keys,
    _load_entity_history,
    _slugify,
    add_ml_priority_scores,
    build_entity_registry,
    calculate_completeness_score,
    resolve_entities_fallback,
)

from tests.helpers.assertions import expect


def test_slugify_normalises_accents_and_whitespace() -> None:
    slug = _slugify("  Résumé  Holdings  ")
    expect(
        slug == "resume-holdings",
        "Slugify should strip diacritics and collapse whitespace",
    )
    expect(_slugify(None) == "", "None inputs should return empty string")


def test_derive_slug_keys_uses_existing_and_fallbacks() -> None:
    df = pd.DataFrame(
        {
            "organization_slug": [None, "", None],
            "organization_name": ["Alpha Labs", "Beta LLC", None],
            "province": ["Gauteng", "", "Western Cape"],
            "address_primary": ["123 Main", "", "456 High"],
        }
    )
    keys = _derive_slug_keys(df)
    expect(len(keys.unique()) == len(df), "Each row should resolve to a unique slug")
    expect(
        keys.iloc[0] == "alpha-labs",
        "Missing slug should fall back to organisation name",
    )
    expect(
        keys.iloc[2] == "western-cape-456-high",
        "Composite keys should use province and address when names missing",
    )


def test_load_entity_history_parses_supported_format(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    history.write_text(
        json.dumps(
            [
                {
                    "entity_id": 1,
                    "organization_name": "Alpha Labs",
                    "name_variants": ["Alpha"],
                    "status_history": [{"status": "active", "date": "2024-01-01T00:00:00"}],
                }
            ]
        )
    )
    loaded = _load_entity_history(str(history))
    expect(not loaded.empty, "History loader should parse JSON array")
    expect(
        isinstance(loaded.loc[0, "name_variants"], list),
        "Name variants should normalise to list",
    )


def test_resolve_entities_fallback_removes_duplicates() -> None:
    df = pd.DataFrame(
        {
            "organization_name": ["Alpha Labs", "alpha labs", "Beta"],
            "province": ["Gauteng", "Gauteng", "Western Cape"],
        }
    )
    deduped, matches = resolve_entities_fallback(df)
    expect(len(deduped) == 2, "Duplicate names should collapse to single row")
    expect(matches.empty, "Fallback path should not emit match pairs")


def test_build_entity_registry_merges_history(tmp_path: Path) -> None:
    current = pd.DataFrame(
        {
            "organization_name": ["Alpha Labs", "Gamma"],
            "status": ["active", "pending"],
            "organization_slug": ["alpha-labs", None],
        }
    )
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            [
                {
                    "entity_id": 10,
                    "organization_name": "Alpha Labs",
                    "name_variants": ["Alpha Holdings"],
                    "status_history": [{"status": "pending", "date": "2024-01-01T00:00:00"}],
                }
            ]
        )
    )

    registry = build_entity_registry(current, str(history_path))
    expect(len(registry) == 2, "Two entities should be present after merge")
    alpha = registry.loc[registry["organization_name"] == "Alpha Labs"].iloc[0]
    expect(alpha["entity_id"] == 10, "Existing entity should retain its identifier")
    expect(
        alpha["status_history"][-1]["status"] == "active",
        "Current status should append to history",
    )


def test_calculate_completeness_score_counts_fields() -> None:
    row = pd.Series(
        {
            "organization_name": "Alpha",
            "province": "Gauteng",
            "contact_primary_email": "user@example.com",
            "contact_primary_phone": None,
            "website": "https://example.com",
            "address_primary": "123 Main",
            "organization_category": "Training",
        }
    )
    score = calculate_completeness_score(row)
    expect(abs(score - (6 / 7)) < 1e-6, "Completeness should reflect filled fields")


def test_add_ml_priority_scores_extends_dataframe() -> None:
    df = pd.DataFrame(
        {
            "organization_name": ["Alpha"],
            "contact_primary_email": ["user@example.com"],
            "contact_primary_phone": ["0211234567"],
            "province": ["Gauteng"],
            "status": ["active"],
        }
    )
    enriched = add_ml_priority_scores(df)
    expect("priority_score" in enriched.columns, "Priority score column should be added")
    expect("completeness_score" in enriched.columns, "Completeness score should be added")
