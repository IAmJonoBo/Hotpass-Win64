from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from hotpass.cli.main import main as cli_main
from hotpass.research import ResearchContext

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


def test_plan_research_cli_respects_allow_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _write_dataset(tmp_path)
    output_path = tmp_path / "plan.json"

    class DummyOutcome:
        def __init__(self) -> None:
            self.plan = SimpleNamespace(entity_name="Example Flight School", allow_network=True)
            self.steps = [SimpleNamespace(name="local_snapshot", status="success", message="ok")]
            self.elapsed_seconds = 0.12
            self._payload = {
                "plan": {"entity_name": self.plan.entity_name, "allow_network": True},
                "steps": [{"name": "local_snapshot", "status": "success", "message": "ok"}],
                "success": True,
            }

        @property
        def success(self) -> bool:
            return True

        def to_dict(self) -> dict[str, object]:
            return self._payload

    captured: dict[str, object] = {}

    def fake_plan(self, context: ResearchContext) -> DummyOutcome:
        captured["allow_network"] = context.allow_network
        captured["urls"] = tuple(context.urls)
        captured["entity_name"] = context.row["organization_name"]
        return DummyOutcome()

    monkeypatch.setenv("FEATURE_ENABLE_REMOTE_RESEARCH", "1")
    monkeypatch.setenv("ALLOW_NETWORK_RESEARCH", "1")
    monkeypatch.setattr("hotpass.research.ResearchOrchestrator.plan", fake_plan, raising=False)

    exit_code = cli_main(
        [
            "plan",
            "research",
            "--dataset",
            str(dataset),
            "--row-id",
            "0",
            "--url",
            "https://example.test",
            "--allow-network",
            "--json",
            "--output",
            str(output_path),
        ]
    )

    expect(exit_code == 0, "CLI plan research should exit successfully when network enabled")
    expect(captured.get("allow_network") is True, "Context should opt into network operations")
    expect(captured.get("urls") == ("https://example.test",), "Target URLs should propagate")
    expect(output_path.exists(), "Plan output should be written to disk")
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    expect(payload["plan"]["allow_network"] is True, "JSON payload should reflect network flag")
