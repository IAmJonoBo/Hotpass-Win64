from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hotpass.cli.main import main as cli_main
from tests.helpers.assertions import expect


class DummySummary:
    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.total_records = 12
        self.elapsed_seconds = 0.42
        self.archive_path: Path | None = None

    def to_payload(self) -> dict[str, Any]:
        return {"success": self.success, "records": self.total_records}


def _write_profile(tmp_path: Path, *, enable_all: bool = True) -> Path:
    profile_path = tmp_path / "advanced-profile.toml"
    feature_block = """
[features]
entity_resolution = true
geospatial = true
enrichment = true
compliance = true
observability = true
"""
    if not enable_all:
        feature_block = """
[features]
entity_resolution = true
geospatial = false
enrichment = false
compliance = false
observability = false
"""

    profile_path.write_text(
        f"""
name = "advanced"
summary = "Advanced orchestrator profile"
log_format = "json"
industry_profile = "aviation"
intent = ["governed investigations"]

[options]
sensitive_fields = ["contact_email"]
{feature_block}
""",
        encoding="utf-8",
    )
    return profile_path


def _fake_logger(captured: dict[str, Any]):
    class _Logger:
        def __init__(self, log_format: str, sensitive_fields: Any) -> None:
            captured["log_format"] = log_format
            captured["sensitive_fields"] = tuple(sensitive_fields or ())
            self.console = None
            self.errors: list[str] = []

        def log_event(self, name: str, payload: dict[str, Any]) -> None:
            captured.setdefault("events", []).append((name, payload))

        def log_error(self, message: str) -> None:
            self.errors.append(message)

        def log_archive(self, path: Path) -> None:  # pragma: no cover - not exercised
            captured.setdefault("archives", []).append(path)

    return _Logger


def _fake_run_pipeline_once(captured: dict[str, Any]):
    def _run(options: Any) -> DummySummary:
        captured["runner"] = options.runner
        captured["runner_kwargs"] = options.runner_kwargs
        captured["profile_name"] = options.profile_name
        captured["telemetry_context"] = options.telemetry_context
        captured["canonical_config"] = options.config
        return DummySummary()

    return _run


def test_orchestrate_cli_profile_enables_advanced_features(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_path = _write_profile(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_path = tmp_path / "out.xlsx"

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "hotpass.cli.commands.orchestrate.StructuredLogger",
        _fake_logger(captured),
    )
    monkeypatch.setattr(
        "hotpass.cli.commands.orchestrate.run_pipeline_once",
        _fake_run_pipeline_once(captured),
    )

    exit_code = cli_main(
        [
            "orchestrate",
            "--input-dir",
            str(input_dir),
            "--output-path",
            str(output_path),
            "--profile",
            str(profile_path),
            "--enable-all",
        ]
    )

    expect(exit_code == 0, "Orchestrate CLI should exit successfully")
    runner = captured.get("runner")
    expect(runner is not None, "Enhanced runner should be configured when features enabled")
    runner_kwargs = captured.get("runner_kwargs") or {}
    enhanced_config = runner_kwargs.get("enhanced_config")
    expect(enhanced_config is not None, "Enhanced config should pass to runner")
    expect(enhanced_config.enable_enrichment is True, "Enable-all should toggle enrichment")
    expect(enhanced_config.enable_compliance is True, "Enable-all should toggle compliance")
    expect(enhanced_config.enable_geospatial is True, "Enable-all should toggle geospatial")
    expect(enhanced_config.enable_entity_resolution is True, "Enable-all should toggle linkage features")
    expect(enhanced_config.enable_observability is True, "Enable-all should toggle observability")
    sensitive = captured.get("sensitive_fields")
    expect("contact_email" in sensitive, "Profile sensitive fields should propagate to logger")


def test_orchestrate_cli_overrides_disable_enrichment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_path = _write_profile(tmp_path)
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    output_path = tmp_path / "refined.xlsx"
    linkage_dir = tmp_path / "linkage-data"

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "hotpass.cli.commands.orchestrate.StructuredLogger",
        _fake_logger(captured),
    )
    monkeypatch.setattr(
        "hotpass.cli.commands.orchestrate.run_pipeline_once",
        _fake_run_pipeline_once(captured),
    )

    exit_code = cli_main(
        [
            "orchestrate",
            "--input-dir",
            str(input_dir),
            "--output-path",
            str(output_path),
            "--profile",
            str(profile_path),
            "--enable-all",
            "--disable-enrichment",
            "--linkage-output-dir",
            str(linkage_dir),
        ]
    )

    expect(exit_code == 0, "CLI should succeed when disabling enrichment explicitly")
    runner_kwargs = captured.get("runner_kwargs") or {}
    enhanced_config = runner_kwargs.get("enhanced_config")
    expect(enhanced_config is not None, "Enhanced config should be available")
    expect(enhanced_config.enable_enrichment is False, "Disable flag should override enable-all")
    expect(enhanced_config.linkage_config is not None, "Linkage config should be constructed")
    persistence = enhanced_config.linkage_config.persistence
    expect(
        persistence.root_dir == linkage_dir.resolve(),
        "Linkage output directory should respect CLI override",
    )
