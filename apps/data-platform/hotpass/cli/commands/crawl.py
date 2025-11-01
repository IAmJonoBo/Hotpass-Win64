"""Hotpass crawl command wrapping the adaptive research orchestrator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hotpass.config import IndustryProfile, get_default_profile, load_industry_profile
from hotpass.research import ResearchOrchestrator, ResearchOutcome
from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "crawl",
        help="Execute a targeted crawl via the research orchestrator",
        description="Run the Hotpass adaptive crawler against a query or URL.",
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "query_or_url",
        type=str,
        help="URL or free-text query to crawl",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Enable network access during the crawl (required for remote fetching)",
    )
    parser.add_argument(
        "--profile-name",
        type=str,
        help="Override the industry profile used during the crawl",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit crawl metadata as JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Persist crawl metadata to the given JSON path",
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="crawl",
        help="Execute a targeted crawl",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, cli_profile: CLIProfile | None) -> int:
    console = Console()
    orchestrator = ResearchOrchestrator()
    profile = _resolve_profile(namespace, cli_profile)

    outcome = orchestrator.crawl(
        profile=profile,
        query_or_url=namespace.query_or_url,
        allow_network=namespace.allow_network,
    )

    if namespace.json:
        payload = json.dumps(outcome.to_dict(), indent=2)
        if namespace.output:
            namespace.output.parent.mkdir(parents=True, exist_ok=True)
            namespace.output.write_text(payload, encoding="utf-8")
        console.print(payload)
    else:
        _render(console, outcome)
        if namespace.output:
            namespace.output.parent.mkdir(parents=True, exist_ok=True)
            namespace.output.write_text(json.dumps(outcome.to_dict(), indent=2), encoding="utf-8")
            console.print(f"[green]Crawl metadata written to[/green] {namespace.output}")

    return 0 if outcome.success else 2


def _resolve_profile(
    namespace: argparse.Namespace,
    cli_profile: CLIProfile | None,
) -> IndustryProfile:
    if namespace.profile_name:
        return load_industry_profile(namespace.profile_name)
    if cli_profile and cli_profile.industry_profile:
        return load_industry_profile(cli_profile.industry_profile)
    return get_default_profile("generic")


def _render(console: Console, outcome: ResearchOutcome) -> None:
    table = Table(title=f"Crawl Summary — {outcome.plan.entity_name}")
    table.add_column("Step", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Message", style="white")
    for step in outcome.steps:
        table.add_row(step.name, step.status.upper(), step.message)
    console.print(table)
    console.print(
        f"[dim]Allow network:[/dim] {outcome.plan.allow_network} · "
        f"[dim]Elapsed:[/dim] {outcome.elapsed_seconds:.2f}s"
    )
