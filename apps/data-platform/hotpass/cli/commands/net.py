"""Network tunnel management commands."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, CommandHandler, SharedParsers
from ..configuration import CLIProfile
from ..state import load_state, remove_state, write_state
from ..utils import CommandExecutionError, format_command, run_command

STATE_FILE = "net.json"
DEFAULT_PREFECT_REMOTE_HOST = "prefect.staging.internal"
DEFAULT_MARQUEZ_REMOTE_HOST = "marquez.staging.internal"
DEFAULT_PREFECT_REMOTE_PORT = 4200
DEFAULT_MARQUEZ_REMOTE_PORT = 5000


@dataclass
class TunnelSession:
    """Representation of a stored tunnel session."""

    label: str
    via: str
    command: list[str]
    pid: int | None
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "via": self.via,
            "command": self.command,
            "pid": self.pid,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TunnelSession:
        return cls(
            label=str(payload.get("label", "")),
            via=str(payload.get("via", "")),
            command=list(payload.get("command", [])),
            pid=payload.get("pid"),
            created_at=str(payload.get("created_at", "")),
            metadata=dict(payload.get("metadata", {})),
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
    up_parser.add_argument(
        "--via",
        choices={"ssh-bastion", "ssm"},
        default="ssh-bastion",
        help="Tunnel mechanism to use",
    )
    up_parser.add_argument(
        "--host",
        help="Bastion host (for ssh-bastion) or SSM target instance ID (for ssm)",
    )
    up_parser.add_argument(
        "--ssh-user",
        default=os.environ.get("HOTPASS_BASTION_USER", os.environ.get("USER", "ec2-user")),
        help="SSH user for bastion hops",
    )
    up_parser.add_argument(
        "--prefect-host",
        default=os.environ.get("HOTPASS_PREFECT_REMOTE_HOST", DEFAULT_PREFECT_REMOTE_HOST),
        help="Remote Prefect host to forward",
    )
    up_parser.add_argument(
        "--prefect-port",
        type=int,
        default=4200,
        help="Local Prefect port",
    )
    up_parser.add_argument(
        "--prefect-remote-port",
        type=int,
        default=DEFAULT_PREFECT_REMOTE_PORT,
        help="Remote Prefect port",
    )
    up_parser.add_argument(
        "--marquez-host",
        default=os.environ.get("HOTPASS_MARQUEZ_REMOTE_HOST", DEFAULT_MARQUEZ_REMOTE_HOST),
        help="Remote Marquez host to forward",
    )
    up_parser.add_argument(
        "--marquez-port",
        type=int,
        default=5000,
        help="Local Marquez port",
    )
    up_parser.add_argument(
        "--marquez-remote-port",
        type=int,
        default=DEFAULT_MARQUEZ_REMOTE_PORT,
        help="Remote Marquez port",
    )
    up_parser.add_argument(
        "--no-marquez",
        action="store_true",
        help="Skip forwarding Marquez UI/API",
    )
    up_parser.add_argument(
        "--label",
        help="Label to associate with the tunnel session",
    )
    up_parser.add_argument(
        "--detach",
        action="store_true",
        help="Run the tunnel in the background and remember the PID",
    )
    up_parser.add_argument(
        "--auto-port",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Automatically pick the next free port if the requested port is in use",
    )
    up_parser.add_argument(
        "--ssh-option",
        action="append",
        dest="ssh_options",
        help="Extra -o options to pass to ssh (repeatable)",
    )
    up_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the tunnel command without executing it",
    )
    up_parser.set_defaults(handler=_handle_up)

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
        Console().print("[red]No net subcommand specified (use 'hotpass net --help').[/red]")
        return 1
    handler = cast(CommandHandler, raw_handler)
    result = handler(namespace, profile)
    return int(result)


# ---------------------------------------------------------------------------
# Helpers


def _load_sessions() -> list[TunnelSession]:
    data = load_state(STATE_FILE, default={"sessions": []}) or {"sessions": []}
    sessions_payload = data.get("sessions", [])
    sessions: list[TunnelSession] = []
    for entry in sessions_payload:
        try:
            sessions.append(TunnelSession.from_dict(entry))
        except Exception:
            continue
    return sessions


def _store_sessions(sessions: list[TunnelSession]) -> None:
    payload = {"sessions": [session.to_dict() for session in sessions]}
    write_state(STATE_FILE, payload)


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _find_available_port(start: int, limit: int = 20) -> int | None:
    port = start
    attempts = limit
    while attempts > 0:
        if _is_port_available(port):
            return port
        port += 1
        attempts -= 1
    return None


def _format_ports(metadata: dict[str, Any]) -> str:
    details = []
    prefect_port = metadata.get("prefect", {}).get("local_port")
    if prefect_port:
        details.append(f"Prefect:{prefect_port}")
    marquez_port = metadata.get("marquez", {}).get("local_port")
    if marquez_port:
        details.append(f"Marquez:{marquez_port}")
    return ", ".join(details) if details else "-"


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_pid(pid: int) -> None:
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            return


# ---------------------------------------------------------------------------
# Command handlers


def _handle_up(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    via = args.via
    label = args.label or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")

    sessions = _load_sessions()
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
    assert host is not None  # narrow for type-checkers

    # Resolve ports
    prefect_port = args.prefect_port
    if not _is_port_available(prefect_port):
        if args.auto_port:
            new_port = _find_available_port(prefect_port + 1)
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
    if enable_marquez and not _is_port_available(marquez_port):
        if args.auto_port:
            new_port = _find_available_port(marquez_port + 1)
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
            proc = subprocess.Popen(  # noqa: S603
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                start_new_session=True,
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
        _store_sessions(sessions)
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


def _handle_down(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    sessions = _load_sessions()
    if not sessions:
        console.print("[yellow]No recorded tunnel sessions.[/yellow]")
        return 0

    if args.all:
        targets = sessions
    else:
        if not args.label:
            console.print("[red]Specify --label or use --all to terminate all sessions.[/red]")
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
        if _is_process_alive(pid):
            _terminate_pid(pid)
            console.print(f"[green]Terminated tunnel '{session.label}' (PID {pid}).[/green]")
        else:
            console.print(
                f"[yellow]Tunnel '{session.label}' already inactive (PID {pid} "
                "not running).[/yellow]"
            )

    if remaining:
        _store_sessions(remaining)
    else:
        remove_state(STATE_FILE)
    return 0


def _handle_status(
    args: argparse.Namespace,
    profile: CLIProfile | None,
) -> int:
    _ = profile
    console = Console()
    sessions = _load_sessions()
    if not sessions:
        console.print("[yellow]No recorded tunnel sessions.[/yellow]")
        return 0

    table = Table("Label", "Method", "Ports", "PID", "Alive?", "Created", "Command")
    for session in sessions:
        pid_display = "-"
        alive = "-"
        if session.pid is not None:
            pid_display = str(session.pid)
            alive = "yes" if _is_process_alive(session.pid) else "no"
        table.add_row(
            session.label or "-",
            session.via,
            _format_ports(session.metadata),
            pid_display,
            alive,
            session.created_at,
            format_command(session.command),
        )
    console.print(table)
    return 0
