"""Enrich command - enrich refined data with additional information."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console

from hotpass.config import load_industry_profile

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    """Build the enrich command parser."""
    parser = subparsers.add_parser(
        "enrich",
        help="Enrich refined data with additional information",
        description=(
            "Enrich refined data with additional information from deterministic sources "
            "and optionally from network-based research. Always tries offline/deterministic "
            "enrichment first, then network-based if enabled."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input/Output options
    io_group = parser.add_argument_group("Input/Output")
    io_group.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the refined input file (XLSX)",
    )
    io_group.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path for the enriched output file",
    )

    # Enrichment options
    enrich_group = parser.add_argument_group("Enrichment")
    enrich_group.add_argument(
        "--allow-network",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=None,
        help=(
            "Allow network-based enrichment (true/false). "
            "Defaults to ALLOW_NETWORK_RESEARCH env var, or false if not set."
        ),
    )
    enrich_group.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for enrichment (0.0-1.0)",
    )

    # Output options
    output_group = parser.add_argument_group("Output")
    output_group.add_argument(
        "--provenance",
        action="store_true",
        default=True,
        help="Include provenance metadata in output (default: true)",
    )

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="enrich",
        help="Enrich refined data with additional information",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    """Handle the enrich command execution."""
    console = Console()

    # Get profile name from CLI profile or namespace
    profile_name = "generic"
    if profile:
        profile_name = profile.industry_profile or "generic"

    # Validate inputs
    input_path = Path(namespace.input)
    if not input_path.exists():
        console.print(f"[red]Error:[/red] Input file not found: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(namespace.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine network permission
    allow_network = namespace.allow_network
    if allow_network is None:
        # Check environment variables
        feature_enabled = os.getenv("FEATURE_ENABLE_REMOTE_RESEARCH", "0") == "1"
        runtime_allowed = os.getenv("ALLOW_NETWORK_RESEARCH", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        allow_network = feature_enabled and runtime_allowed

    # Load profile
    try:
        industry_profile = load_industry_profile(profile_name)
        console.print(f"[cyan]Loaded profile:[/cyan] {industry_profile.display_name}")
    except Exception as e:
        console.print(f"[red]Error loading profile:[/red] {e}", file=sys.stderr)
        return 1

    # Display enrichment configuration
    console.print(f"[cyan]Input:[/cyan] {input_path}")
    console.print(f"[cyan]Output:[/cyan] {output_path}")
    network_status = "enabled" if allow_network else "disabled (deterministic only)"
    console.print(f"[cyan]Network enrichment:[/cyan] {network_status}")
    console.print(f"[cyan]Confidence threshold:[/cyan] {namespace.confidence_threshold}")

    # Import enrichment pipeline (lazy import to avoid circular dependencies)
    try:
        from hotpass.enrichment.pipeline import enrich_data
        from hotpass.enrichment.provenance import ProvenanceTracker
    except ImportError:
        console.print(
            "[yellow]Warning:[/yellow] Enrichment pipeline not fully implemented yet. "
            "This is a placeholder that will be completed in Sprint 2.",
            file=sys.stderr,
        )
        # For now, create a stub output
        import pandas as pd

        df = pd.read_excel(input_path)

        # Add provenance columns
        df["provenance_source"] = "deterministic"
        df["provenance_timestamp"] = pd.Timestamp.now().isoformat()
        df["provenance_confidence"] = 1.0
        df["provenance_strategy"] = "offline-first"

        if not allow_network:
            df["provenance_network_status"] = "skipped: network disabled"

        df.to_excel(output_path, index=False)
        console.print(f"[green]✓[/green] Enriched data written to {output_path}")
        console.print("[yellow]Note:[/yellow] Full enrichment pipeline coming in Sprint 2")
        return 0

    # Run enrichment pipeline
    try:
        tracker = ProvenanceTracker()
        enriched_df = enrich_data(
            input_path=input_path,
            profile=industry_profile,
            allow_network=allow_network,
            confidence_threshold=namespace.confidence_threshold,
            provenance_tracker=tracker,
        )

        # Write output
        if namespace.provenance:
            enriched_df = tracker.add_provenance_columns(enriched_df)

        enriched_df.to_excel(output_path, index=False)

        console.print(f"[green]✓[/green] Enriched {len(enriched_df)} rows")
        console.print(f"[green]✓[/green] Output written to {output_path}")

        # Display enrichment summary
        if namespace.provenance and "provenance_source" in enriched_df.columns:
            source_counts = enriched_df["provenance_source"].value_counts()
            console.print("\n[cyan]Enrichment sources:[/cyan]")
            for source, count in source_counts.items():
                console.print(f"  {source}: {count}")

        return 0

    except Exception as e:
        console.print(f"[red]Error during enrichment:[/red] {e}", file=sys.stderr)
        structured_logs = getattr(namespace, "structured_logs", False)
        if structured_logs:
            import traceback

            console.print(traceback.format_exc(), file=sys.stderr)
        return 1
