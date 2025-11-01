"""AWS credential and EKS verification helpers."""

from __future__ import annotations

import argparse
import json
from typing import Any

from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..state import write_state
from ..utils import CommandExecutionError, format_command, run_command

try:
    from ops.arc.verify_runner_lifecycle import AwsIdentityVerifier
except ModuleNotFoundError:  # pragma: no cover - defensive guard
    AwsIdentityVerifier = None  # type: ignore[assignment]


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "aws",
        help="Check AWS identity and EKS connectivity",
        description=(
            "Resolve the current AWS identity and optionally validate access to an "
            "EKS cluster. Results are stored in .hotpass/aws.json."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--aws-profile",
        dest="aws_profile",
        help="AWS CLI profile name to use (defaults to Hotpass profile if omitted)",
    )
    parser.add_argument("--region", help="AWS region override for commands")
    parser.add_argument(
        "--eks-cluster",
        help="EKS cluster name to describe/verify (optional)",
    )
    parser.add_argument(
        "--kube-context",
        help="Alias to assign when updating kubeconfig (defaults to cluster name)",
    )
    parser.add_argument(
        "--kubeconfig",
        type=str,
        help="Path to kubeconfig file to update (defaults to standard kubeconfig)",
    )
    parser.add_argument(
        "--verify-kubeconfig",
        action="store_true",
        help="Run 'aws eks update-kubeconfig' after describing the cluster",
    )
    parser.add_argument(
        "--output",
        choices={"text", "json"},
        default="text",
        help="Render mode for the command output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the AWS commands without executing them",
    )
    parser.set_defaults(handler=_command_handler)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="aws",
        help="Validate AWS identity and EKS connectivity",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    _ = profile  # AWS checks are profile-agnostic within the CLI
    console = Console()
    if AwsIdentityVerifier is None:
        console.print(
            "[red]AwsIdentityVerifier module unavailable. Check ops/arc installation.[/red]"
        )
        return 1

    aws_profile = getattr(namespace, "aws_profile", None)
    aws_region = namespace.region
    dry_run = namespace.dry_run
    output_mode = namespace.output
    result_payload: dict[str, Any] = {
        "profile": aws_profile,
        "region": aws_region,
    }

    # Resolve identity
    try:
        identity_verifier = AwsIdentityVerifier(region=aws_region, profile=aws_profile)
        identity = identity_verifier.verify() if not dry_run else None
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to resolve AWS identity: {exc}[/red]")
        return 1

    if identity:
        result_payload["identity"] = identity.as_dict()

    cluster_info: dict[str, Any] | None = None
    cluster_name = namespace.eks_cluster
    if cluster_name:
        describe_command = _build_aws_command(
            ["eks", "describe-cluster", "--name", cluster_name, "--output", "json"],
            profile=aws_profile,
            region=aws_region,
        )
        console.print(
            f"[cyan]Describing cluster:[/cyan] {format_command(describe_command)}"
        )
        if not dry_run:
            try:
                proc = run_command(describe_command, capture_output=True, check=True)
            except CommandExecutionError as exc:
                console.print(f"[red]{exc}[/red]")
                return 1
            cluster_info = json.loads(proc.stdout)
            result_payload["cluster"] = cluster_info
        if namespace.verify_kubeconfig:
            kube_command = _build_aws_command(
                ["eks", "update-kubeconfig", "--name", cluster_name],
                profile=aws_profile,
                region=aws_region,
            )
            if namespace.kube_context:
                kube_command.extend(["--alias", namespace.kube_context])
            if namespace.kubeconfig:
                kube_command.extend(["--kubeconfig", namespace.kubeconfig])
            console.print(
                f"[cyan]Updating kubeconfig:[/cyan] {format_command(kube_command)}"
            )
            if not dry_run:
                try:
                    run_command(kube_command, check=True)
                except CommandExecutionError as exc:
                    console.print(f"[red]{exc}[/red]")
                    return 1

    if output_mode == "json":
        console.print(json.dumps(result_payload, indent=2))
    else:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Field")
        table.add_column("Value")
        identity_dict = result_payload.get("identity", {})
        if identity_dict:
            table.add_row("Account", identity_dict.get("account", ""))
            table.add_row("User ID", identity_dict.get("user_id", ""))
            table.add_row("ARN", identity_dict.get("arn", ""))
            table.add_row("Source", identity_dict.get("source", ""))
        else:
            table.add_row("Identity", "Dry-run (not resolved)")
        if cluster_name:
            if cluster_info:
                status = cluster_info.get("cluster", {}).get("status", "unknown")
                endpoint = cluster_info.get("cluster", {}).get("endpoint", "n/a")
                table.add_row("EKS Cluster", cluster_name)
                table.add_row("Cluster status", status)
                table.add_row("API endpoint", endpoint)
            else:
                table.add_row("EKS Cluster", f"{cluster_name} (dry-run)")
        console.print(table)

    if not dry_run:
        write_state("aws.json", result_payload)
        console.print(
            "[green]AWS verification complete; state recorded under .hotpass/aws.json[/green]"
        )
    else:
        console.print("[yellow]Dry-run complete; no commands executed.[/yellow]")

    return 0


def _build_aws_command(
    command: list[str],
    *,
    profile: str | None,
    region: str | None,
) -> list[str]:
    base = ["aws"]
    if profile:
        base.extend(["--profile", profile])
    if region:
        base.extend(["--region", region])
    base.extend(command)
    return base
