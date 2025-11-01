"""Implementation of the `hotpass deploy` subcommand."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from hotpass.prefect import deployments as prefect_deployments

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..progress import DEFAULT_SENSITIVE_FIELD_TOKENS, StructuredLogger
from ..shared import normalise_sensitive_fields


@dataclass(slots=True)
class DeployOptions:
    flows: tuple[str, ...]
    manifest_dir: Path | None
    build_image: bool
    push_image: bool
    log_format: str
    sensitive_fields: tuple[str, ...]
    deployment_name: str | None
    schedule: str | None
    disable_schedule: bool
    work_pool: str | None


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "deploy",
        help="Deploy the Hotpass pipeline to Prefect",
        description="Apply Prefect deployment manifests shipped with the repository.",
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--flow",
        dest="flows",
        action="append",
        help="Identifier of a Prefect deployment manifest to apply (may be repeated).",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=None,
        help="Directory containing Prefect deployment manifests (defaults to ./prefect).",
    )
    parser.add_argument(
        "--build-image",
        action="store_true",
        help="Build the Prefect deployment image before registering.",
    )
    parser.add_argument(
        "--push-image",
        action="store_true",
        help="Push the built image to the configured registry.",
    )
    parser.add_argument(
        "--name",
        dest="deployment_name",
        help="Override the Prefect deployment name for selected manifests.",
    )
    parser.add_argument(
        "--schedule",
        help=(
            "Cron schedule applied to selected deployments (UTC). Use 'none' to disable scheduling."
        ),
    )
    parser.add_argument(
        "--work-pool",
        dest="work_pool",
        help="Prefect work pool name to register deployments against.",
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="deploy",
        help="Deploy the Hotpass pipeline",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    options = _resolve_options(namespace, profile)
    logger = StructuredLogger(options.log_format, options.sensitive_fields)
    console = logger.console if options.log_format == "rich" else None

    if console:
        console.print("[bold cyan]Applying Prefect deployments...[/bold cyan]")
        if options.flows:
            console.print(f"[dim]Selected flows:[/dim] {', '.join(sorted(options.flows))}")
        if options.manifest_dir:
            console.print(f"[dim]Manifest directory:[/dim] {options.manifest_dir}")
        console.print(
            f"[dim]Build image:[/dim] {'yes' if options.build_image else 'no'}",
        )
        console.print(
            f"[dim]Push image:[/dim] {'yes' if options.push_image else 'no'}",
        )
        if options.deployment_name:
            console.print(f"[dim]Deployment name:[/dim] {options.deployment_name}")
        if options.disable_schedule:
            console.print("[dim]Schedule:[/dim] disabled")
        elif options.schedule:
            console.print(f"[dim]Schedule:[/dim] {options.schedule}")
        if options.work_pool:
            console.print(f"[dim]Work pool:[/dim] {options.work_pool}")

    try:
        deployment_ids = prefect_deployments.deploy_pipeline(
            flows=options.flows or None,
            base_dir=options.manifest_dir,
            build_image=options.build_image,
            push_image=options.push_image,
            deployment_name=options.deployment_name,
            schedule=options.schedule,
            disable_schedule=options.disable_schedule,
            work_pool=options.work_pool,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.log_error(f"Deployment failed: {exc}")
        return 1

    logger.log_event(
        "deploy.completed",
        {
            "flows": options.flows,
            "manifest_dir": str(options.manifest_dir) if options.manifest_dir else None,
            "build_image": options.build_image,
            "push_image": options.push_image,
            "deployment_name": options.deployment_name,
            "schedule": options.schedule,
            "disable_schedule": options.disable_schedule,
            "work_pool": options.work_pool,
            "deployment_ids": deployment_ids,
        },
    )
    if console:
        if deployment_ids:
            console.print(
                "[bold green]✓[/bold green] Prefect deployments registered: "
                + ", ".join(str(value) for value in deployment_ids)
            )
        else:
            console.print("[bold yellow]No deployments matched the provided filters.[/bold yellow]")
    return 0


def _resolve_options(namespace: argparse.Namespace, profile: CLIProfile | None) -> DeployOptions:
    log_format_value: str | None = getattr(namespace, "log_format", None)
    if log_format_value is None and profile is not None:
        log_format_value = profile.log_format
    log_format = (log_format_value or "rich").lower()
    if log_format not in {"json", "rich"}:
        msg = f"Unsupported log format: {log_format}"
        raise ValueError(msg)

    raw_sensitive = getattr(namespace, "sensitive_fields", None)
    if raw_sensitive is None and profile is not None:
        raw_sensitive = profile.options.get("sensitive_fields")
    sensitive_iter: Iterable[str] | None = None
    if isinstance(raw_sensitive, str):
        sensitive_iter = [raw_sensitive]
    elif isinstance(raw_sensitive, Iterable):
        sensitive_iter = [str(value) for value in raw_sensitive if value is not None]
    elif raw_sensitive is not None:
        sensitive_iter = [str(raw_sensitive)]
    sensitive_fields = normalise_sensitive_fields(sensitive_iter, DEFAULT_SENSITIVE_FIELD_TOKENS)

    flows_value = getattr(namespace, "flows", None)
    flows: tuple[str, ...] = tuple(str(value) for value in flows_value or ())

    manifest_dir = getattr(namespace, "manifest_dir", None)
    manifest_path: Path | None = None
    if manifest_dir:
        manifest_path = Path(manifest_dir)

    raw_schedule = getattr(namespace, "schedule", None)
    disable_schedule = False
    schedule_value: str | None = None
    if raw_schedule is not None:
        normalised = raw_schedule.strip()
        if not normalised or normalised.lower() in {"none", "off"}:
            disable_schedule = True
            schedule_value = None
        else:
            schedule_value = normalised

    return DeployOptions(
        flows=flows,
        manifest_dir=manifest_path,
        build_image=bool(getattr(namespace, "build_image", False)),
        push_image=bool(getattr(namespace, "push_image", False)),
        log_format=log_format,
        sensitive_fields=sensitive_fields,
        deployment_name=getattr(namespace, "deployment_name", None),
        schedule=schedule_value,
        disable_schedule=disable_schedule,
        work_pool=getattr(namespace, "work_pool", None),
    )


__all__ = ["register", "build"]
