from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console
from rich.table import Table

from ...inventory import InventoryService, InventorySummary, load_feature_requirements
from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "inventory",
        help="Inspect the asset inventory and implementation status",
        description=(
            "Display inventory assets sourced from data/inventory/asset-register.yaml and "
            "surface requirement status across backend, CLI, and frontend surfaces."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    subcommands = parser.add_subparsers(dest="inventory_command")

    list_parser = subcommands.add_parser(
        "list",
        help="List inventory assets with summary statistics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON payload instead of human-readable table.",
    )

    status_parser = subcommands.add_parser(
        "status",
        help="Show requirement status across backend/frontend/CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON payload instead of human-readable table.",
    )

    parser.set_defaults(inventory_command="list")
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="inventory",
        help="Inspect the asset inventory and implementation status",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile  # Profiles are unused for inventory operations.
    subcommand = getattr(namespace, "inventory_command", "list")
    service = InventoryService()

    if subcommand == "status":
        return _render_status(service, json_output=bool(getattr(namespace, "json", False)))

    # Default to list command
    return _render_assets(service, json_output=bool(getattr(namespace, "json", False)))


def _render_assets(service: InventoryService, *, json_output: bool) -> int:
    console = Console()
    try:
        manifest = service.load_manifest()
        summary = service.summary()
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    if json_output:
        payload = {
            "manifest": {
                "version": manifest.version,
                "maintainer": manifest.maintainer,
                "review_cadence": manifest.review_cadence,
            },
            "summary": _summary_dict(summary),
            "assets": [asset.model_dump(mode="json") for asset in manifest.assets],
        }
        console.print_json(json.dumps(payload))
        return 0

    table = Table(title="Asset inventory", header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="magenta")
    table.add_column("Classification", style="green")
    table.add_column("Owner", style="white")
    table.add_column("Custodian", style="white")
    table.add_column("Location", style="yellow")

    for asset in manifest.assets:
        table.add_row(
            asset.id,
            asset.name,
            asset.type,
            asset.classification,
            asset.owner,
            asset.custodian,
            asset.location,
        )

    console.print(
        f"[bold]Version:[/bold] {manifest.version}  "
        f"[bold]Maintainer:[/bold] {manifest.maintainer}  "
        f"[bold]Review cadence:[/bold] {manifest.review_cadence}"
    )
    type_summary = ", ".join(f"{name} ({count})" for name, count in summary.by_type.items())
    classification_summary = ", ".join(
        f"{name} ({count})" for name, count in summary.by_classification.items()
    )
    console.print(
        f"[bold]Total assets:[/bold] {summary.total_assets}  "
        f"[bold]Types:[/bold] {type_summary}  "
        f"[bold]Classifications:[/bold] {classification_summary}"
    )
    console.print(table)
    return 0


def _render_status(service: InventoryService, *, json_output: bool) -> int:
    console = Console()
    try:
        requirements = load_feature_requirements(service=service)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    if json_output:
        payload = {
            "requirements": [requirement.as_dict() for requirement in requirements],
        }
        console.print_json(json.dumps(payload))
        return 0

    table = Table(title="Inventory feature status", header_style="bold cyan")
    table.add_column("Surface", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Status", style="green")
    table.add_column("Detail", style="white")

    for requirement in requirements:
        table.add_row(
            requirement.surface,
            requirement.description,
            requirement.status.value,
            requirement.detail or "",
        )

    console.print(table)
    return 0


def _summary_dict(summary: InventorySummary) -> dict[str, Any]:
    return {
        "total_assets": summary.total_assets,
        "by_type": summary.by_type,
        "by_classification": summary.by_classification,
    }


__all__ = ["register"]
