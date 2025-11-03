"""Operator-friendly wrapper around core Hotpass automation."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess  # nosec B404 - CLI requires subprocess invocations
from collections.abc import Iterable, Sequence
from typing import Protocol, cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

DEFAULT_TUNNEL_HOST = os.environ.get("HOTPASS_BASTION_HOST", "bastion.example.com")
DEFAULT_TUNNEL_VIA = os.environ.get("HOTPASS_TUNNEL_VIA", "ssh-bastion")
DEFAULT_SETUP_PRESET = "staging"
DEFAULT_ENV_TARGET = "staging"


class _CommandHandler(Protocol):
    def __call__(self, args: argparse.Namespace, console: Console) -> int: ...


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    console = Console()
    handler = cast(_CommandHandler | None, getattr(args, "handler", None))
    if handler is None:
        parser.print_help()
        return 1
    try:
        return handler(args, console)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        return 130
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotpass-operator",
        description="Guided CLI for Hotpass operators (credentials, tunnels, pipelines).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without executing them.",
    )
    parser.add_argument(
        "--assume-yes",
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Accept defaults for confirmation prompts.",
    )
    subparsers = parser.add_subparsers(dest="command")

    wizard = subparsers.add_parser(
        "wizard",
        help="Opinionated bootstrap: credentials → setup → env file.",
        description="Guide operators through the minimum viable setup for Hotpass.",
    )
    wizard.add_argument(
        "--host", help="Tunnel host or SSM target for environment access."
    )
    wizard.add_argument(
        "--via",
        choices={"ssh-bastion", "ssm"},
        default=DEFAULT_TUNNEL_VIA,
        help="Tunnel transport to use when opening connections during setup.",
    )
    wizard.add_argument(
        "--preset",
        default=DEFAULT_SETUP_PRESET,
        help="Preset passed to 'hotpass setup'.",
    )
    wizard.add_argument(
        "--skip-credentials",
        action="store_true",
        help="Skip the credentials wizard step.",
    )
    wizard.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip the hotpass setup wizard (tunnels, contexts, etc).",
    )
    wizard.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip .env file generation.",
    )
    wizard.add_argument(
        "--env-target",
        default=DEFAULT_ENV_TARGET,
        help="Environment label when writing .env files.",
    )
    wizard.add_argument(
        "--include-credentials",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include stored credentials when generating the .env file.",
    )
    wizard.add_argument(
        "--allow-network",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Embed network enrichment flags inside the generated .env file.",
    )
    wizard.set_defaults(handler=_handle_wizard)

    connect = subparsers.add_parser(
        "connect",
        help="Open tunnels to Prefect and Marquez (lease mode by default).",
    )
    connect.add_argument(
        "--host", help="Tunnel host / SSM target.", default=DEFAULT_TUNNEL_HOST
    )
    connect.add_argument(
        "--via",
        choices={"ssh-bastion", "ssm"},
        default=DEFAULT_TUNNEL_VIA,
        help="Tunnel transport to use.",
    )
    connect.add_argument(
        "--detach",
        action="store_true",
        help="Run tunnels in the background (detached).",
    )
    connect.add_argument(
        "--label",
        help="Label recorded for the tunnel session (detached mode).",
    )
    connect.add_argument(
        "--no-marquez",
        action="store_true",
        help="Skip Marquez port forwarding.",
    )
    connect.set_defaults(handler=_handle_connect)

    refine = subparsers.add_parser(
        "refine",
        help="Run the core refinement pipeline with sensible defaults.",
    )
    refine.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing workbook inputs.",
    )
    refine.add_argument(
        "--output-path",
        default="dist/refined.xlsx",
        help="Output path for the refined workbook.",
    )
    refine.add_argument(
        "--profile",
        default="generic",
        help="Profile name to use (defaults to 'generic').",
    )
    refine.add_argument(
        "--archive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable archiving of pipeline artefacts.",
    )
    refine.set_defaults(handler=_handle_refine)

    qa = subparsers.add_parser(
        "qa",
        help="Run Hotpass QA gates end-to-end.",
    )
    qa.set_defaults(handler=_handle_qa)

    heartbeat = subparsers.add_parser(
        "heartbeat",
        help="Health probe used by container orchestrators.",
    )
    heartbeat.set_defaults(handler=_handle_heartbeat)

    return parser


def _handle_wizard(args: argparse.Namespace, console: Console) -> int:
    dry_run = args.dry_run
    assume_yes = args.assume_yes
    summary: list[tuple[str, str]] = []

    console.print(Panel("Hotpass operator bootstrap wizard", style="bold cyan"))

    if not args.skip_credentials:
        cred_args = ["hotpass", "credentials", "wizard"]
        if assume_yes:
            cred_args.append("--assume-yes")
        _invoke(cred_args, console, dry_run=dry_run)
        summary.append(("Credentials", "Stored via wizard"))
    else:
        summary.append(("Credentials", "Skipped"))

    if not args.skip_setup:
        host = args.host or (
            DEFAULT_TUNNEL_HOST if assume_yes else _prompt_host(console)
        )
        setup_args: list[str] = [
            "hotpass",
            "setup",
            "--preset",
            args.preset,
            "--execute",
            "--skip-deps",
            "--skip-credentials",
        ]
        if assume_yes:
            setup_args.append("--assume-yes")
        if host:
            setup_args.extend(["--host", host])
        if args.via:
            setup_args.extend(["--via", args.via])
        _invoke(setup_args, console, dry_run=dry_run)
        summary.append(("Setup", f"Completed preset '{args.preset}'"))
    else:
        summary.append(("Setup", "Skipped"))

    if not args.skip_env:
        env_args: list[str] = [
            "hotpass",
            "env",
            "--target",
            args.env_target,
            "--force",
        ]
        if args.allow_network:
            env_args.append("--allow-network")
        if args.include_credentials:
            env_args.append("--include-credentials")
        _invoke(env_args, console, dry_run=dry_run)
        summary.append(("Environment", f".env.{args.env_target} updated"))
    else:
        summary.append(("Environment", "Skipped"))

    table = Table(title="Wizard summary", show_header=True, header_style="bold cyan")
    table.add_column("Step")
    table.add_column("Result")
    for label, result in summary:
        table.add_row(label, result)
    console.print(table)
    if dry_run:
        console.print("[yellow]Dry-run only. No changes were executed.[/yellow]")
    return 0


def _handle_connect(args: argparse.Namespace, console: Console) -> int:
    dry_run = args.dry_run
    via = args.via or DEFAULT_TUNNEL_VIA
    host = args.host or DEFAULT_TUNNEL_HOST
    if args.detach:
        command = [
            "hotpass",
            "net",
            "up",
            "--via",
            via,
            "--host",
            host,
            "--detach",
        ]
        if args.label:
            command.extend(["--label", args.label])
        if args.no_marquez:
            command.append("--no-marquez")
        _invoke(command, console, dry_run=dry_run)
        console.print(
            Panel(
                "Tunnel started in the background. Use 'hotpass net status' to inspect sessions.",
                style="green",
            )
        )
        return 0

    command = [
        "hotpass",
        "net",
        "lease",
        "--via",
        via,
        "--host",
        host,
    ]
    if args.no_marquez:
        command.append("--no-marquez")
    if args.label:
        command.extend(["--label", args.label])
    console.print(
        Panel(
            "Opening managed tunnel lease. Press Ctrl+C when you want to disconnect.",
            style="cyan",
        )
    )
    return _invoke(command, console, dry_run=dry_run, passthrough=True)


def _handle_refine(args: argparse.Namespace, console: Console) -> int:
    command = [
        "hotpass",
        "refine",
        "--input-dir",
        args.input_dir,
        "--output-path",
        args.output_path,
        "--profile",
        args.profile,
    ]
    if args.archive:
        command.append("--archive")
    else:
        command.append("--no-archive")
    return _invoke(command, console, dry_run=args.dry_run)


def _handle_qa(args: argparse.Namespace, console: Console) -> int:
    command = ["hotpass", "qa", "all"]
    return _invoke(command, console, dry_run=args.dry_run)


def _handle_heartbeat(
    args: argparse.Namespace, console: Console
) -> int:  # noqa: ARG001
    console.print("hotpass-operator heartbeat ok")
    return 0


def _invoke(
    command: Sequence[str],
    console: Console,
    *,
    dry_run: bool = False,
    passthrough: bool = False,
    env: dict[str, str] | None = None,
) -> int:
    rendered = _render_command(command)
    console.print(f"[cyan]$ {rendered}[/cyan]")
    if dry_run:
        return 0
    try:
        result = subprocess.run(  # nosec B603 - command arguments are explicit lists
            list(command),
            check=False,
            env=env,
            stdout=None if passthrough else subprocess.PIPE,
            stderr=None if passthrough else subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Command not found: {command[0]} ({exc})") from exc
    if result.returncode != 0:
        output = result.stdout if result.stdout else ""
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {rendered}\n{output}"
        )
    if result.stdout and not passthrough:
        console.print(result.stdout.strip())
    return 0


def _render_command(parts: Iterable[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _prompt_host(console: Console) -> str:
    return str(
        Prompt.ask("Tunnel host (bastion or SSM target)", default=DEFAULT_TUNNEL_HOST)
    )


__all__ = ["main"]
