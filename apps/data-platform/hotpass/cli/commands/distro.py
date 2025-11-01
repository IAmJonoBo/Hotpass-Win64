"""Distribution helper commands."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import cast

from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, CommandHandler, SharedParsers
from ..configuration import CLIProfile

DOC_SOURCES = [
    Path("README.md"),
    Path("AGENTS.md"),
    Path("docs/reference/cli.md"),
]


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "distro",
        help="Create distribution-ready artefacts",
        description="Package documentation and helper files alongside built wheels.",
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    distro_subparsers = parser.add_subparsers(dest="distro_command")

    docs_parser = distro_subparsers.add_parser(
        "docs",
        help="Collect CLI and onboarding docs into a single directory",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    docs_parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/docs"),
        help="Directory to write collated docs to",
    )
    docs_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output directory if it exists",
    )
    docs_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the files that would be copied without writing them",
    )
    docs_parser.set_defaults(handler=_handle_docs)

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="distro",
        help="Create distribution companion artefacts",
        builder=build,
        handler=_dispatch,
    )


def _dispatch(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    raw_handler = getattr(namespace, "handler", None)
    if not callable(raw_handler):
        Console().print("[red]No distro subcommand specified (use 'hotpass distro --help').[/red]")
        return 1
    handler = cast(CommandHandler, raw_handler)
    result = handler(namespace, profile)
    return int(result)


def _handle_docs(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    sources = [path for path in DOC_SOURCES if path.exists()]
    if not sources:
        console.print("[red]No documentation files found to package.[/red]")
        return 1

    if args.dry_run:
        table = Table("Source", "Destination")
        for src in sources:
            table.add_row(str(src), str(args.output / src.name))
        console.print(table)
        console.print("[yellow]Dry-run complete; docs not copied.[/yellow]")
        return 0

    output_dir: Path = args.output
    if output_dir.exists():
        if not args.force:
            console.print(
                f"[red]Output directory {output_dir} already exists. Use --force "
                "to overwrite.[/red]"
            )
            return 1
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for src in sources:
        shutil.copy2(src, output_dir / src.name)
    console.print(f"[green]Copied {len(sources)} documentation files to {output_dir}[/green]")
    return 0
