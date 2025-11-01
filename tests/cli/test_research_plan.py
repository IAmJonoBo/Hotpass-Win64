from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from hotpass.cli.main import main as cli_main

from tests.helpers.pytest_marks import usefixtures


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "research-input.xlsx"
    df = pd.DataFrame(
        {
            "organization_name": ["Example Flight School"],
            "contact_primary_email": [""],
            "website": ["example.com"],
        }
    )
    df.to_excel(path, index=False)
    return path


@usefixtures("monkeypatch")
def test_plan_research_cli_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _write_dataset(tmp_path)
    monkeypatch.delenv("FEATURE_ENABLE_REMOTE_RESEARCH", raising=False)
    monkeypatch.delenv("ALLOW_NETWORK_RESEARCH", raising=False)

    exit_code = cli_main(
        [
            "plan",
            "research",
            "--dataset",
            str(dataset),
            "--row-id",
            "0",
            "--allow-network",
        ]
    )

    expect(exit_code == 0, "CLI plan research should exit successfully")


@usefixtures("monkeypatch")
def test_crawl_cli_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_ENABLE_REMOTE_RESEARCH", raising=False)
    monkeypatch.delenv("ALLOW_NETWORK_RESEARCH", raising=False)

    exit_code = cli_main(
        [
            "crawl",
            "https://example.test",
            "--allow-network",
        ]
    )

    expect(exit_code == 0, "Crawl command should exit successfully")
