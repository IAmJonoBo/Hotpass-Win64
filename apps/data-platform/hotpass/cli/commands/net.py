"""Network tunnel management commands."""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404 - tunnel management requires subprocess control
import time
from datetime import UTC, datetime
from typing import cast

from rich.console import Console
from rich.table import Table

from ops.net.tunnels import (
    TunnelSession,
    clear_sessions,
    find_available_port,
    format_ports,
    is_port_available,
    is_process_alive,
    load_sessions,
    save_sessions,
    terminate_pid,
)

from ..builder import CLICommand, CommandHandler, SharedParsers
from ..configuration import CLIProfile
from ..utils import CommandExecutionError, format_command, run_command

DEFAULT_PREFECT_REMOTE_HOST = "prefect.staging.internal"
DEFAULT_MARQUEZ_REMOTE_HOST = "marquez.staging.internal"
DEFAULT_PREFECT_REMOTE_PORT = 4200
DEFAULT_MARQUEZ_REMOTE_PORT = 5000


def _configure_tunnel_parser(
    parser: argparse.ArgumentParser,
    *,
    include_detach: bool,
) -> None:
    parser.add_argument(
        "--via",
        choices={"ssh-bastion", "ssm"},
        default="ssh-bastion",
        help="Tunnel mechanism to use",
    )
    parser.add_argument(
        "--host",
        help="Bastion host (for ssh-bastion) or SSM target instance ID (for ssm)",
    )
    parser.add_argument(
        "--ssh-user",
        default=os.environ.get(
            "HOTPASS_BASTION_USER", os.environ.get("USER", "ec2-user")
        ),
        help="SSH user for bastion hops",
    )
    parser.add_argument(
        "--prefect-host",
        default=os.environ.get(
            "HOTPASS_PREFECT_REMOTE_HOST", DEFAULT_PREFECT_REMOTE_HOST
        ),
        help="Remote Prefect host to forward",
    )
    parser.add_argument(
        "--prefect-port",
        type=int,
        default=4200,
        help="Local Prefect port",
    )
    parser.add_argument(
        "--prefect-remote-port",
        type=int,
        default=DEFAULT_PREFECT_REMOTE_PORT,
        help="Remote Prefect port",
    )
    parser.add_argument(
        "--marquez-host",
        default=os.environ.get(
            "HOTPASS_MARQUEZ_REMOTE_HOST", DEFAULT_MARQUEZ_REMOTE_HOST
        ),
        help="Remote Marquez host to forward",
    )
    parser.add_argument(
        "--marquez-port",
        type=int,
        default=5000,
        help="Local Marquez port",
    )
    parser.add_argument(
        "--marquez-remote-port",
        type=int,
        default=DEFAULT_MARQUEZ_REMOTE_PORT,
        help="Remote Marquez port",
    )
    parser.add_argument(
        "--no-marquez",
        action="store_true",
        help="Skip forwarding Marquez UI/API",
    )
    parser.add_argument(
        "--label",
        help="Label to associate with the tunnel session",
    )
    if include_detach:
        parser.add_argument(
            "--detach",
            action="store_true",
            help="Run the tunnel in the background and remember the PID",
        )
    parser.add_argument(
        "--auto-port",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Automatically pick the next free port if the requested port is in use",
    )
    parser.add_argument(
        "--ssh-option",
        action="append",
        dest="ssh_options",
        help="Extra -o options to pass to ssh (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the tunnel command without executing it",
    )


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "net",
        help="Manage SSH/SSM tunnels to Hotpass environments",
        description=(
            "Establish and manage tunnels to staging infrastructure (Prefect, Marquez). "
            "Supports SSH bastion and AWS SSM port forwarding flows."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    net_subparsers = parser.add_subparsers(dest="net_command")

    up_parser = net_subparsers.add_parser(
        "up",
        help="Start a tunnel session",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _configure_tunnel_parser(up_parser, include_detach=True)
    up_parser.set_defaults(handler=_handle_up)

    lease_parser = net_subparsers.add_parser(
        "lease",
        help="Start a tunnel that is torn down when the CLI exits",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _configure_tunnel_parser(lease_parser, include_detach=False)
    lease_parser.set_defaults(handler=_handle_lease)

    down_parser = net_subparsers.add_parser(
        "down",
        help="Stop tunnel sessions started with 'net up'",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    down_parser.add_argument(
        "--label",
        help="Label of the tunnel session to stop",
    )
    down_parser.add_argument(
        "--all",
        action="store_true",
        help="Terminate all recorded tunnel sessions",
    )
    down_parser.set_defaults(handler=_handle_down)

    status_parser = net_subparsers.add_parser(
        "status",
        help="Display saved tunnel sessions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    status_parser.set_defaults(handler=_handle_status)

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="net",
        help="Manage tunnels to Hotpass infrastructure",
        builder=build,
        handler=_dispatch,
    )


def _dispatch(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile  # network commands are environment specific
    raw_handler = getattr(namespace, "handler", None)
    if not callable(raw_handler):
        Console().print(
            "[red]No net subcommand specified (use 'hotpass net --help').[/red]"
        )
        return 1
    handler = cast(CommandHandler, raw_handler)
    result = handler(namespace, profile)
    return int(result)


# ---------------------------------------------------------------------------
# Command handlers


def _handle_up(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    via = args.via
    label = args.label or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")

    sessions = load_sessions()
    if any(session.label == label for session in sessions):
        console.print(
            f"[red]A tunnel session named '{label}' already exists. "
            "Use --label to supply a unique name or "
            f"run 'hotpass net down --label {label}'.[/red]"
        )
        return 1

    # Resolve host/target
    raw_host = args.host or os.environ.get("HOTPASS_BASTION_HOST")
    host: str | None = str(raw_host) if raw_host is not None else None
    if via == "ssh-bastion" and not host:
        console.print(
            "[red]Bastion host is required (pass --host or set HOTPASS_BASTION_HOST).[/red]"
        )
        return 1
    if via == "ssm" and not host:
        console.print(
            "[red]SSM target instance ID is required "
            "(pass --host or set HOTPASS_BASTION_HOST).[/red]"
        )
        return 1
    if host is None:
        console.print("[red]Unable to resolve target host for tunnel setup.[/red]")
        return 1
    host = cast(str, host)

    # Resolve ports
    prefect_port = args.prefect_port
    if not is_port_available(prefect_port):
        if args.auto_port:
            new_port = find_available_port(prefect_port + 1)
            if new_port is None:
                console.print(
                    "[red]Unable to locate a free port for Prefect tunnel; "
                    "disable --auto-port to stop auto searching or free ports.[/red]"
                )
                return 1
            console.print(
                f"[yellow]Local port {prefect_port} in use. "
                f"Selecting {new_port} for Prefect[/yellow]"
            )
            prefect_port = new_port
        else:
            console.print(
                f"[red]Local port {prefect_port} is in use. Specify a free port or "
                "enable --auto-port.[/red]"
            )
            return 1

    enable_marquez = not args.no_marquez
    marquez_port = args.marquez_port
    if enable_marquez and not is_port_available(marquez_port):
        if args.auto_port:
            new_port = find_available_port(marquez_port + 1)
            if new_port is None:
                console.print(
                    "[red]Unable to locate a free port for Marquez tunnel; "
                    "disable --auto-port to stop auto searching or free ports.[/red]"
                )
                return 1
            console.print(
                f"[yellow]Local port {marquez_port} in use. "
                f"Selecting {new_port} for Marquez[/yellow]"
            )
            marquez_port = new_port
        else:
            console.print(
                f"[red]Local port {marquez_port} is in use. Specify a free port or "
                "enable --auto-port.[/red]"
            )
            return 1

    command: list[str] = []
    if via == "ssh-bastion":
        command = ["ssh", "-N"]
        for option in args.ssh_options or []:
            command.extend(["-o", option])
        command.extend(
            [
                "-L",
                f"{prefect_port}:{args.prefect_host}:{args.prefect_remote_port}",
            ]
        )
        if enable_marquez:
            command.extend(
                [
                    "-L",
                    f"{marquez_port}:{args.marquez_host}:{args.marquez_remote_port}",
                ]
            )
        command.append(f"{args.ssh_user}@{host}")
    else:  # via == "ssm"
        command = [
            "aws",
            "ssm",
            "start-session",
            "--target",
            host,
            "--document-name",
            "AWS-StartPortForwardingSession",
            "--parameters",
            f"portNumber={args.prefect_remote_port},localPortNumber={prefect_port}",
        ]
        if enable_marquez:
            console.print(
                "[yellow]SSM tunnels currently forward a single port; "
                "run a second session for Marquez if required.[/yellow]"
            )

    console.print(f"[cyan]Tunnel command:[/cyan] {format_command(command)}")

    metadata = {
        "prefect": {
            "local_port": prefect_port,
            "remote_host": args.prefect_host,
            "remote_port": args.prefect_remote_port,
        }
    }
    if enable_marquez:
        metadata["marquez"] = {
            "local_port": marquez_port,
            "remote_host": args.marquez_host,
            "remote_port": args.marquez_remote_port,
        }

    if args.dry_run:
        console.print("[green]Dry-run complete; tunnel not started.[/green]")
        return 0

    if args.detach:
        try:
            proc = (
                subprocess.Popen(  # nosec B603 - command is explicit and shell disabled
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        except FileNotFoundError as exc:
            console.print(f"[red]Failed to start tunnel: {exc}[/red]")
            return 1
        session = TunnelSession(
            label=label,
            via=via,
            command=command,
            pid=proc.pid,
            created_at=datetime.now(tz=UTC).isoformat(),
            metadata=metadata,
        )
        sessions.append(session)
        save_sessions(sessions)
        console.print(
            f"[green]Tunnel '{label}' started in background (PID {proc.pid}). "
            "Use 'hotpass net status' to inspect or 'hotpass net down --label {label}' to stop."
        )
        return 0

    console.print(
        "[blue]Starting tunnel in the foreground. Press Ctrl+C to close the session.[/blue]"
    )
    try:
        run_command(command, check=True)
    except CommandExecutionError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    return 0


def _handle_lease(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    lease_args = argparse.Namespace(**vars(args))
    lease_args.detach = True
    lease_args.dry_run = getattr(args, "dry_run", False)
    if not getattr(lease_args, "label", None):
        lease_args.label = datetime.now(tz=UTC).strftime("lease-%Y%m%dT%H%M%SZ")

    console.print(
        "[cyan]Opening managed tunnel lease. The session stops automatically when you exit.[/cyan]"
    )
    exit_code = _handle_up(lease_args, profile)
    if exit_code != 0:
        return exit_code

    if lease_args.dry_run:
        return 0

    console.print(
        "[green]Tunnel active. Press Ctrl+C or close the terminal to stop.[/green]"
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping tunnel lease...[/yellow]")
    finally:
        down_args = argparse.Namespace(label=lease_args.label, all=False)
        down_result = _handle_down(down_args, profile)
        if down_result != 0:
            console.print(
                "[red]Automatic tunnel teardown failed.[/red] "
                f"Run 'hotpass net down --label {lease_args.label}' manually."
            )
    return 0


def _handle_down(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    sessions = load_sessions()
    if not sessions:
        console.print("[yellow]No recorded tunnel sessions.[/yellow]")
        return 0

    if args.all:
        targets = sessions
    else:
        if not args.label:
            console.print(
                "[red]Specify --label or use --all to terminate all sessions.[/red]"
            )
            return 1
        targets = [session for session in sessions if session.label == args.label]
        if not targets:
            console.print(f"[red]No tunnel session named '{args.label}' found.[/red]")
            return 1

    remaining: list[TunnelSession] = []
    for session in sessions:
        if session not in targets:
            remaining.append(session)
            continue
        pid = session.pid
        if pid is None:
            console.print(
                f"[yellow]Session '{session.label}' was not started in detach mode; "
                "nothing to terminate.[/yellow]"
            )
            continue
        if is_process_alive(pid):
            terminate_pid(pid)
            console.print(
                f"[green]Terminated tunnel '{session.label}' (PID {pid}).[/green]"
            )
        else:
            console.print(
                f"[yellow]Tunnel '{session.label}' already inactive (PID {pid} "
                "not running).[/yellow]"
            )

    if remaining:
        save_sessions(remaining)
    else:
        clear_sessions()
    return 0


def _handle_status(
    args: argparse.Namespace,
    profile: CLIProfile | None,
) -> int:
    _ = profile
    console = Console()
    sessions = load_sessions()
    if not sessions:
        console.print("[yellow]No recorded tunnel sessions.[/yellow]")
        return 0

    table = Table("Label", "Method", "Ports", "PID", "Alive?", "Created", "Command")
    for session in sessions:
        pid_display = "-"
        alive = "-"
        if session.pid is not None:
            pid_display = str(session.pid)
            alive = "yes" if is_process_alive(session.pid) else "no"
        table.add_row(
            session.label or "-",
            session.via,
            format_ports(session.metadata),
            pid_display,
            alive,
            session.created_at,
            format_command(session.command),
        )
    console.print(table)
    return 0
