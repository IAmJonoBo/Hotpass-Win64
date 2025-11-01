"""Implementation of the `hotpass orchestrate` subcommand."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from hotpass.error_handling import DataContractError
from hotpass.linkage import LabelStudioConfig, LinkageConfig, LinkageThresholds
from hotpass.orchestration import PipelineOrchestrationError, PipelineRunOptions, run_pipeline_once

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..progress import DEFAULT_SENSITIVE_FIELD_TOKENS, StructuredLogger
from ..shared import normalise_sensitive_fields
from .run import RunOptions
from .run import _resolve_options as resolve_run_options

FEATURE_FLAG_NAMES = (
    "entity_resolution",
    "geospatial",
    "enrichment",
    "compliance",
    "observability",
    "dashboards",
)


@dataclass(slots=True)
class OrchestrateOptions:
    run: RunOptions
    industry_profile_name: str
    features: dict[str, bool]
    linkage_match_threshold: float
    linkage_review_threshold: float
    linkage_output_dir: Path | None
    linkage_use_splink: bool
    label_studio_url: str | None
    label_studio_token: str | None
    label_studio_project: int | None


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "orchestrate",
        help="Run the pipeline with Prefect orchestration and optional enhanced features",
        description=(
            "Execute the Hotpass pipeline under Prefect with feature toggles for entity "
            "resolution, enrichment, compliance, and observability."
        ),
        parents=[shared.base, shared.pipeline, shared.excel],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--industry-profile",
        default="aviation",
        help="Prefect industry profile name used when loading orchestrator presets",
    )
    parser.add_argument(
        "--enable-all",
        action="store_true",
        help=(
            "Enable all enhanced features (entity resolution, geospatial, enrichment, "
            "compliance, observability)"
        ),
    )
    _add_feature_flag(parser, "entity_resolution", "Enable probabilistic entity resolution")
    _add_feature_flag(parser, "geospatial", "Enable geospatial enrichment (geocoding)")
    _add_feature_flag(parser, "enrichment", "Enable web enrichment workflows")
    _add_feature_flag(parser, "compliance", "Enable compliance tracking and PII detection")
    _add_feature_flag(
        parser,
        "observability",
        "Enable observability exporters for orchestrated runs",
        dest="feature_observability",
    )
    parser.add_argument(
        "--linkage-match-threshold",
        type=float,
        default=0.9,
        help="Probability threshold treated as an automatic match",
    )
    parser.add_argument(
        "--linkage-review-threshold",
        type=float,
        default=0.7,
        help="Probability threshold that routes pairs to human review",
    )
    parser.add_argument(
        "--linkage-output-dir",
        type=Path,
        help="Directory for persisted linkage artefacts",
    )
    parser.add_argument(
        "--linkage-use-splink",
        action="store_true",
        help="Use Splink for probabilistic linkage (default: rule-based)",
    )
    parser.add_argument("--label-studio-url", help="Label Studio base URL for review tasks")
    parser.add_argument("--label-studio-token", help="Label Studio API token for task submission")
    parser.add_argument(
        "--label-studio-project",
        type=int,
        help="Label Studio project identifier",
    )
    parser.set_defaults(
        entity_resolution=None,
        geospatial=None,
        enrichment=None,
        compliance=None,
        feature_observability=None,
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="orchestrate",
        help="Run the pipeline with Prefect orchestration",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    options = _resolve_orchestrate_options(namespace, profile)
    logger = StructuredLogger(options.run.log_format, options.run.sensitive_fields)
    console = logger.console if options.run.log_format == "rich" else None

    canonical = options.run.canonical_config
    pipeline_runtime = canonical.pipeline

    if console:
        console.print("[bold cyan]Hotpass Prefect Orchestration[/bold cyan]")
        console.print(f"[dim]Industry profile:[/dim] {options.industry_profile_name}")
        console.print(f"[dim]Input directory:[/dim] {pipeline_runtime.input_dir}")
        console.print(f"[dim]Output path:[/dim] {pipeline_runtime.output_path}")
        enabled = [feature for feature, value in options.features.items() if value]
        if enabled:
            console.print(f"[dim]Enabled features:[/dim] {', '.join(sorted(enabled))}")
        console.print()

    runner: Callable[..., Any] | None = None
    runner_kwargs: dict[str, Any] | None = None

    if any(
        options.features.get(name, False)
        for name in (
            "entity_resolution",
            "geospatial",
            "enrichment",
            "compliance",
            "observability",
        )
    ):
        try:
            from hotpass.pipeline.features.config import EnhancedPipelineConfig
            from hotpass.pipeline_enhanced import run_enhanced_pipeline as enhanced_runner
        except Exception:  # pragma: no cover - guard when extras unavailable
            logger.log_error(
                "Enhanced pipeline extras are not installed. Install with: "
                "uv sync --extra enrichment --extra compliance --extra geospatial"
            )
            return 1

        linkage_config = _build_linkage_config(options)
        enhanced_config = EnhancedPipelineConfig(
            enable_entity_resolution=options.features.get("entity_resolution", False),
            enable_geospatial=options.features.get("geospatial", False),
            enable_enrichment=options.features.get("enrichment", False),
            enable_compliance=options.features.get("compliance", False),
            enable_observability=options.features.get("observability", False),
            geocode_addresses=options.features.get("geospatial", False),
            enrich_websites=options.features.get("enrichment", False),
            detect_pii=options.features.get("compliance", False),
            entity_resolution_threshold=options.linkage_review_threshold,
            use_splink=options.linkage_use_splink
            or options.features.get("entity_resolution", False),
            linkage_config=linkage_config,
            linkage_output_dir=(
                str(options.linkage_output_dir) if options.linkage_output_dir else None
            ),
            linkage_match_threshold=options.linkage_match_threshold,
        )
        runner = cast(Callable[..., Any], enhanced_runner)
        runner_kwargs = {"enhanced_config": enhanced_config}

    try:
        summary = run_pipeline_once(
            PipelineRunOptions(
                config=canonical,
                profile_name=options.industry_profile_name,
                runner=runner,
                runner_kwargs=runner_kwargs,
                telemetry_context={"hotpass.command": "hotpass orchestrate"},
            )
        )
    except DataContractError as exc:
        logger.log_error(f"Data contract validation failed: {exc.context.message}")
        if console:
            console.print("[bold red]✗ Data contract validation failed[/bold red]")
            console.print(f"[dim]Source:[/dim] {exc.context.source_file or 'unknown'}")
            console.print(f"[dim]Details:[/dim] {exc.context.details}")
            if exc.context.suggested_fix:
                console.print(f"[yellow]Suggested fix:[/yellow] {exc.context.suggested_fix}")
        return 2
    except PipelineOrchestrationError as exc:
        logger.log_error(f"Pipeline failed: {exc}")
        return 1

    payload = summary.to_payload()
    logger.log_event("orchestrate.summary", payload)

    if console:
        if summary.success:
            console.print("[bold green]✓[/bold green] Pipeline completed successfully!")
        else:
            console.print(
                "[bold yellow]⚠[/bold yellow] Pipeline completed with validation warnings"
            )
        console.print(f"  Records processed: {summary.total_records}")
        console.print(f"  Duration: {summary.elapsed_seconds:.2f}s")
        if summary.archive_path:
            console.print(f"  Archive: {summary.archive_path}")

    if summary.archive_path:
        logger.log_archive(Path(summary.archive_path))

    return 0 if summary.success else 1


def _resolve_orchestrate_options(
    namespace: argparse.Namespace, profile: CLIProfile | None
) -> OrchestrateOptions:
    run_options = resolve_run_options(namespace, profile)
    config = run_options.canonical_config

    industry_profile_name = namespace.industry_profile
    if profile and profile.industry_profile:
        industry_profile_name = profile.industry_profile
    if not industry_profile_name:
        industry_profile_name = "aviation"

    base_features = config.features.model_dump()
    features = {name: bool(base_features.get(name, False)) for name in FEATURE_FLAG_NAMES}
    if config.pipeline.observability is not None:
        features["observability"] = bool(config.pipeline.observability)
    if profile:
        features.update(profile.feature_payload())

    if getattr(namespace, "enable_all", False):
        for name in features:
            features[name] = True

    override_map = {
        "entity_resolution": namespace.entity_resolution,
        "geospatial": namespace.geospatial,
        "enrichment": namespace.enrichment,
        "compliance": namespace.compliance,
        "observability": getattr(namespace, "feature_observability", None),
    }
    for name, override in override_map.items():
        if override is not None:
            features[name] = bool(override)

    sensitive_field_values = getattr(namespace, "sensitive_fields", None)
    if sensitive_field_values is None and profile is not None:
        sensitive_field_values = profile.options.get("sensitive_fields")
    sensitive_field_iter: Iterable[str] | None = None
    if isinstance(sensitive_field_values, str):
        sensitive_field_iter = [sensitive_field_values]
    elif isinstance(sensitive_field_values, Iterable):
        sensitive_field_iter = [str(value) for value in sensitive_field_values if value is not None]
    elif sensitive_field_values is not None:
        sensitive_field_iter = [str(sensitive_field_values)]
    run_sensitive_fields = normalise_sensitive_fields(
        sensitive_field_iter, DEFAULT_SENSITIVE_FIELD_TOKENS
    )
    updated_config = config.merge({"features": features})
    if features.get("observability") is not None:
        updated_config = updated_config.merge(
            {"pipeline": {"observability": bool(features["observability"])}}
        )
    run_options = replace(
        run_options,
        canonical_config=updated_config,
        sensitive_fields=run_sensitive_fields,
    )

    linkage_output_dir = (
        Path(namespace.linkage_output_dir) if namespace.linkage_output_dir else None
    )

    return OrchestrateOptions(
        run=run_options,
        industry_profile_name=industry_profile_name,
        features=features,
        linkage_match_threshold=float(namespace.linkage_match_threshold or 0.9),
        linkage_review_threshold=float(namespace.linkage_review_threshold or 0.7),
        linkage_output_dir=linkage_output_dir,
        linkage_use_splink=bool(namespace.linkage_use_splink),
        label_studio_url=namespace.label_studio_url,
        label_studio_token=namespace.label_studio_token,
        label_studio_project=namespace.label_studio_project,
    )


def _build_linkage_config(options: OrchestrateOptions) -> LinkageConfig | None:
    thresholds = LinkageThresholds(
        high=max(options.linkage_match_threshold, options.linkage_review_threshold),
        review=options.linkage_review_threshold,
    )

    label_studio = None
    if options.label_studio_url and options.label_studio_token and options.label_studio_project:
        label_studio = LabelStudioConfig(
            api_url=options.label_studio_url,
            api_token=options.label_studio_token,
            project_id=options.label_studio_project,
        )

    if not options.features.get("entity_resolution", False):
        return LinkageConfig(
            use_splink=False,
            thresholds=thresholds,
            label_studio=label_studio,
        )

    output_root = options.linkage_output_dir
    if output_root is None:
        output_root = options.run.canonical_config.pipeline.output_path.parent / "linkage"

    return LinkageConfig(
        use_splink=options.linkage_use_splink or options.features.get("entity_resolution", False),
        thresholds=thresholds,
        label_studio=label_studio,
    ).with_output_root(output_root.resolve())


def _add_feature_flag(
    parser: argparse.ArgumentParser,
    feature_name: str,
    help_text: str,
    *,
    dest: str | None = None,
) -> None:
    dest_name = dest or feature_name
    parser.add_argument(
        f"--enable-{feature_name.replace('_', '-')}",
        dest=dest_name,
        action="store_true",
        help=help_text,
    )
    parser.add_argument(
        f"--disable-{feature_name.replace('_', '-')}",
        dest=dest_name,
        action="store_false",
        help=f"Disable {help_text.lower()}",
    )


__all__ = ["register", "build"]
