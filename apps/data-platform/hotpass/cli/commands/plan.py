"""Plan-oriented CLI commands (e.g., adaptive research planning)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from hotpass.config import IndustryProfile, get_default_profile, load_industry_profile
from hotpass.research import ResearchContext, ResearchOrchestrator, ResearchOutcome
from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile

PlanHandler = Callable[[argparse.Namespace, CLIProfile | None], int]


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "plan",
        help="Plan adaptive research tasks and supporting workflows",
        description=(
            "Coordinate adaptive research plans before executing enrichment and crawl passes."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.set_defaults(handler=_dispatch_plan, plan_parser=parser)

    plan_subparsers = parser.add_subparsers(dest="plan_command")
    research_parser = plan_subparsers.add_parser(
        "research",
        help="Plan deterministic and network research for a specific entity",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    research_parser.add_argument(
        "--dataset",
        type=Path,
        help="Dataset (Excel/CSV) containing the entity to research",
    )
    research_parser.add_argument(
        "--row-id",
        type=str,
        help="Row index or identifier to select from the dataset",
    )
    research_parser.add_argument(
        "--entity",
        type=str,
        help="Entity name to look up when row-id is not supplied",
    )
    research_parser.add_argument(
        "--query",
        type=str,
        help="Optional free-text query to seed research searches",
    )
    research_parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Target URL to crawl (may be repeated)",
    )
    research_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Enable network-based enrichment during the research pass",
    )
    research_parser.add_argument(
        "--profile-name",
        type=str,
        help="Override the industry profile used for research orchestration",
    )
    research_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit plan output as JSON",
    )
    research_parser.add_argument(
        "--output",
        type=Path,
        help="Persist plan output to the given JSON path",
    )
    research_parser.set_defaults(plan_handler=_handle_research_plan)

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="plan",
        help="Plan adaptive research tasks",
        builder=build,
        handler=_dispatch_plan,
    )


def _dispatch_plan(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    handler: PlanHandler | None = getattr(namespace, "plan_handler", None)
    if handler is None:
        plan_parser: argparse.ArgumentParser | None = getattr(namespace, "plan_parser", None)
        if plan_parser is not None:
            plan_parser.print_help()
        return 1
    return handler(namespace, profile)


def _handle_research_plan(namespace: argparse.Namespace, cli_profile: CLIProfile | None) -> int:
    console = Console()
    industry_profile = _resolve_industry_profile(namespace, cli_profile)

    try:
        row = _load_row(namespace.dataset, namespace.row_id, namespace.entity)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    context = ResearchContext(
        profile=industry_profile,
        row=row,
        entity_name=namespace.entity,
        query=namespace.query,
        urls=namespace.url,
        allow_network=namespace.allow_network,
    )
    orchestrator = ResearchOrchestrator()
    outcome = orchestrator.plan(context)

    if namespace.json:
        payload = outcome.to_dict()
        output = json.dumps(payload, indent=2)
        if namespace.output:
            namespace.output.parent.mkdir(parents=True, exist_ok=True)
            namespace.output.write_text(output, encoding="utf-8")
        console.print(output)
    else:
        _render_outcome(console, outcome, namespace.output)

    return 0 if outcome.success else 2


def _resolve_industry_profile(
    namespace: argparse.Namespace,
    cli_profile: CLIProfile | None,
) -> IndustryProfile:
    profile_name = namespace.profile_name
    if profile_name:
        return load_industry_profile(profile_name)
    if cli_profile and cli_profile.industry_profile:
        return load_industry_profile(cli_profile.industry_profile)
    return get_default_profile("generic")


def _load_row(
    dataset: Path | None,
    row_identifier: str | None,
    entity: str | None,
) -> pd.Series | None:
    if dataset is None:
        return None
    if not dataset.exists():
        raise ValueError(f"Dataset not found: {dataset}")

    if dataset.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        frame = pd.read_excel(dataset)
    else:
        frame = pd.read_csv(dataset)

    if frame.empty:
        raise ValueError(f"Dataset {dataset} has no rows to plan against")

    if row_identifier is not None:
        try:
            index = int(row_identifier)
            return frame.iloc[index]
        except (ValueError, IndexError):
            pass

        if row_identifier in frame.get("id", []):
            match = frame[frame["id"] == row_identifier]
            if not match.empty:
                return match.iloc[0]

    if entity:
        mask = frame["organization_name"].astype(str).str.casefold() == entity.casefold()
        match = frame[mask]
        if not match.empty:
            return match.iloc[0]

    if row_identifier is not None:
        raise ValueError(f"Unable to locate row '{row_identifier}' in {dataset}")
    if entity is not None:
        raise ValueError(f"Unable to locate entity '{entity}' in {dataset}")
    return frame.iloc[0]


def _render_outcome(
    console: Console,
    outcome: ResearchOutcome,
    output_path: Path | None,
) -> None:
    table = Table(title=f"Adaptive Research Plan — {outcome.plan.entity_name}")
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

    if output_path:
        payload = outcome.to_dict()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]Plan written to[/green] {output_path}")
