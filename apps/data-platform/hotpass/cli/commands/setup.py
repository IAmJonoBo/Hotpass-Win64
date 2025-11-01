"""Guided setup workflows for operators and agents."""

from __future__ import annotations

import argparse
import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..builder import CLICommand, CommandHandler, SharedParsers
from ..configuration import CLIProfile
from ..state import write_state
from ..utils import CommandExecutionError, format_command, run_command

DEFAULT_PRESET = "staging"
DEFAULT_EXTRAS_STAGING = ["dev", "orchestration", "enrichment"]
DEFAULT_EXTRAS_LOCAL = ["dev", "docs"]
DEFAULT_EXTRAS_FALLBACK = ["dev", "orchestration"]
DEFAULT_PREFECT_PROFILE = "hotpass-staging"
DEFAULT_AWS_PROFILE = "hotpass-staging"
DEFAULT_EKS_CLUSTER = "hotpass-staging"
DEFAULT_NAMESPACE = "hotpass"
DEFAULT_ENV_TARGET = "staging"
DEFAULT_VIA = "ssh-bastion"


@dataclass(slots=True)
class WizardStep:
    """A single action executed by the setup wizard."""

    title: str
    summary: str
    cli_args: list[str] | None = None
    shell_command: list[str] | None = None
    env: dict[str, str] = field(default_factory=dict)

    def display_command(self) -> str:
        if self.cli_args:
            return "hotpass " + " ".join(self.cli_args)
        if self.shell_command:
            return str(format_command(self.shell_command))
        return self.summary


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "setup",
        help="Run guided wizards for dependency sync and staging bootstrap",
        description=(
            "Guide operators through environment bootstrap: sync dependencies, open tunnels, "
            "verify AWS credentials, initialise Prefect/Kubernetes contexts, and emit .env files."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--preset",
        choices={"staging", "local"},
        default=DEFAULT_PRESET,
        help="Preset that controls default extras, namespaces, and environment targets",
    )
    parser.add_argument(
        "--extras",
        action="append",
        help="Explicit uv extras to install (repeatable). Overrides preset defaults.",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip dependency synchronisation.",
    )
    parser.add_argument(
        "--skip-prereqs",
        action="store_true",
        help="Skip prerequisite command checks (uv, prefect, aws, kubectl, ssh).",
    )
    parser.add_argument(
        "--via",
        choices={"ssh-bastion", "ssm"},
        help="Tunnel mechanism passed to 'hotpass net up'. Defaults to preset choice.",
    )
    parser.add_argument(
        "--host",
        help="Bastion hostname (ssh-bastion) or SSM instance ID (ssm) for tunnel creation.",
    )
    parser.add_argument(
        "--label",
        help="Label recorded for the tunnel session (defaults to preset-derived value).",
    )
    parser.add_argument(
        "--skip-tunnels",
        action="store_true",
        help="Skip tunnel creation (net up).",
    )
    parser.add_argument(
        "--aws-profile",
        help="AWS CLI profile used during verification (defaults to preset-derived value).",
    )
    parser.add_argument(
        "--aws-region",
        help="AWS region override for verification commands.",
    )
    parser.add_argument(
        "--skip-aws",
        action="store_true",
        help="Skip AWS identity/EKS verification.",
    )
    parser.add_argument(
        "--eks-cluster",
        help="EKS cluster name for kubeconfig updates.",
    )
    parser.add_argument(
        "--kube-context",
        help="Context alias to assign in kubeconfig.",
    )
    parser.add_argument(
        "--namespace",
        help="Namespace recorded with the context metadata.",
    )
    parser.add_argument(
        "--skip-ctx",
        action="store_true",
        help="Skip Prefect/Kubernetes context configuration.",
    )
    parser.add_argument(
        "--prefect-profile",
        help="Prefect profile name to configure.",
    )
    parser.add_argument(
        "--prefect-url",
        help="Explicit Prefect API URL (otherwise derived from tunnels or defaults).",
    )
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip environment file generation.",
    )
    parser.add_argument(
        "--env-target",
        help="Environment label passed to 'hotpass env --target'.",
    )
    parser.add_argument(
        "--force-env",
        action="store_true",
        help="Overwrite environment file if it already exists.",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Enable network enrichment flags in generated environment files.",
    )
    parser.add_argument(
        "--skip-arc",
        action="store_true",
        help="Skip ARC lifecycle verification wrapper.",
    )
    parser.add_argument("--arc-owner", help="GitHub organisation/user for ARC runs.")
    parser.add_argument("--arc-repository", help="GitHub repository for ARC runs.")
    parser.add_argument("--arc-scale-set", help="RunnerScaleSet name to verify.")
    parser.add_argument(
        "--arc-namespace",
        default="arc-runners",
        help="Namespace used when verifying ARC runners.",
    )
    parser.add_argument(
        "--arc-snapshot",
        help="Optional snapshot JSON passed to 'hotpass arc --snapshot'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the plan without executing.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the plan without prompting for confirmation.",
    )
    parser.add_argument(
        "--assume-yes",
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Assume yes when prompted (interactive mode only).",
    )
    parser.set_defaults(handler=_command_handler)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="setup",
        help="Guided setup wizard for staging and local operators",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    console = Console()
    interactive = _is_interactive(namespace, console)

    if not namespace.skip_prereqs:
        missing = _check_prerequisites(console)
        if missing:
            console.print(
                Panel(
                    "[red]Missing required commands:[/red] "
                    + ", ".join(sorted(missing))
                    + "\nInstall the tools above or rerun with --skip-prereqs.",
                    title="Prerequisite Check",
                    style="red",
                )
            )
            if not interactive:
                return 1
            if not namespace.assume_yes and not Confirm.ask(
                "Continue despite missing prerequisites?", default=False
            ):
                return 1

    plan = _build_plan(namespace, interactive, console)
    if not plan:
        console.print("[yellow]Nothing to do – all steps were skipped.[/yellow]")
        return 0

    _render_plan(plan, console)

    if namespace.dry_run:
        console.print("[green]Dry-run complete; no actions executed.[/green]")
        return 0

    if not namespace.execute:
        if interactive and (
            namespace.assume_yes or Confirm.ask("Execute this plan now?", default=True)
        ):
            pass
        else:
            console.print(
                "[cyan]Use --execute (or reply yes) to run the plan automatically.[/cyan]"
            )
            return 0

    try:
        _run_plan(plan, profile)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    write_state(
        "setup.json",
        {
            "preset": namespace.preset,
            "executed_at": datetime.now(tz=UTC).isoformat(),
            "steps": [step.title for step in plan],
        },
    )
    console.print("[green]Setup wizard completed successfully.[/green]")
    return 0


def _is_interactive(namespace: argparse.Namespace, console: Console) -> bool:
    interactive = getattr(namespace, "interactive", None)
    if interactive is not None:
        return bool(interactive)
    return bool(console.is_terminal)


def _check_prerequisites(console: Console) -> set[str]:
    required = {
        "uv": shutil.which("uv"),
        "prefect": shutil.which("prefect"),
        "aws": shutil.which("aws"),
        "kubectl": shutil.which("kubectl"),
        "ssh": shutil.which("ssh"),
    }
    table = Table(title="Prerequisite Check", show_header=True, header_style="bold cyan")
    table.add_column("Tool")
    table.add_column("Status")
    missing: set[str] = set()
    for tool, path in required.items():
        if path:
            table.add_row(tool, "[green]available[/green]")
        else:
            table.add_row(tool, "[red]missing[/red]")
            missing.add(tool)
    console.print(table)
    return missing


def _build_plan(
    namespace: argparse.Namespace,
    interactive: bool,
    console: Console,
) -> list[WizardStep]:
    plan: list[WizardStep] = []
    preset = namespace.preset or DEFAULT_PRESET

    extras = namespace.extras or _default_extras_for_preset(preset)
    if extras and not namespace.skip_deps:
        plan.append(
            WizardStep(
                title="Synchronise dependencies",
                summary=f"uv sync with extras: {' '.join(extras)}",
                shell_command=["bash", "ops/uv_sync_extras.sh"],
                env={"HOTPASS_UV_EXTRAS": " ".join(extras)},
            )
        )

    if not namespace.skip_tunnels:
        host = namespace.host or os.environ.get("HOTPASS_BASTION_HOST")
        if not host and interactive:
            host = Prompt.ask(
                "Bastion host or SSM target for tunnels",
                default=os.environ.get("HOTPASS_BASTION_HOST", "bastion.example.com"),
            )
        via = namespace.via or os.environ.get("HOTPASS_TUNNEL_VIA", DEFAULT_VIA)
        label = namespace.label or f"{preset}-wizard"
        if not host:
            console.print(
                "[red]Tunnel step skipped: provide --host or HOTPASS_BASTION_HOST "
                "when using --skip-tunnels=False.[/red]"
            )
        else:
            args = [
                "net",
                "up",
                "--via",
                via,
                "--host",
                host,
                "--label",
                label,
                "--detach",
            ]
            plan.append(
                WizardStep(
                    title="Open tunnels",
                    summary=f"hotpass net up via {via} ({host})",
                    cli_args=args,
                )
            )

    if not namespace.skip_aws:
        aws_profile = (
            namespace.aws_profile
            or os.environ.get("HOTPASS_AWS_PROFILE")
            or (DEFAULT_AWS_PROFILE if preset == "staging" else None)
        )
        aws_region = namespace.aws_region or os.environ.get("HOTPASS_AWS_REGION")
        aws_args = ["aws"]
        if aws_profile:
            aws_args.extend(["--profile", aws_profile])
        if aws_region:
            aws_args.extend(["--region", aws_region])
        eks_cluster = namespace.eks_cluster or (
            DEFAULT_EKS_CLUSTER if preset == "staging" else None
        )
        if eks_cluster:
            aws_args.extend(["--eks-cluster", eks_cluster, "--output", "text"])
        plan.append(
            WizardStep(
                title="Verify AWS credentials",
                summary="hotpass aws to confirm identity and optional EKS access",
                cli_args=aws_args,
            )
        )

    if not namespace.skip_ctx:
        prefect_profile = namespace.prefect_profile or (
            DEFAULT_PREFECT_PROFILE if preset == "staging" else "hotpass-local"
        )
        ctx_args = ["ctx", "init", "--prefect-profile", prefect_profile]
        if namespace.prefect_url:
            ctx_args.extend(["--prefect-url", namespace.prefect_url])
        if namespace.eks_cluster or preset == "staging":
            cluster = namespace.eks_cluster or DEFAULT_EKS_CLUSTER
            if cluster:
                ctx_args.extend(["--eks-cluster", cluster])
        if namespace.kube_context:
            ctx_args.extend(["--kube-context", namespace.kube_context])
        namespace_value = namespace.namespace or (
            DEFAULT_NAMESPACE if preset == "staging" else namespace.namespace
        )
        if namespace_value:
            ctx_args.extend(["--namespace", namespace_value])
        plan.append(
            WizardStep(
                title="Configure contexts",
                summary="hotpass ctx init to align Prefect and kube contexts",
                cli_args=ctx_args,
            )
        )

    if not namespace.skip_env:
        env_target = namespace.env_target or (
            DEFAULT_ENV_TARGET if preset == "staging" else namespace.env_target
        )
        env_args = ["env", "--target", env_target]
        if namespace.prefect_url:
            env_args.extend(["--prefect-url", namespace.prefect_url])
        if namespace.allow_network:
            env_args.append("--allow-network")
        if namespace.force_env:
            env_args.append("--force")
        plan.append(
            WizardStep(
                title="Write environment file",
                summary=f"hotpass env --target {env_target}",
                cli_args=env_args,
            )
        )

    if not namespace.skip_arc:
        owner = namespace.arc_owner or os.environ.get("HOTPASS_ARC_OWNER")
        repository = namespace.arc_repository or os.environ.get("HOTPASS_ARC_REPOSITORY")
        scale_set = namespace.arc_scale_set or os.environ.get("HOTPASS_ARC_SCALE_SET")
        snapshot = namespace.arc_snapshot

        if not (owner and repository and scale_set):
            console.print(
                "[yellow]ARC verification skipped. Provide --arc-owner, --arc-repository, "
                "and --arc-scale-set to include this step.[/yellow]"
            )
        else:
            arc_args = [
                "arc",
                "--owner",
                owner,
                "--repository",
                repository,
                "--scale-set",
                scale_set,
                "--namespace",
                namespace.arc_namespace or "arc-runners",
                "--store-summary",
            ]
            if namespace.aws_region:
                arc_args.extend(["--aws-region", namespace.aws_region])
            if namespace.aws_profile:
                arc_args.extend(["--aws-profile", namespace.aws_profile])
            if snapshot:
                arc_args.extend(["--snapshot", snapshot])
            plan.append(
                WizardStep(
                    title="Verify ARC lifecycle",
                    summary="hotpass arc wrapper",
                    cli_args=arc_args,
                )
            )

    plan.append(
        WizardStep(
            title="Review next steps",
            summary=(
                "Review AGENTS.md and docs/how-to-guides/manage-arc-runners.md for deeper "
                "workflows."
            ),
        )
    )

    return plan


def _default_extras_for_preset(preset: str) -> list[str]:
    if preset == "staging":
        return DEFAULT_EXTRAS_STAGING
    if preset == "local":
        return DEFAULT_EXTRAS_LOCAL
    return DEFAULT_EXTRAS_FALLBACK


def _render_plan(steps: Sequence[WizardStep], console: Console) -> None:
    table = Table(title="Setup Plan", show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Step")
    table.add_column("Command / Notes")
    for idx, step in enumerate(steps, start=1):
        table.add_row(str(idx), step.title, step.display_command())
    console.print(table)


def _run_plan(steps: Sequence[WizardStep], profile: CLIProfile | None) -> None:
    for idx, step in enumerate(steps, start=1):
        if step.cli_args is None and step.shell_command is None:
            continue
        if step.shell_command:
            try:
                run_command(step.shell_command, check=True, env={**os.environ, **step.env})
            except CommandExecutionError as exc:
                raise RuntimeError(f"Step {idx} failed: {exc}") from exc
            continue
        if step.cli_args:
            exit_code = _invoke_cli(step.cli_args, profile)
            if exit_code != 0:
                raise RuntimeError(
                    f"Step {idx} failed with exit code {exit_code}: {' '.join(step.cli_args)}"
                )


def _invoke_cli(cli_args: list[str], profile: CLIProfile | None) -> int:
    from ..main import build_parser as build_root_parser  # local import to avoid heavy startup cost

    parser = build_root_parser()
    parsed = parser.parse_args(cli_args)
    raw_handler = getattr(parsed, "handler", None)
    if not callable(raw_handler):
        raise RuntimeError(f"No handler found for CLI args: {' '.join(cli_args)}")
    handler = cast(CommandHandler, raw_handler)
    result = handler(parsed, profile)
    return int(result)


__all__ = ["register", "build"]
