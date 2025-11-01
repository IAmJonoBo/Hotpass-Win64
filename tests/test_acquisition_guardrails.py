import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

collect_dataset = importlib.import_module("ops.acquisition.collect_dataset")
guardrails_module = importlib.import_module("ops.acquisition.guardrails")

collect_main = collect_dataset.main
CollectionGuards = guardrails_module.CollectionGuards
ProviderPolicy = guardrails_module.ProviderPolicy
ProvenanceLedger = guardrails_module.ProvenanceLedger
RobotsTxtGuard = guardrails_module.RobotsTxtGuard
TermsOfServicePolicy = guardrails_module.TermsOfServicePolicy


def test_robots_guard_allows_allowed_paths(tmp_path: Path) -> None:
    robots = tmp_path / "robots.txt"
    robots.write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    guard = RobotsTxtGuard(str(robots))
    guard.ensure_allowed("https://example.com/data.csv")


def test_robots_guard_denies_disallowed_path(tmp_path: Path) -> None:
    robots = tmp_path / "robots.txt"
    robots.write_text("User-agent: Hotpass\nDisallow: /private\n", encoding="utf-8")
    guard = RobotsTxtGuard(str(robots), user_agent="Hotpass")
    with pytest.raises(PermissionError):
        guard.ensure_allowed("https://example.com/private/resource.json")


def test_provenance_ledger_appends_entries(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = ProvenanceLedger(ledger_path)
    ledger.append(
        record_id="123",
        source="https://example.com/data.csv",
        license="CC-BY-4.0",
        policy_hash="abc123",
        metadata={"note": "demo"},
    )
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["record_id"] == "123"
    assert payload["policy_hash"] == "abc123"
    assert payload["metadata"]["note"] == "demo"


def test_collection_guards_guard_many(tmp_path: Path) -> None:
    robots = tmp_path / "robots.txt"
    robots.write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    tos_path = tmp_path / "tos.txt"
    tos_path.write_text("Terms", encoding="utf-8")

    guards = CollectionGuards(
        robots_guard=RobotsTxtGuard(str(robots)),
        ledger=ProvenanceLedger(tmp_path / "ledger.jsonl"),
        tos_policy=TermsOfServicePolicy.from_path(tos_path),
    )

    records = [("1", {"value": "a"}), ("2", {"value": "b"})]
    guards.guard_many(records, source_url="https://example.com/data.csv", license="ODC-BY")

    ledger_contents = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    logged = [json.loads(line) for line in ledger_contents.splitlines()]
    assert len(logged) == 2
    assert {entry["record_id"] for entry in logged} == {"1", "2"}


def test_provider_policy_allowlist(tmp_path: Path) -> None:
    policy_path = ROOT / "policy" / "acquisition" / "providers.json"
    policy = ProviderPolicy.from_path(policy_path)

    metadata = policy.ensure_allowed("LinkedIn")
    assert metadata["category"] == "professional_network"

    with pytest.raises(PermissionError):
        policy.ensure_allowed("unlisted")


def test_collect_dataset_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    robots = tmp_path / "robots.txt"
    robots.write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    tos_path = tmp_path / "tos.txt"
    tos_path.write_text("Example ToS", encoding="utf-8")
    records_path = tmp_path / "records.jsonl"
    records_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "1", "name": "Alpha"}),
                json.dumps({"id": "2", "name": "Beta"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = [
        "--records",
        str(records_path),
        "--source-url",
        "https://example.com/data.csv",
        "--license",
        "CC-BY-4.0",
        "--robots",
        str(robots),
        "--tos-path",
        str(tos_path),
        "--ledger",
        str(tmp_path / "ledger.jsonl"),
    ]

    exit_code = collect_main(args)
    assert exit_code == 0
    ledger_contents = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    logged = [json.loads(line) for line in ledger_contents.splitlines()]
    assert len(logged) == 2
    assert {entry["record_id"] for entry in logged} == {"1", "2"}
