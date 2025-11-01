"""Implementation of the `hotpass version` subcommand for data versioning."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from hotpass.versioning import DatasetVersion, DVCManager
from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile

console = Console()


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    """Build the version subcommand parser.

    Args:
        subparsers: Subparser collection to register with
        shared: Shared parsers (unused for this command)

    Returns:
        Configured argument parser
    """
    parser = subparsers.add_parser(
        "version",
        help="Manage dataset versions with DVC",
        description="Initialize DVC, track datasets, and manage semantic versions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize DVC in the repository",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show DVC status and tracked datasets",
    )

    parser.add_argument(
        "--add",
        type=Path,
        metavar="PATH",
        help="Add a path to DVC tracking",
    )

    parser.add_argument(
        "--get",
        metavar="DATASET",
        help="Get the current version for a dataset (default: refined_data)",
    )

    parser.add_argument(
        "--set",
        metavar="VERSION",
        help="Set version (e.g., 1.2.3)",
    )

    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Bump version component",
    )

    parser.add_argument(
        "--tag",
        action="store_true",
        help="Create a git tag for the current version",
    )

    parser.add_argument(
        "--dataset",
        default="refined_data",
        help="Dataset name for version operations",
    )

    parser.add_argument(
        "--description",
        help="Version description",
    )

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root directory",
    )

    return parser


def register() -> CLICommand:
    """Register the version command.

    Returns:
        CLICommand configuration
    """
    return CLICommand(
        name="version",
        help="Manage dataset versions with DVC",
        builder=build,
        handler=_command_handler,
        is_default=False,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    """Handle the version command.

    Args:
        namespace: Parsed command-line arguments
        profile: CLI profile (unused for this command)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    manager = DVCManager(namespace.repo_root)

    if namespace.init:
        console.print("[bold blue]Initializing DVC...[/bold blue]")
        if manager.initialize():
            console.print("[bold green]✓[/bold green] DVC initialized successfully")
            console.print("\n[dim]Configure a remote with: dvc remote add ...[/dim]")
            return 0
        else:
            console.print("[bold red]✗[/bold red] Failed to initialize DVC")
            return 1

    if namespace.status:
        console.print("[bold blue]DVC Status[/bold blue]")
        status = manager.status()

        if not status["initialized"]:
            console.print("[yellow]DVC not initialized. Run: hotpass version --init[/yellow]")
            return 1

        if status.get("error"):
            console.print(f"[red]Error: {status['error']}[/red]")
            return 1

        console.print(status.get("status_output", ""))

        if status.get("has_changes"):
            console.print("\n[yellow]Tracked files have changes[/yellow]")
        else:
            console.print("\n[green]All tracked files are up to date[/green]")

        return 0

    if namespace.add:
        if not manager.is_initialized():
            console.print("[red]DVC not initialized. Run: hotpass version --init[/red]")
            return 1

        console.print(f"[bold blue]Adding {namespace.add} to DVC...[/bold blue]")
        if manager.add_path(namespace.add):
            console.print(f"[bold green]✓[/bold green] {namespace.add} added to DVC tracking")
            console.print(f"\n[dim]Commit the .dvc file: git add {namespace.add}.dvc[/dim]")
            return 0
        else:
            console.print(f"[bold red]✗[/bold red] Failed to add {namespace.add}")
            return 1

    if namespace.get:
        dataset_name = namespace.get
        version = manager.get_version(dataset_name)

        table = Table(title=f"Version for {dataset_name}")
        table.add_column("Component", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Semantic Version", version.semver)
        table.add_row("Timestamp", version.timestamp)
        if version.checksum:
            table.add_row("Checksum", version.checksum)
        if version.description:
            table.add_row("Description", version.description)

        console.print(table)
        return 0

    if namespace.set:
        try:
            parts = namespace.set.split(".")
            if len(parts) != 3:
                console.print("[red]Version must be in format: major.minor.patch[/red]")
                return 1

            major, minor, patch = map(int, parts)
            version = DatasetVersion(
                major=major,
                minor=minor,
                patch=patch,
                timestamp=datetime.now(UTC).isoformat(),
                description=namespace.description,
            )

            if manager.set_version(version, namespace.dataset):
                console.print(
                    f"[bold green]✓[/bold green] Set version {version.semver} "
                    f"for {namespace.dataset}"
                )

                if namespace.tag:
                    if manager.tag_version(version, namespace.dataset):
                        console.print(
                            f"[bold green]✓[/bold green] Created tag "
                            f"{namespace.dataset}-v{version.semver}"
                        )
                    else:
                        console.print("[yellow]Warning: Failed to create git tag[/yellow]")

                return 0
            else:
                console.print("[bold red]✗[/bold red] Failed to set version")
                return 1

        except ValueError:
            console.print("[red]Invalid version format. Use: major.minor.patch[/red]")
            return 1

    if namespace.bump:
        current_version = manager.get_version(namespace.dataset)
        new_version = current_version.bump(namespace.bump)

        if namespace.description:
            new_version.description = namespace.description

        if manager.set_version(new_version, namespace.dataset):
            console.print(
                f"[bold green]✓[/bold green] Bumped {namespace.bump}: "
                f"{current_version.semver} → {new_version.semver}"
            )

            if namespace.tag:
                if manager.tag_version(new_version, namespace.dataset):
                    console.print(
                        f"[bold green]✓[/bold green] Created tag "
                        f"{namespace.dataset}-v{new_version.semver}"
                    )
                else:
                    console.print("[yellow]Warning: Failed to create git tag[/yellow]")

            return 0
        else:
            console.print("[bold red]✗[/bold red] Failed to bump version")
            return 1

    console.print("[yellow]No action specified. Use --help for usage.[/yellow]")
    return 1


__all__ = ["build", "register"]
