"""Environment file generation helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..state import load_state

NET_STATE_FILE = "net.json"
CTX_STATE_FILE = "contexts.json"


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "env",
        help="Write Hotpass .env files",
        description=(
            "Generate environment files with Prefect and OpenLineage configuration. "
            "Defaults reuse tunnel information from .hotpass/net.json when available."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        default="staging",
        help="Environment name (affects output filename)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Explicit output path (defaults to .env.<target>)",
    )
    parser.add_argument(
        "--prefect-url",
        help="Override Prefect API URL (otherwise derived from tunnels or defaults)",
    )
    parser.add_argument(
        "--openlineage-url",
        help="Override OpenLineage API URL (otherwise derived from tunnels or defaults)",
    )
    parser.add_argument(
        "--allow-network",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Toggle network enrichment-related environment variables",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the environment file contents without writing",
    )
    parser.set_defaults(handler=_command_handler)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="env",
        help="Generate .env files for Hotpass environments",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile
    console = Console()
    target = namespace.target
    output_path = namespace.output or Path(f".env.{target}")

    prefect_url = namespace.prefect_url or _derive_prefect_url()
    openlineage_url = namespace.openlineage_url or _derive_openlineage_url()
    allow_network = namespace.allow_network
    dry_run = namespace.dry_run

    env_lines = _build_env_lines(
        prefect_url=prefect_url,
        openlineage_url=openlineage_url,
        allow_network=allow_network,
    )

    if dry_run:
        console.print(Panel("\n".join(env_lines), title="Environment Preview", expand=False))
        console.print("[yellow]Dry-run complete; file not written.[/yellow]")
        return 0

    if output_path.exists() and not namespace.force:
        console.print(
            f"[red]Output path {output_path} already exists. Use --force to overwrite.[/red]"
        )
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    console.print(f"[green]Environment file written to {output_path}[/green]")
    console.print(f"Use `set -a; source {output_path}; set +a` to load the variables.")
    return 0


def _build_env_lines(
    *,
    prefect_url: str,
    openlineage_url: str,
    allow_network: bool,
) -> list[str]:
    lines = [
        f"PREFECT_API_URL={prefect_url}",
        f"OPENLINEAGE_URL={openlineage_url}",
    ]
    ctx_state = load_state(CTX_STATE_FILE, default={"entries": []}) or {"entries": []}
    entries = ctx_state.get("entries", [])
    if entries:
        last_entry = entries[-1]
        prefect = last_entry.get("prefect", {})
        profile = prefect.get("profile")
        if profile:
            lines.append(f"HOTPASS_PREFECT_PROFILE={profile}")
        namespace = last_entry.get("kubernetes", {}).get("namespace")
        if namespace:
            lines.append(f"HOTPASS_KUBE_NAMESPACE={namespace}")
    lines.append(f"FEATURE_ENABLE_REMOTE_RESEARCH={'true' if allow_network else 'false'}")
    lines.append(f"ALLOW_NETWORK_RESEARCH={'true' if allow_network else 'false'}")
    return lines


def _derive_prefect_url() -> str:
    net_state = load_state(NET_STATE_FILE, default={"sessions": []}) or {"sessions": []}
    sessions = net_state.get("sessions", [])
    if sessions:
        session = sessions[-1]
        prefect_meta = session.get("metadata", {}).get("prefect", {})
        port = prefect_meta.get("local_port")
        if port:
            return f"http://127.0.0.1:{port}/api"
    return "http://127.0.0.1:4200/api"


def _derive_openlineage_url() -> str:
    net_state = load_state(NET_STATE_FILE, default={"sessions": []}) or {"sessions": []}
    sessions = net_state.get("sessions", [])
    if sessions:
        session = sessions[-1]
        marquez_meta = session.get("metadata", {}).get("marquez", {})
        port = marquez_meta.get("local_port")
        if port:
            return f"http://127.0.0.1:{port}/api/v1"
    return "http://127.0.0.1:5000/api/v1"
