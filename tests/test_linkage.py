from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.helpers.fixtures import fixture

pytest.importorskip("frictionless")

from hotpass.linkage import (
    LabelStudioConfig,
    LinkageConfig,  # noqa: E402
    LinkagePersistence,
    LinkageThresholds,
    link_entities,
)
from hotpass.linkage import runner as linkage_runner  # noqa: E402


@fixture
def sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "organization_name": "Aero Logistics",
                "organization_slug": "aero-logistics",
                "contact_primary_email": "ops@aerologistics.example",
                "contact_primary_phone": "+27110000000",
                "province": "Gauteng",
            },
            {
                "organization_name": "Aero  Logistics",
                "organization_slug": "aero-logistics",
                "contact_primary_email": "ops@aerologistics.example",
                "contact_primary_phone": "+27 11 000 0000",
                "province": "Gauteng",
            },
            {
                "organization_name": "Aero South",
                "contact_primary_email": "info@aerosouth.example",
                "contact_primary_phone": "+27210000000",
                "province": "Western Cape",
            },
        ]
    )


def test_link_entities_rule_based_classification(
    sample_dataframe: pd.DataFrame, tmp_path: Path
) -> None:
    persistence = LinkagePersistence(root_dir=tmp_path)
    config = LinkageConfig(
        use_splink=False,
        thresholds=LinkageThresholds(high=0.9, review=0.6),
        persistence=persistence,
    )

    result = link_entities(sample_dataframe, config)

    assert len(result.deduplicated) == 2
    assert "match_probability" in result.matches.columns
    assert result.matches["classification"].isin({"match", "review", "reject"}).all()
    assert persistence.matches_path().exists()
    assert persistence.review_path().exists()
    metadata = json.loads(persistence.metadata_path().read_text(encoding="utf-8"))
    assert metadata["thresholds"] == {"high": 0.9, "review": 0.6, "reject": 0.0}


def test_link_entities_label_studio_integration(
    sample_dataframe: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("splink.duckdb.linker")

    submitted_payloads: list[dict[str, object]] = []

    class StubConnector:
        def __init__(self, config: LabelStudioConfig) -> None:
            self.config = config

        def submit_tasks(self, tasks: list[dict[str, object]]) -> None:
            submitted_payloads.extend(tasks)

        def fetch_completed_annotations(self) -> list[dict[str, object]]:
            return [{"id": 1, "decision": "match"}]

    monkeypatch.setattr(linkage_runner, "LabelStudioConnector", StubConnector)

    variant = sample_dataframe.copy()
    variant.loc[1, "contact_primary_email"] = "ops+alt@aerologistics.example"
    variant.loc[1, "contact_primary_phone"] = "+27 11 000 9999"

    persistence = LinkagePersistence(root_dir=tmp_path)
    config = LinkageConfig(
        use_splink=True,
        thresholds=LinkageThresholds(high=0.9, review=0.01),
        persistence=persistence,
        label_studio=LabelStudioConfig(
            api_url="https://labelstudio.example",
            api_token="token",
            project_id=1,
        ),
    )

    result = link_entities(variant, config)

    assert submitted_payloads, "expected review payload to be submitted"
    decisions_path = persistence.decisions_path()
    assert decisions_path.exists()
    lines = decisions_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, "expected reviewer decisions to be persisted"
    record = json.loads(lines[0])
    assert record["thresholds"]["review"] == pytest.approx(config.thresholds.review)
    assert result.review_queue.shape[0] == len(submitted_payloads)


def test_link_entities_splink_review_queue(sample_dataframe: pd.DataFrame) -> None:
    pytest.importorskip("splink.duckdb.linker")

    variant = sample_dataframe.copy()
    variant.loc[1, "contact_primary_email"] = "ops+alt@aerologistics.example"
    variant.loc[1, "contact_primary_phone"] = "+27 11 000 9999"

    config = LinkageConfig(
        use_splink=True,
        thresholds=LinkageThresholds(high=0.9, review=0.01),
    )

    result = link_entities(variant, config)

    assert not result.review_queue.empty
    assert (result.matches["classification"] == "review").any()
