"""ARC runner lifecycle verification wrapper."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..state import ensure_state_dir
from ..utils import format_command


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "arc",
        help="Verify GitHub ARC runner scale sets",
        description=(
            "Wrapper around ops.arc.verify_runner_lifecycle that provides tunnel-aware output, "
            "optional artifact storage, and improved UX."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--owner", required=True, help="Repository owner (org or user)")
    parser.add_argument("--repository", required=True, help="Repository name")
    parser.add_argument("--scale-set", required=True, help="RunnerScaleSet name")
    parser.add_argument(
        "--namespace",
        default="arc-runners",
        help="Kubernetes namespace for runners",
    )
    parser.add_argument(
        "--timeout", type=float, default=600.0, help="Timeout in seconds"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--snapshot", type=Path, help="Snapshot file for offline verification"
    )
    parser.add_argument(
        "--verify-oidc", action="store_true", help="Also verify AWS OIDC identity"
    )
    parser.add_argument("--aws-region", help="AWS region override for identity checks")
    parser.add_argument(
        "--aws-profile", help="AWS profile override for identity checks"
    )
    parser.add_argument(
        "--output",
        choices={"text", "json"},
        default="text",
        help="Render mode for lifecycle tool output",
    )
    parser.add_argument(
        "--store-summary",
        action="store_true",
        help="Persist the verification output under .hotpass/arc/<timestamp>/",
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        help="Write the JSON verification result to this path for the web UI health checks.",
    )
    parser.add_argument(
        "--store-dir",
        type=Path,
        help="Custom directory to store verification output (defaults to .hotpass/arc/<timestamp>)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the underlying command without executing it",
    )
    parser.set_defaults(handler=_command_handler)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="arc",
        help="Verify GitHub ARC runner lifecycle",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    if namespace.status_path and namespace.output != "json":
        namespace.output = "json"
    command = _build_runner_command(namespace)
    console.print(f"[cyan]ARC verification command:[/cyan] {format_command(command)}")

    if namespace.dry_run:
        console.print("[yellow]Dry-run complete; verification not executed.[/yellow]")
        return 0

    try:
        proc = __import__("subprocess").run(  # noqa: S602
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]Failed to execute verification command: {exc}[/red]")
        return 1

    if proc.stdout:
        console.print(proc.stdout.strip())
    if proc.stderr:
        console.print(
            Panel(proc.stderr.strip(), title="stderr", expand=False, style="red")
        )

    if proc.returncode != 0:
        console.print("[red]ARC verification failed.[/red]")
        return int(proc.returncode)

    if namespace.store_summary:
        output_dir = _resolve_store_dir(namespace.store_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "arc_verification.txt"
        summary_path.write_text(proc.stdout, encoding="utf-8")
        metadata = {
            "command": command,
            "owner": namespace.owner,
            "repository": namespace.repository,
            "scale_set": namespace.scale_set,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        console.print(f"[green]Stored verification output under {output_dir}[/green]")

    if namespace.status_path:
        status_path = Path(namespace.status_path)
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            console.print(f"[red]Failed to decode ARC status JSON: {exc}[/red]")
            return 1
        payload.setdefault("verified_at", datetime.now(tz=UTC).isoformat())
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]ARC status written to {status_path}[/green]")

    return 0


def _build_runner_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "ops.arc.verify_runner_lifecycle",
        "--owner",
        args.owner,
        "--repository",
        args.repository,
        "--scale-set",
        args.scale_set,
        "--namespace",
        args.namespace,
        "--timeout",
        str(args.timeout),
        "--poll-interval",
        str(args.poll_interval),
        "--output",
        args.output,
    ]
    if args.snapshot:
        command.extend(["--snapshot", str(args.snapshot)])
    if args.verify_oidc:
        command.append("--verify-oidc")
    if args.aws_region:
        command.extend(["--aws-region", args.aws_region])
    if args.aws_profile:
        command.extend(["--aws-profile", args.aws_profile])
    return command


def _resolve_store_dir(user_dir: Path | None) -> Path:
    if user_dir is not None:
        return user_dir
    state_dir: Path = ensure_state_dir()
    arc_dir = state_dir / "arc"
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return arc_dir / timestamp
