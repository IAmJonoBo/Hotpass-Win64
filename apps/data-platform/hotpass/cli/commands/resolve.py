"""Implementation of the `hotpass resolve` subcommand."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from hotpass.linkage import LabelStudioConfig, LinkageConfig, LinkageThresholds, link_entities

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..progress import DEFAULT_SENSITIVE_FIELD_TOKENS, StructuredLogger
from ..shared import normalise_sensitive_fields


@dataclass(slots=True)
class ResolveOptions:
    input_file: Path
    output_file: Path
    threshold: float
    use_splink: bool
    match_threshold: float
    review_threshold: float
    label_studio_url: str | None
    label_studio_token: str | None
    label_studio_project: int | None
    log_format: str
    sensitive_fields: tuple[str, ...]


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "resolve",
        help="Run entity resolution on existing datasets",
        description=(
            "Deduplicate records using rule-based or probabilistic linkage with optional "
            "Label Studio review queues."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Input Excel/CSV file with potential duplicates",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        required=True,
        help="Output file for deduplicated data",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Match probability threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--use-splink",
        dest="use_splink",
        action="store_true",
        help="Use Splink for probabilistic matching",
    )
    parser.add_argument(
        "--no-use-splink",
        dest="use_splink",
        action="store_false",
        help="Disable Splink even when the active profile enables probabilistic linkage",
    )
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=0.9,
        help="Probability considered a confirmed match",
    )
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=0.7,
        help="Probability routed to Label Studio review",
    )
    parser.add_argument("--label-studio-url", help="Label Studio base URL for review tasks")
    parser.add_argument("--label-studio-token", help="Label Studio API token")
    parser.add_argument("--label-studio-project", type=int, help="Label Studio project identifier")
    parser.set_defaults(use_splink=None)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="resolve",
        help="Run entity resolution on exported datasets",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    options = _resolve_options(namespace, profile)
    logger = StructuredLogger(options.log_format, options.sensitive_fields)
    console = logger.console if options.log_format == "rich" else None

    if not options.input_file.exists():
        logger.log_error(f"Input file not found: {options.input_file}")
        return 1

    try:
        if options.input_file.suffix.lower() == ".csv":
            df = pd.read_csv(options.input_file)
        else:
            df = pd.read_excel(options.input_file)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.log_error(f"Unable to read {options.input_file}: {exc}")
        return 1

    if df.empty:
        logger.log_error("Input dataset is empty")
        return 1

    if console:
        console.print("[bold cyan]Running entity resolution...[/bold cyan]")
        console.print(f"[dim]Records loaded:[/dim] {len(df)}")

    thresholds = LinkageThresholds(high=options.match_threshold, review=options.review_threshold)
    label_studio_config = _build_label_studio(options)
    linkage_config = LinkageConfig(
        use_splink=options.use_splink,
        thresholds=thresholds,
        label_studio=label_studio_config,
    ).with_output_root(options.output_file.parent / "linkage")

    try:
        linkage_result = link_entities(df, linkage_config)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.log_error(f"Entity resolution failed: {exc}")
        return 1

    deduplicated = linkage_result.deduplicated
    matches = linkage_result.matches

    try:
        if options.output_file.suffix.lower() == ".csv":
            deduplicated.to_csv(options.output_file, index=False)
        else:
            deduplicated.to_excel(options.output_file, index=False, engine="openpyxl")
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.log_error(f"Failed to write output: {exc}")
        return 1

    removed = len(df) - len(deduplicated)
    review_count = len(linkage_result.review_queue)
    payload = {
        "input_records": len(df),
        "deduplicated_records": len(deduplicated),
        "duplicates_removed": removed,
        "high_confidence_matches": int((matches["classification"] == "match").sum()),
        "review_pairs": review_count,
        "review_path": str(linkage_config.persistence.review_path()),
        "output_path": str(options.output_file),
    }
    logger.log_event("resolve.summary", payload)

    if console:
        console.print("[bold green]✓[/bold green] Entity resolution complete!")
        console.print(f"  Deduplicated records: {len(deduplicated)}")
        console.print(f"  Duplicates removed: {removed}")
        console.print(f"  Review queue: {review_count} pairs written to {payload['review_path']}")

    return 0


def _resolve_options(namespace: argparse.Namespace, profile: CLIProfile | None) -> ResolveOptions:
    log_format_value: str | None = getattr(namespace, "log_format", None)
    if log_format_value is None and profile is not None:
        log_format_value = profile.log_format
    log_format = (log_format_value or "rich").lower()
    if log_format not in {"json", "rich"}:
        msg = f"Unsupported log format: {log_format}"
        raise ValueError(msg)

    raw_sensitive = getattr(namespace, "sensitive_fields", None)
    if raw_sensitive is None and profile is not None:
        raw_sensitive = profile.options.get("sensitive_fields")
    sensitive_iter: Iterable[str] | None = None
    if isinstance(raw_sensitive, str):
        sensitive_iter = [raw_sensitive]
    elif isinstance(raw_sensitive, Iterable):
        sensitive_iter = [str(value) for value in raw_sensitive if value is not None]
    elif raw_sensitive is not None:
        sensitive_iter = [str(raw_sensitive)]
    sensitive_fields = normalise_sensitive_fields(sensitive_iter, DEFAULT_SENSITIVE_FIELD_TOKENS)

    use_splink = namespace.use_splink
    if profile and profile.features.entity_resolution and use_splink is None:
        use_splink = True

    return ResolveOptions(
        input_file=Path(namespace.input_file),
        output_file=Path(namespace.output_file),
        threshold=float(namespace.threshold),
        use_splink=bool(use_splink),
        match_threshold=float(
            namespace.match_threshold
            if namespace.match_threshold is not None
            else namespace.threshold
        ),
        review_threshold=float(
            namespace.review_threshold
            if namespace.review_threshold is not None
            else namespace.threshold
        ),
        label_studio_url=namespace.label_studio_url,
        label_studio_token=namespace.label_studio_token,
        label_studio_project=namespace.label_studio_project,
        log_format=log_format,
        sensitive_fields=sensitive_fields,
    )


def _build_label_studio(options: ResolveOptions) -> LabelStudioConfig | None:
    if not (
        options.label_studio_url and options.label_studio_token and options.label_studio_project
    ):
        return None
    return LabelStudioConfig(
        api_url=options.label_studio_url,
        api_token=options.label_studio_token,
        project_id=options.label_studio_project,
    )


__all__ = ["register", "build"]
