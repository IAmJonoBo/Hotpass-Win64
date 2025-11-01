"""Smoke-level regression checks executed on every PR."""

from __future__ import annotations

import pytest

from hotpass.config import get_default_profile, load_industry_profile
from hotpass.telemetry.bootstrap import (TelemetryBootstrapOptions,
                                         bootstrap_metrics)
from tests.helpers.assertions import expect

pytestmark = pytest.mark.bandwidth("smoke")


def test_generic_profile_loads() -> None:
    profile = get_default_profile("generic")
    expect(profile.name == "generic", "Generic profile should be available")
    expect("organization_name" in profile.required_fields, "Profile should define required fields")


def test_profile_loader_handles_missing(tmp_path) -> None:
    loaded = load_industry_profile("missing", config_dir=tmp_path)
    expect(loaded.name == "generic", "Missing profile should fall back to generic")


def test_bootstrap_metrics_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    options = TelemetryBootstrapOptions(enabled=False)
    metrics = bootstrap_metrics(options)
    expect(metrics is None, "Disabled telemetry should not bootstrap metrics")


def test_bootstrap_metrics_initialises(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"initialise": 0}

    def fake_initialize_observability(**_: object) -> None:
        calls["initialise"] += 1

    def fake_get_pipeline_metrics() -> str:
        return "metrics"

    monkeypatch.setattr(
        "hotpass.telemetry.bootstrap.initialize_observability",
        fake_initialize_observability,
    )
    monkeypatch.setattr(
        "hotpass.telemetry.bootstrap.get_pipeline_metrics",
        fake_get_pipeline_metrics,
    )

    options = TelemetryBootstrapOptions(enabled=True, environment="smoke")
    metrics = bootstrap_metrics(options, additional_attributes={"build": "ci"})

    expect(calls["initialise"] == 1, "Telemetry bootstrap should initialise observability")
    expect(metrics == "metrics", "Bootstrap should return metrics object from helper")
