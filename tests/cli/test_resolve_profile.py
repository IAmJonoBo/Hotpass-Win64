from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from hotpass.cli.commands.resolve import _resolve_options
from hotpass.cli.configuration import CLIProfile, FeatureFlags
from hotpass.cli.main import main as cli_main
from hotpass.linkage import LabelStudioConfig



def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class DummyLogger:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.console = None

    def log_error(self, message: str) -> None:
        self.errors.append(message)

    def log_event(self, name: str, payload: dict[str, object]) -> None:
        self.events.append((name, payload))


def test_resolve_profile_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_path = tmp_path / "duplicates.csv"
    output_path = tmp_path / "deduped.csv"
    dataset = pd.DataFrame(
        {
            "organization_name": ["Acme Flight", "Acme Flight"],
            "contact_email": ["ops@acme.test", "ops@acme.test"],
            "contact_phone": ["+2711000000", "+2711000000"],
        }
    )
    dataset.to_csv(input_path, index=False)

    profile_path = tmp_path / "advanced-resolve.toml"
    profile_path.write_text(
        """
name = "advanced-resolve"
summary = "Advanced resolve coverage"
log_format = "json"
industry_profile = "test"

[features]
entity_resolution = true

[options]
sensitive_fields = ["contact_email"]
"""
    )

    captured: dict[str, object] = {}

    def fake_structured_logger(
        log_format: str, sensitive_fields: tuple[str, ...]
    ) -> DummyLogger:
        captured["log_format"] = log_format
        captured["sensitive_fields"] = tuple(sensitive_fields)
        return DummyLogger()

    class DummyResult:
        def __init__(self, deduped: pd.DataFrame) -> None:
            self.deduplicated = deduped
            self.matches = pd.DataFrame({"classification": []})
            self.review_queue = pd.DataFrame({"classification": []})
            from hotpass.linkage import LinkageThresholds

            self.thresholds = LinkageThresholds(high=0.9, review=0.7)

    def fake_link_entities(df: pd.DataFrame, config: Any) -> DummyResult:
        captured["use_splink"] = config.use_splink
        captured["threshold_high"] = config.thresholds.high
        captured["threshold_review"] = config.thresholds.review
        return DummyResult(df.iloc[[0]].copy())

    monkeypatch.setattr(
        "hotpass.cli.commands.resolve.StructuredLogger", fake_structured_logger
    )
    monkeypatch.setattr(
        "hotpass.cli.commands.resolve.link_entities", fake_link_entities
    )

    exit_code = cli_main(
        [
            "resolve",
            "--input-file",
            str(input_path),
            "--output-file",
            str(output_path),
            "--profile",
            str(profile_path),
        ]
    )

    expect(exit_code == 0, "Resolve command should succeed with advanced profile")
    expect(output_path.exists(), "Deduplicated output should be written")
    expect(
        captured.get("log_format") == "json", "Profile should enforce JSON log format"
    )
    sensitive_fields = captured.get("sensitive_fields", ())
    expect(
        isinstance(sensitive_fields, tuple) and "contact_email" in sensitive_fields,
        "Sensitive fields from profile should propagate",
    )
    expect(
        captured.get("threshold_high") == 0.9,
        "Match threshold should honour CLI defaults when not overridden",
    )
    expect(
        captured.get("threshold_review") == 0.7,
        "Review threshold should honour CLI defaults when not overridden",
    )
    expect(
        captured.get("use_splink") is True,
        "Entity resolution feature flag should enable Splink",
    )
    expect(output_path.read_text().strip() != "", "Output CSV should contain data")


def _namespace(tmp_path: Path, **overrides: Any) -> Namespace:
    defaults: dict[str, Any] = {
        "input_file": tmp_path / "in.csv",
        "output_file": tmp_path / "out.csv",
        "threshold": 0.8,
        "use_splink": None,
        "match_threshold": None,
        "review_threshold": None,
        "label_studio_url": None,
        "label_studio_token": None,
        "label_studio_project": None,
        "log_format": None,
        "sensitive_fields": None,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def _profile(**flags: bool) -> CLIProfile:
    feature_flags = FeatureFlags(**flags)
    return CLIProfile(name="advanced", features=feature_flags)


def test_resolve_options_profile_enables_splink_by_default(tmp_path: Path) -> None:
    namespace = _namespace(tmp_path)
    options = _resolve_options(namespace, profile=_profile(entity_resolution=True))

    expect(options.use_splink is True, "Profile flag should default to Splink usage")
    expect(
        options.match_threshold == options.threshold,
        "match threshold should inherit base threshold when unspecified",
    )
    expect(
        options.review_threshold == options.threshold,
        "review threshold should inherit base threshold when unspecified",
    )


def test_resolve_options_honours_cli_disable_flag(tmp_path: Path) -> None:
    namespace = _namespace(tmp_path, use_splink=False)
    options = _resolve_options(namespace, profile=_profile(entity_resolution=True))

    expect(
        options.use_splink is False,
        "Explicit CLI flag should override profile defaults",
    )


def test_resolve_profile_supports_label_studio_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "deduped.csv"
    pd.DataFrame(
        {"organization_name": ["Example"], "contact_email": ["one@example.com"]}
    ).to_csv(input_path, index=False)

    captured: dict[str, Any] = {}

    class DummyResult:
        def __init__(self) -> None:
            frame = pd.DataFrame(
                {"organization_name": ["Example"], "classification": ["match"]}
            )
            self.deduplicated = frame[["organization_name"]]
            self.matches = frame
            self.review_queue = pd.DataFrame()

    def fake_link_entities(df: pd.DataFrame, config: Any) -> DummyResult:
        captured["label_studio"] = config.label_studio
        return DummyResult()

    monkeypatch.delenv("FEATURE_ENABLE_REMOTE_RESEARCH", raising=False)
    monkeypatch.delenv("ALLOW_NETWORK_RESEARCH", raising=False)
    monkeypatch.setattr(
        "hotpass.cli.commands.resolve.link_entities", fake_link_entities
    )

    exit_code = cli_main(
        [
            "resolve",
            "--input-file",
            str(input_path),
            "--output-file",
            str(output_path),
            "--label-studio-url",
            "https://label.example",
            "--label-studio-token",
            "token-123",
            "--label-studio-project",
            "42",
        ]
    )

    expect(exit_code == 0, "Resolve command should succeed with Label Studio options")
    label_config_any = captured.get("label_studio")
    expect(label_config_any is not None, "Label Studio config should be constructed")
    label_config = cast(LabelStudioConfig, label_config_any)
    expect(
        label_config.api_url == "https://label.example",
        "Label Studio URL should propagate",
    )
    expect(label_config.api_token == "token-123", "Label Studio token should propagate")
    expect(label_config.project_id == 42, "Label Studio project id should propagate")
