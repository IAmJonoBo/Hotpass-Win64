"""Implementation of the `hotpass run` subcommand."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from rich.prompt import Confirm

from hotpass.artifacts import create_refined_archive
from hotpass.automation.hooks import dispatch_webhooks, push_crm_updates
from hotpass.automation.http import AutomationHTTPClient, DeadLetterQueue
from hotpass.config import load_industry_profile
from hotpass.config_schema import HotpassConfig
from hotpass.error_handling import DataContractError
from hotpass.lineage import (
    build_hotpass_run_facet,
    build_output_datasets,
    create_emitter,
    discover_input_datasets,
)
from hotpass.orchestration import build_pipeline_job_name
from hotpass.pipeline import PipelineConfig, default_feature_bundle
from hotpass.pipeline.orchestrator import PipelineExecutionConfig, PipelineOrchestrator
from hotpass.telemetry.bootstrap import TelemetryBootstrapOptions, telemetry_session

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..progress import (
    DEFAULT_SENSITIVE_FIELD_TOKENS,
    PipelineProgress,
    StructuredLogger,
    render_progress,
)
from ..shared import infer_report_format, load_config, normalise_sensitive_fields

LEGACY_PIPELINE_KEYS: frozenset[str] = frozenset(
    {
        "input_dir",
        "output_path",
        "dist_dir",
        "archive",
        "expectation_suite",
        "country_code",
        "party_store_path",
        "log_format",
        "report_path",
        "report_format",
        "excel_chunk_size",
        "excel_engine",
        "excel_stage_dir",
        "qa_mode",
        "observability",
        "sensitive_fields",
    }
)


def _resolve_profile_name(config: PipelineConfig) -> str | None:
    industry_profile = getattr(config, "industry_profile", None)
    profile_name = getattr(industry_profile, "name", None)
    if profile_name:
        return str(profile_name)
    expectation = getattr(config, "expectation_suite_name", None)
    if expectation:
        return str(expectation)
    return None


def _first_dataset_name(datasets: Iterable[Any]) -> str | None:
    for dataset in datasets:
        if isinstance(dataset, Mapping):
            name = dataset.get("name")
            if name:
                return str(name)
        elif isinstance(dataset, Path):
            return str(dataset)
        else:
            candidate = str(dataset).strip()
            if candidate:
                return candidate
    return None


def _research_enabled() -> bool:
    truthy = {"1", "true", "yes", "on"}
    feature = os.getenv("FEATURE_ENABLE_REMOTE_RESEARCH", "0").lower()
    allow = os.getenv("ALLOW_NETWORK_RESEARCH", "false").lower()
    return feature in truthy and allow in truthy


@dataclass(slots=True)
class RunOptions:
    """Resolved options driving the core pipeline run."""

    canonical_config: HotpassConfig
    log_format: str
    report_path: Path | None
    report_format: str | None
    party_store_path: Path | None
    sensitive_fields: tuple[str, ...]
    interactive: bool | None
    profile_name: str | None


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "run",
        help="Run the Hotpass refinement pipeline",
        description=(
            "Validate, normalise, and publish refined workbooks with optional archiving "
            "and reporting."
        ),
        parents=[shared.base, shared.pipeline, shared.reporting, shared.excel],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="run",
        help="Run the Hotpass refinement pipeline",
        builder=build,
        handler=_command_handler,
        is_default=True,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    options = _resolve_options(namespace, profile)
    logger = StructuredLogger(options.log_format, options.sensitive_fields)
    console = logger.console if options.log_format == "rich" else None

    config = options.canonical_config

    if config.pipeline.run_id is None:
        generated_run_id = uuid4().hex
        config = config.merge({"pipeline": {"run_id": generated_run_id}})
        options = replace(options, canonical_config=config)

    interactive = options.interactive
    if interactive is None:
        interactive = console is not None and sys.stdin.isatty()

    input_dir = config.pipeline.input_dir
    output_path = config.pipeline.output_path

    if not input_dir.exists():
        logger.log_error(f"Input directory does not exist: {input_dir}")
        logger.log_error("Please create the directory or specify a different path with --input-dir")
        return 1
    if not input_dir.is_dir():
        logger.log_error(f"Input path is not a directory: {input_dir}")
        return 1

    excel_files = list(input_dir.glob("*.xlsx")) + list(input_dir.glob("*.xls"))
    if not excel_files:
        logger.log_error(f"No Excel files found in: {input_dir}")
        logger.log_error("Please add Excel files to the input directory")
        return 1

    if console:
        console.print("[bold cyan]Hotpass Data Refinement Pipeline[/bold cyan]")
        console.print(f"[dim]Profile:[/dim] {options.profile_name or 'default'}")
        console.print(f"[dim]Input directory:[/dim] {input_dir}")
        console.print(f"[dim]Output path:[/dim] {output_path}")
        console.print(f"[dim]Found {len(excel_files)} Excel file(s)[/dim]")
        console.print()

    progress_context = render_progress(console)
    with progress_context as progress:
        listener = progress.handle_event if isinstance(progress, PipelineProgress) else None

        base_config = config.to_pipeline_config(progress_listener=listener)
        enhanced_config = config.to_enhanced_config()
        orchestrator = PipelineOrchestrator()

        telemetry_options = TelemetryBootstrapOptions(
            enabled=enhanced_config.enable_observability,
            service_name=enhanced_config.telemetry_service_name,
            environment=enhanced_config.telemetry_environment,
            exporters=enhanced_config.telemetry_exporters,
            resource_attributes=enhanced_config.telemetry_attributes,
            exporter_settings=enhanced_config.telemetry_exporter_settings,
        )
        telemetry_context = {
            "hotpass.command": "hotpass run",
        }
        if options.profile_name:
            telemetry_context["hotpass.profile"] = options.profile_name
        if base_config.run_id:
            telemetry_context["hotpass.run_id"] = base_config.run_id

        with telemetry_session(
            telemetry_options, additional_attributes=telemetry_context
        ) as metrics:
            execution = PipelineExecutionConfig(
                base_config=base_config,
                enhanced_config=enhanced_config,
                features=default_feature_bundle(),
                metrics=metrics,
            )

            input_datasets = discover_input_datasets(base_config.input_dir)
            facets = build_hotpass_run_facet(
                profile=_resolve_profile_name(base_config),
                source_spreadsheet=_first_dataset_name(input_datasets),
                research_enabled=_research_enabled(),
            )
            emitter = create_emitter(
                build_pipeline_job_name(base_config),
                run_id=base_config.run_id,
                facets=facets,
            )
            emitter.emit_start(inputs=input_datasets)

            lineage_outputs = build_output_datasets(base_config.output_path)
            archive_path: Path | None = None

            try:
                result = orchestrator.run(execution)

                report = result.quality_report
                logger.log_summary(report)

                if console:
                    console.print()
                    console.print("[bold green]✓[/bold green] Pipeline completed successfully!")
                    console.print(f"[dim]Refined data written to:[/dim] {output_path}")

                if interactive and console and report.recommendations:
                    console.print()
                    if Confirm.ask("View top recommendations now?", default=True):
                        console.print("[bold]Top recommendations:[/bold]")
                        for recommendation in report.recommendations[:3]:
                            console.print(f"  • {recommendation}")

                if options.report_path is not None:
                    options.report_path.parent.mkdir(parents=True, exist_ok=True)
                    if options.report_format == "html":
                        options.report_path.write_text(report.to_html(), encoding="utf-8")
                    else:
                        options.report_path.write_text(report.to_markdown(), encoding="utf-8")
                    logger.log_report_write(options.report_path, options.report_format)

                if options.party_store_path is not None and result.party_store is not None:
                    options.party_store_path.parent.mkdir(parents=True, exist_ok=True)
                    payload = result.party_store.as_dict()
                    options.party_store_path.write_text(
                        json.dumps(payload, indent=2), encoding="utf-8"
                    )
                    logger.log_party_store(options.party_store_path)

                if (
                    config.pipeline.intent_digest_path is not None
                    and result.intent_digest is not None
                ):
                    logger.log_intent_digest(
                        config.pipeline.intent_digest_path,
                        int(result.intent_digest.shape[0]),
                    )

                digest_df = result.intent_digest
                daily_list_df = result.daily_list

                automation_http_config = base_config.automation_http
                http_client = AutomationHTTPClient(automation_http_config)
                dead_letter_queue: DeadLetterQueue | None = None
                if (
                    automation_http_config.dead_letter_enabled
                    and automation_http_config.dead_letter_path is not None
                ):
                    dead_letter_queue = DeadLetterQueue(automation_http_config.dead_letter_path)

                effective_digest = digest_df
                if effective_digest is None:
                    if daily_list_df is not None:
                        effective_digest = daily_list_df
                    else:
                        effective_digest = pd.DataFrame()

                if config.pipeline.intent_webhooks:
                    dispatch_webhooks(
                        effective_digest,
                        webhooks=config.pipeline.intent_webhooks,
                        daily_list=daily_list_df,
                        logger=logger,
                        http_client=http_client,
                        dead_letter=dead_letter_queue,
                    )

                if daily_list_df is not None and config.pipeline.crm_endpoint:
                    push_crm_updates(
                        daily_list_df,
                        config.pipeline.crm_endpoint,
                        token=config.pipeline.crm_token,
                        logger=logger,
                        http_client=http_client,
                        dead_letter=dead_letter_queue,
                    )

                store_path = config.pipeline.intent_signal_store_path
                if store_path is not None and not store_path.exists():
                    store_path.parent.mkdir(parents=True, exist_ok=True)
                    store_path.write_text("[]\n", encoding="utf-8")

                if config.pipeline.archive:
                    config.pipeline.dist_dir.mkdir(parents=True, exist_ok=True)
                    archive_path = create_refined_archive(output_path, config.pipeline.dist_dir)
                    logger.log_archive(archive_path)
                    lineage_outputs = build_output_datasets(base_config.output_path, archive_path)
            except DataContractError as exc:
                context = getattr(exc, "context", None)
                message = context.message if context is not None else str(exc)
                emitter.emit_fail(message, outputs=lineage_outputs)
                logger.log_error(f"Data contract validation failed: {message}")
                if console:
                    console.print("[bold red]✗ Data contract validation failed[/bold red]")
                    source_hint = (
                        context.source_file if context and context.source_file else "unknown"
                    )
                    console.print(f"[dim]Source:[/dim] {source_hint}")
                    details = context.details if context else "Unavailable"
                    console.print(f"[dim]Details:[/dim] {details}")
                    if context and context.suggested_fix:
                        console.print(f"[yellow]Suggested fix:[/yellow] {context.suggested_fix}")
                return 2
            except Exception as exc:  # pragma: no cover - defensive guard
                emitter.emit_fail(str(exc), outputs=lineage_outputs)
                logger.log_error(str(exc))
                if console:
                    console.print("[bold red]Pipeline failed with error:[/bold red]")
                    console.print_exception()
                return 1
            else:
                emitter.emit_complete(outputs=lineage_outputs)

    return 0


def _resolve_options(namespace: argparse.Namespace, profile: CLIProfile | None) -> RunOptions:
    canonical = HotpassConfig()
    profile_name = profile.name if profile else None

    if profile is not None:
        canonical = profile.apply_to_config(canonical)

    config_paths: list[Path] = []
    if profile is not None:
        config_paths.extend(profile.resolved_config_files())
        if profile.industry_profile:
            industry = load_industry_profile(profile.industry_profile)
            canonical = canonical.merge({"profile": industry.to_dict()})

    cli_config_paths = getattr(namespace, "config_paths", None)
    if cli_config_paths:
        config_paths.extend(Path(path) for path in cli_config_paths)

    for config_path in config_paths:
        if not config_path.exists():
            msg = f"Configuration file not found: {config_path}"
            raise FileNotFoundError(msg)
        payload = _normalise_config_payload(load_config(config_path))
        canonical = canonical.merge(payload)

    pipeline_updates: dict[str, Any] = {}
    automation_http_updates: dict[str, Any] = {}
    retry_updates: dict[str, Any] = {}
    circuit_updates: dict[str, Any] = {}
    telemetry_updates: dict[str, Any] = {}

    def _parse_bool(value: str) -> bool:
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        msg = "expected boolean value"
        raise ValueError(msg)

    def _parse_kv(values: Iterable[str], option: str) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for item in values:
            if "=" not in item:
                msg = f"{option} values must use KEY=VALUE syntax"
                raise ValueError(msg)
            key, value = item.split("=", 1)
            pairs[key.strip()] = value.strip()
        return pairs

    if namespace.input_dir is not None:
        pipeline_updates["input_dir"] = Path(namespace.input_dir)
    if namespace.output_path is not None:
        pipeline_updates["output_path"] = Path(namespace.output_path)
    if namespace.expectation_suite_name is not None:
        pipeline_updates["expectation_suite"] = namespace.expectation_suite_name
    if namespace.country_code is not None:
        pipeline_updates["country_code"] = namespace.country_code
    if namespace.dist_dir is not None:
        pipeline_updates["dist_dir"] = Path(namespace.dist_dir)
    if namespace.party_store_path is not None:
        pipeline_updates["party_store_path"] = Path(namespace.party_store_path)
    if getattr(namespace, "intent_digest_path", None) is not None:
        pipeline_updates["intent_digest_path"] = Path(namespace.intent_digest_path)
    if getattr(namespace, "intent_signal_store", None) is not None:
        pipeline_updates["intent_signal_store_path"] = Path(namespace.intent_signal_store)
    if getattr(namespace, "daily_list_path", None) is not None:
        pipeline_updates["daily_list_path"] = Path(namespace.daily_list_path)
    if getattr(namespace, "daily_list_size", None) is not None:
        pipeline_updates["daily_list_size"] = int(namespace.daily_list_size)
    if getattr(namespace, "intent_webhooks", None):
        pipeline_updates["intent_webhooks"] = [
            str(value) for value in namespace.intent_webhooks if value is not None
        ]
    if getattr(namespace, "crm_endpoint", None) is not None:
        pipeline_updates["crm_endpoint"] = namespace.crm_endpoint
    if getattr(namespace, "crm_token", None) is not None:
        pipeline_updates["crm_token"] = namespace.crm_token
    if getattr(namespace, "import_config_path", None) is not None:
        import_config_path = Path(namespace.import_config_path)
        if not import_config_path.exists():
            msg = f"Import configuration file not found: {import_config_path}"
            raise FileNotFoundError(msg)
        import_payload = load_config(import_config_path)
        mappings = import_payload.get("import_mappings") or import_payload.get("mappings") or []
        rules = import_payload.get("import_rules") or import_payload.get("rules") or []
        if mappings:
            pipeline_updates["import_mappings"] = list(mappings)
        if rules:
            pipeline_updates["import_rules"] = list(rules)
    if getattr(namespace, "automation_http_timeout", None) is not None:
        automation_http_updates["timeout"] = float(namespace.automation_http_timeout)
    if getattr(namespace, "automation_http_retries", None) is not None:
        retry_updates["attempts"] = int(namespace.automation_http_retries)
    if getattr(namespace, "automation_http_backoff", None) is not None:
        retry_updates["backoff_factor"] = float(namespace.automation_http_backoff)
    if getattr(namespace, "automation_http_backoff_max", None) is not None:
        retry_updates["backoff_max"] = float(namespace.automation_http_backoff_max)
    if getattr(namespace, "automation_http_circuit_threshold", None) is not None:
        circuit_updates["failure_threshold"] = int(namespace.automation_http_circuit_threshold)
    if getattr(namespace, "automation_http_circuit_reset", None) is not None:
        circuit_updates["recovery_time"] = float(namespace.automation_http_circuit_reset)
    if getattr(namespace, "automation_http_idempotency_header", None) is not None:
        automation_http_updates["idempotency_header"] = namespace.automation_http_idempotency_header
    if getattr(namespace, "automation_http_dead_letter", None) is not None:
        automation_http_updates["dead_letter_path"] = Path(namespace.automation_http_dead_letter)
    if getattr(namespace, "automation_http_dead_letter_enabled", None) is not None:
        automation_http_updates["dead_letter_enabled"] = bool(
            namespace.automation_http_dead_letter_enabled
        )
    if namespace.telemetry_service_name:
        telemetry_updates["service_name"] = namespace.telemetry_service_name
    if namespace.telemetry_environment:
        telemetry_updates["environment"] = namespace.telemetry_environment
    if namespace.telemetry_exporters:
        telemetry_updates["exporters"] = tuple(namespace.telemetry_exporters)
        telemetry_updates.setdefault("enabled", True)
    if namespace.telemetry_resource_attributes:
        telemetry_updates["resource_attributes"] = _parse_kv(
            namespace.telemetry_resource_attributes,
            "--telemetry-resource-attr",
        )
    if namespace.telemetry_otlp_headers:
        telemetry_updates["otlp_headers"] = _parse_kv(
            namespace.telemetry_otlp_headers,
            "--telemetry-otlp-header",
        )
    if namespace.telemetry_otlp_endpoint:
        telemetry_updates["otlp_endpoint"] = namespace.telemetry_otlp_endpoint
    if namespace.telemetry_otlp_metrics_endpoint:
        telemetry_updates["otlp_metrics_endpoint"] = namespace.telemetry_otlp_metrics_endpoint
    if namespace.telemetry_otlp_insecure is not None:
        telemetry_updates["otlp_insecure"] = bool(namespace.telemetry_otlp_insecure)
    if namespace.telemetry_otlp_timeout is not None:
        telemetry_updates["otlp_timeout"] = float(namespace.telemetry_otlp_timeout)

    if namespace.log_format is not None:
        pipeline_updates["log_format"] = namespace.log_format
    if namespace.report_path is not None:
        pipeline_updates["report_path"] = Path(namespace.report_path)
    if namespace.report_format is not None:
        pipeline_updates["report_format"] = namespace.report_format
    if getattr(namespace, "excel_chunk_size", None) is not None:
        pipeline_updates["excel_chunk_size"] = int(namespace.excel_chunk_size)
    if getattr(namespace, "excel_engine", None):
        pipeline_updates["excel_engine"] = namespace.excel_engine
    if getattr(namespace, "excel_stage_dir", None) is not None:
        pipeline_updates["excel_stage_dir"] = Path(namespace.excel_stage_dir)
    if getattr(namespace, "qa_mode", None) is not None:
        pipeline_updates["qa_mode"] = namespace.qa_mode
    if getattr(namespace, "observability", None) is not None:
        pipeline_updates["observability"] = bool(namespace.observability)
        telemetry_updates["enabled"] = bool(namespace.observability)
    if getattr(namespace, "archive", None) is not None:
        pipeline_updates["archive"] = bool(namespace.archive)

    if "timeout" not in automation_http_updates:
        env_timeout = os.getenv("HOTPASS_AUTOMATION_HTTP_TIMEOUT")
        if env_timeout is not None:
            try:
                automation_http_updates["timeout"] = float(env_timeout)
            except ValueError as exc:  # pragma: no cover
                raise ValueError("HOTPASS_AUTOMATION_HTTP_TIMEOUT must be numeric") from exc
    if "attempts" not in retry_updates:
        env_retries = os.getenv("HOTPASS_AUTOMATION_HTTP_RETRIES")
        if env_retries is not None:
            try:
                retry_updates["attempts"] = int(env_retries)
            except ValueError as exc:  # pragma: no cover
                raise ValueError("HOTPASS_AUTOMATION_HTTP_RETRIES must be an integer") from exc
    if "backoff_factor" not in retry_updates:
        env_backoff = os.getenv("HOTPASS_AUTOMATION_HTTP_BACKOFF")
        if env_backoff is not None:
            try:
                retry_updates["backoff_factor"] = float(env_backoff)
            except ValueError as exc:  # pragma: no cover
                raise ValueError("HOTPASS_AUTOMATION_HTTP_BACKOFF must be numeric") from exc
    if "backoff_max" not in retry_updates:
        env_backoff_max = os.getenv("HOTPASS_AUTOMATION_HTTP_BACKOFF_MAX")
        if env_backoff_max is not None:
            try:
                retry_updates["backoff_max"] = float(env_backoff_max)
            except ValueError as exc:  # pragma: no cover
                raise ValueError("HOTPASS_AUTOMATION_HTTP_BACKOFF_MAX must be numeric") from exc
    if "failure_threshold" not in circuit_updates:
        env_threshold = os.getenv("HOTPASS_AUTOMATION_HTTP_CIRCUIT_THRESHOLD")
        if env_threshold is not None:
            try:
                circuit_updates["failure_threshold"] = int(env_threshold)
            except ValueError as exc:  # pragma: no cover
                raise ValueError(
                    "HOTPASS_AUTOMATION_HTTP_CIRCUIT_THRESHOLD must be an integer"
                ) from exc
    if "recovery_time" not in circuit_updates:
        env_reset = os.getenv("HOTPASS_AUTOMATION_HTTP_CIRCUIT_RESET")
        if env_reset is not None:
            try:
                circuit_updates["recovery_time"] = float(env_reset)
            except ValueError as exc:  # pragma: no cover
                raise ValueError("HOTPASS_AUTOMATION_HTTP_CIRCUIT_RESET must be numeric") from exc
    if "idempotency_header" not in automation_http_updates:
        env_header = os.getenv("HOTPASS_AUTOMATION_HTTP_IDEMPOTENCY_HEADER")
        if env_header:
            automation_http_updates["idempotency_header"] = env_header
    if "dead_letter_path" not in automation_http_updates:
        env_dead_letter = os.getenv("HOTPASS_AUTOMATION_HTTP_DEAD_LETTER")
        if env_dead_letter:
            automation_http_updates["dead_letter_path"] = Path(env_dead_letter)
    if "dead_letter_enabled" not in automation_http_updates:
        env_dead_letter_enabled = os.getenv("HOTPASS_AUTOMATION_HTTP_DEAD_LETTER_ENABLED")
        if env_dead_letter_enabled is not None:
            try:
                automation_http_updates["dead_letter_enabled"] = _parse_bool(
                    env_dead_letter_enabled
                )
            except ValueError as exc:  # pragma: no cover
                raise ValueError(
                    "HOTPASS_AUTOMATION_HTTP_DEAD_LETTER_ENABLED must be a boolean"
                ) from exc

    if retry_updates:
        automation_http_updates["retry"] = retry_updates
    if circuit_updates:
        automation_http_updates["circuit_breaker"] = circuit_updates
    if automation_http_updates:
        pipeline_updates["automation_http"] = automation_http_updates

    updates: dict[str, Any] = {}
    if pipeline_updates:
        updates["pipeline"] = pipeline_updates
    if telemetry_updates:
        updates["telemetry"] = telemetry_updates

    if updates:
        canonical = canonical.merge(updates)

    sensitive_cli = getattr(namespace, "sensitive_fields", None)
    if sensitive_cli is not None:
        canonical = canonical.merge(
            {
                "pipeline": {
                    "sensitive_fields": [str(value) for value in sensitive_cli],
                }
            }
        )

    log_format = canonical.pipeline.log_format
    sensitive_fields = normalise_sensitive_fields(
        canonical.pipeline.sensitive_fields,
        DEFAULT_SENSITIVE_FIELD_TOKENS,
    )

    interactive = getattr(namespace, "interactive", None)
    if not isinstance(interactive, bool | type(None)):
        interactive = bool(interactive)

    report_path = canonical.pipeline.report_path
    report_format = canonical.pipeline.report_format or (
        infer_report_format(report_path) if report_path else None
    )
    party_store_path = canonical.pipeline.party_store_path

    return RunOptions(
        canonical_config=canonical,
        log_format=log_format,
        report_path=report_path,
        report_format=report_format,
        party_store_path=party_store_path,
        sensitive_fields=sensitive_fields,
        interactive=interactive,
        profile_name=profile_name,
    )


def _normalise_config_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade legacy flat payloads to canonical structure for merging."""

    upgraded: dict[str, Any] = dict(payload)
    pipeline_payload: dict[str, Any] = dict(upgraded.get("pipeline", {}))

    changed = False
    for key in list(upgraded.keys()):
        if key in LEGACY_PIPELINE_KEYS:
            pipeline_payload.setdefault(key, upgraded.pop(key))
            changed = True

    if changed:
        upgraded["pipeline"] = pipeline_payload

    return upgraded


__all__ = ["register", "build", "RunOptions"]
