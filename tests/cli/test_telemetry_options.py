from argparse import Namespace
from pathlib import Path

from hotpass.cli.commands.run import _resolve_options

from tests.helpers.fixtures import fixture


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@fixture
def namespace(tmp_path: Path) -> Namespace:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_path = tmp_path / "refined.xlsx"
    return Namespace(
        config_paths=None,
        profile=None,
        profile_search_paths=None,
        log_format="json",
        sensitive_fields=None,
        interactive=None,
        qa_mode=None,
        input_dir=str(input_dir),
        output_path=str(output_path),
        expectation_suite_name=None,
        country_code=None,
        dist_dir=None,
        party_store_path=None,
        intent_digest_path=None,
        intent_signal_store=None,
        daily_list_path=None,
        daily_list_size=None,
        intent_webhooks=None,
        crm_endpoint=None,
        crm_token=None,
        automation_http_timeout=None,
        automation_http_retries=None,
        automation_http_backoff=None,
        automation_http_backoff_max=None,
        automation_http_circuit_threshold=None,
        automation_http_circuit_reset=None,
        automation_http_idempotency_header=None,
        automation_http_dead_letter=None,
        automation_http_dead_letter_enabled=None,
        automation_http_dead_letter_mode=None,
        automation_http_dead_letter_retention=None,
        automation_http_dead_letter_compress=None,
        observability=True,
        telemetry_service_name="hotpass-cli",
        telemetry_environment="staging",
        telemetry_exporters=["otlp"],
        telemetry_resource_attributes=["deployment=cli"],
        telemetry_otlp_headers=["Authorization=Bearer 123"],
        telemetry_otlp_endpoint="grpc://collector:4317",
        telemetry_otlp_metrics_endpoint="grpc://collector:4317",
        telemetry_otlp_insecure=True,
        telemetry_otlp_timeout=5.0,
        report_path=None,
        report_format=None,
        archive=None,
        enable_all=False,
        entity_resolution=None,
        geospatial=None,
        enrichment=None,
        compliance=None,
        feature_observability=None,
    )


def test_resolve_options_merges_telemetry(namespace: Namespace) -> None:
    options = _resolve_options(namespace, profile=None)
    config = options.canonical_config

    expect(config.telemetry.enabled is True, "Telemetry should be enabled via CLI flag.")
    expect(
        config.telemetry.service_name == "hotpass-cli",
        "Service name should override default.",
    )
    expect(config.telemetry.environment == "staging", "Environment should match CLI flag.")
    expect(
        config.telemetry.exporters == ("otlp",),
        "Exporter list should prefer CLI values.",
    )
    expect(
        config.telemetry.resource_attributes["deployment"] == "cli",
        "Resource attributes should parse KEY=VALUE pairs.",
    )
    exporter_settings = config.telemetry.resolved_exporter_settings()
    expect("otlp" in exporter_settings, "OTLP settings should be registered.")
    otlp_settings = exporter_settings["otlp"]
    expect(
        otlp_settings["endpoint"] == "grpc://collector:4317",
        "OTLP endpoint should honour CLI flag.",
    )
    expect(
        otlp_settings.get("headers", {}).get("Authorization") == "Bearer 123",
        "OTLP headers should parse KEY=VALUE pairs.",
    )
    expect(
        otlp_settings.get("insecure") is True,
        "OTLP insecure flag should propagate.",
    )
    expect(
        otlp_settings.get("timeout") == 5.0,
        "OTLP timeout should propagate from CLI.",
    )
