"""Context bootstrap commands for Prefect and Kubernetes."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any, cast

from rich.console import Console
from rich.table import Table

from ops.net.tunnels import latest_session

from ..builder import CLICommand, CommandHandler, SharedParsers
from ..configuration import CLIProfile
from ..state import load_state, write_state
from ..utils import CommandExecutionError, format_command, run_command

DEFAULT_PREFECT_URL = "http://127.0.0.1:4200/api"
CTX_STATE_FILE = "contexts.json"


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "ctx",
        help="Manage Prefect and Kubernetes contexts",
        description=(
            "Bootstrap Prefect profiles and Kubernetes kubeconfig contexts needed by Hotpass.\n\n"
            "Prefect configuration defaults reuse tunnel ports recorded in "
            ".hotpass/net.json when available."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ctx_subparsers = parser.add_subparsers(dest="ctx_command")

    init_parser = ctx_subparsers.add_parser(
        "init",
        help="Create Prefect profile and/or kubeconfig context",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    init_parser.add_argument(
        "--prefect-profile",
        default="hotpass-staging",
        help="Prefect profile name",
    )
    init_parser.add_argument(
        "--prefect-url", help="Prefect API URL to set for the profile"
    )
    init_parser.add_argument(
        "--use-net",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Derive Prefect URL from active tunnels in .hotpass/net.json when available",
    )
    init_parser.add_argument(
        "--overwrite-prefect",
        action="store_true",
        help="Overwrite the Prefect profile if it already exists",
    )
    init_parser.add_argument(
        "--eks-cluster",
        help="EKS cluster name to configure via aws eks update-kubeconfig",
    )
    init_parser.add_argument(
        "--kube-context",
        help="Alias to assign the kubeconfig context; defaults to the cluster name",
    )
    init_parser.add_argument(
        "--kubeconfig", help="Path to the kubeconfig file to update"
    )
    init_parser.add_argument(
        "--namespace",
        help="Optional namespace to export alongside the context",
    )
    init_parser.add_argument(
        "--no-prefect",
        action="store_true",
        help="Skip Prefect operations (only manage Kubernetes context)",
    )
    init_parser.add_argument(
        "--no-kube",
        action="store_true",
        help="Skip Kubernetes operations (only manage Prefect profile)",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands that would run without executing them",
    )
    init_parser.set_defaults(handler=_handle_init)

    list_parser = ctx_subparsers.add_parser(
        "list",
        help="Show recorded context metadata",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    list_parser.set_defaults(handler=_handle_list)

    return parser


def register() -> CLICommand:
    return CLICommand(
        name="ctx",
        help="Bootstrap Prefect and Kubernetes contexts",
        builder=build,
        handler=_dispatch,
    )


def _dispatch(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile  # context bootstrap is profile independent
    raw_handler = getattr(namespace, "handler", None)
    if not callable(raw_handler):
        Console().print(
            "[red]No ctx subcommand specified (use 'hotpass ctx --help').[/red]"
        )
        return 1
    handler = cast(CommandHandler, raw_handler)
    result = handler(namespace, profile)
    return int(result)


def _handle_init(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    dry_run = args.dry_run
    result: dict[str, Any] = {
        "prefect": {},
        "kubernetes": {},
    }

    if not args.no_prefect:
        prefect_profile = args.prefect_profile
        prefect_url = _resolve_prefect_url(args)
        console.print(
            f"[cyan]Configuring Prefect profile '{prefect_profile}' with API URL "
            f"{prefect_url}[/cyan]"
        )
        if not dry_run:
            commands = [
                ["prefect", "profile", "create", prefect_profile],
                [
                    "prefect",
                    "config",
                    "set",
                    f"PREFECT_API_URL={prefect_url}",
                    "--profile",
                    prefect_profile,
                ],
            ]
            if args.overwrite_prefect:
                commands[0].append("--overwrite")
            try:
                run_command(commands[0], check=True)
            except CommandExecutionError as exc:
                if not args.overwrite_prefect and "already exists" in str(exc):
                    console.print(
                        "[yellow]Prefect profile already exists; reusing existing profile. "
                        "Use --overwrite-prefect to recreate.[/yellow]"
                    )
                else:
                    console.print(f"[red]{exc}[/red]")
                    return 1
            try:
                run_command(commands[1], check=True)
            except CommandExecutionError as exc:
                console.print(f"[red]{exc}[/red]")
                return 1
        result["prefect"] = {
            "profile": prefect_profile,
            "api_url": prefect_url,
        }
    else:
        console.print("[yellow]Skipping Prefect profile setup (--no-prefect).[/yellow]")

    if not args.no_kube and args.eks_cluster:
        kube_command = _build_update_kubeconfig_command(
            cluster=args.eks_cluster,
            context=args.kube_context,
            kubeconfig=args.kubeconfig,
        )
        console.print(
            f"[cyan]Updating kubeconfig:[/cyan] {format_command(kube_command)}"
        )
        if not dry_run:
            try:
                run_command(kube_command, check=True)
            except CommandExecutionError as exc:
                console.print(f"[red]{exc}[/red]")
                return 1
        result["kubernetes"] = {
            "cluster": args.eks_cluster,
            "context": args.kube_context or args.eks_cluster,
            "kubeconfig": args.kubeconfig,
            "namespace": args.namespace,
        }
    elif args.no_kube:
        console.print("[yellow]Skipping kubeconfig updates (--no-kube).[/yellow]")
    else:
        console.print("[yellow]No EKS cluster supplied; kubeconfig unchanged.[/yellow]")

    if args.namespace and not args.no_prefect:
        result.setdefault("prefect", {})["namespace"] = args.namespace

    if not dry_run:
        _append_context_state(result)
        console.print(
            "[green]Context configuration recorded under .hotpass/contexts.json.[/green]"
        )
    else:
        console.print("[yellow]Dry-run complete; no changes written.[/yellow]")

    return 0


def _handle_list(args: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    state = load_state(CTX_STATE_FILE, default={"entries": []}) or {"entries": []}
    entries = state.get("entries", [])
    if not entries:
        console.print("[yellow]No context entries recorded yet.[/yellow]")
        return 0
    headers = [
        "Prefect Profile",
        "API URL",
        "Kube Context",
        "Cluster",
        "Namespace",
        "Recorded At",
    ]
    table = Table(*headers)
    for entry in entries:
        prefect = entry.get("prefect", {})
        kube = entry.get("kubernetes", {})
        table.add_row(
            prefect.get("profile", "-"),
            prefect.get("api_url", "-"),
            kube.get("context", "-"),
            kube.get("cluster", "-"),
            kube.get("namespace", "-"),
            entry.get("recorded_at", "-"),
        )
    console.print(table)
    return 0


def _resolve_prefect_url(args: argparse.Namespace) -> str:
    if args.prefect_url:
        return str(args.prefect_url)
    if args.use_net:
        session = latest_session()
        if session:
            prefect_meta = session.metadata.get("prefect", {})
            port = prefect_meta.get("local_port")
            if port:
                return f"http://127.0.0.1:{port}/api"
    return DEFAULT_PREFECT_URL


def _build_update_kubeconfig_command(
    *,
    cluster: str,
    context: str | None,
    kubeconfig: str | None,
) -> list[str]:
    command = ["aws", "eks", "update-kubeconfig", "--name", cluster]
    if context:
        command.extend(["--alias", context])
    if kubeconfig:
        command.extend(["--kubeconfig", kubeconfig])
    return command


def _append_context_state(payload: dict[str, Any]) -> None:
    current = load_state(CTX_STATE_FILE, default={"entries": []}) or {"entries": []}
    entries = current.get("entries", [])
    payload = dict(payload)
    payload["recorded_at"] = datetime.now(tz=UTC).isoformat()
    entries.append(payload)
    current["entries"] = entries
    write_state(CTX_STATE_FILE, current)
