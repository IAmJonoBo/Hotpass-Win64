from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from unittest.mock import Mock

import pytest
from hotpass.telemetry.bootstrap import (
    TelemetryBootstrapOptions,
    bootstrap_metrics,
    telemetry_session,
)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_bootstrap_metrics_returns_none_when_disabled() -> None:
    options = TelemetryBootstrapOptions(enabled=False)

    expect(
        bootstrap_metrics(options) is None,
        "Bootstrap should return None when telemetry is disabled.",
    )


def test_bootstrap_options_normalise_attributes() -> None:
    options = TelemetryBootstrapOptions(
        resource_attributes={"keep": "value", "drop": None},
        exporter_settings={"console": {"timeout": 10}, "invalid": "noop"},
    )

    merged_attributes = options.merged_resource_attributes({"extra": "1", "skip": None})
    expect("drop" not in merged_attributes, "None-valued attributes should be removed.")
    expect(merged_attributes["keep"] == "value", "Original attributes should be preserved.")
    expect(
        merged_attributes["extra"] == "1",
        "Additional attributes should merge correctly.",
    )

    settings = options.merged_exporter_settings()
    expect("invalid" not in settings, "Non-mapping exporter settings should be ignored.")
    expect(
        settings["console"]["timeout"] == 10,
        "Mapping exporter settings should persist.",
    )


def test_telemetry_session_initializes_and_shuts_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = TelemetryBootstrapOptions(enabled=True, exporters=("console",))
    metrics = Mock(name="metrics")
    captured: dict[str, object] = {}

    def _fake_bootstrap(
        bootstrap_options: TelemetryBootstrapOptions,
        *,
        additional_attributes: Mapping[str, str] | None = None,
    ) -> Mock:
        captured["options"] = bootstrap_options
        captured["attributes"] = dict(additional_attributes or {})
        return metrics

    shutdown_mock = Mock(name="shutdown")

    monkeypatch.setattr(
        "hotpass.telemetry.bootstrap.bootstrap_metrics",
        _fake_bootstrap,
    )
    monkeypatch.setattr(
        "hotpass.telemetry.bootstrap.shutdown_observability",
        shutdown_mock,
    )

    with telemetry_session(
        options,
        additional_attributes={"hotpass.command": "test"},
    ) as context:
        expect(context is metrics, "Telemetry session should yield metrics from bootstrap.")

    expect(shutdown_mock.call_count == 1, "Shutdown should be called when session exits.")

    stored = captured["options"]
    expect(
        isinstance(stored, TelemetryBootstrapOptions),
        "Bootstrap should receive options.",
    )
    attributes = cast(dict[str, object], captured["attributes"])
    expect(
        attributes.get("hotpass.command") == "test",
        "Additional telemetry attributes should pass through.",
    )


def test_telemetry_session_skip_bootstrap_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = TelemetryBootstrapOptions(enabled=False)
    bootstrap_mock = Mock(name="bootstrap")
    shutdown_mock = Mock(name="shutdown")

    monkeypatch.setattr(
        "hotpass.telemetry.bootstrap.bootstrap_metrics",
        bootstrap_mock,
    )
    monkeypatch.setattr(
        "hotpass.telemetry.bootstrap.shutdown_observability",
        shutdown_mock,
    )

    with telemetry_session(options) as context:
        expect(context is None, "Disabled telemetry session should yield None.")

    expect(bootstrap_mock.call_count == 0, "Bootstrap should not be called when disabled.")
    expect(
        shutdown_mock.call_count == 0,
        "Shutdown should not run when telemetry is disabled.",
    )
