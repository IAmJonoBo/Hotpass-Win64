from __future__ import annotations

import argparse
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm

DEFAULT_EXTRAS = ["dev", "docs"]


@dataclass
class BootstrapStep:
    description: str
    command: list[str] | None = None
    action: Callable[[bool, Console], int] | None = None
    dry_run_message: str | None = None

    def run(self, execute: bool, console: Console) -> int:
        if self.action is not None:
            return self.action(execute, console)
        if not self.command:
            return 0
        if not execute:
            hint = self.dry_run_message or " ".join(self.command)
            console.print(f"[cyan]{self.description}[/cyan]: {hint}")
            return 0
        result = subprocess.run(self.command, check=False)  # nosec B603
        if result.returncode != 0:
            console.print(
                f"[red]Step failed:[/red] {' '.join(self.command)} (exit {result.returncode})"
            )
        return result.returncode


def build_bootstrap_plan(
    extras: Iterable[str],
    prefect_profile: str,
    env_file: Path,
    vault_address: str | None,
) -> list[BootstrapStep]:
    extras_flags: list[str] = []
    for extra in extras:
        extras_flags.extend(["--extra", extra])

    def _write_env_file(execute: bool, console: Console) -> int:
        if not execute:
            console.print(f"[cyan]Seed environment file[/cyan]: would write {env_file}")
            return 0
        env_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"HOTPASS_PREFECT_PROFILE={prefect_profile}"]
        if vault_address:
            lines.append(f"HOTPASS_VAULT_ADDR={vault_address}")
        else:
            lines.append("HOTPASS_VAULT_ADDR=https://vault.internal")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        console.print(f"[green]Seeded environment file:[/green] {env_file}")
        return 0

    return [
        BootstrapStep(
            description="Create uv virtual environment",
            command=["uv", "venv"],
            dry_run_message="uv venv",
        ),
        BootstrapStep(
            description="Synchronise dependencies with extras",
            command=["uv", "sync", *extras_flags],
            dry_run_message="uv sync " + " ".join(extras_flags),
        ),
        BootstrapStep(
            description="Create Prefect profile",
            command=["prefect", "profile", "create", prefect_profile, "--overwrite"],
        ),
        BootstrapStep(
            description="Seed environment configuration",
            action=_write_env_file,
        ),
        BootstrapStep(
            description="Generate SBOM",
            command=["uv", "run", "python", "ops/supply_chain/generate_sbom.py"],
            dry_run_message="uv run python ops/supply_chain/generate_sbom.py",
        ),
        BootstrapStep(
            description="Generate provenance statement",
            command=[
                "uv",
                "run",
                "python",
                "ops/supply_chain/generate_provenance.py",
            ],
            dry_run_message="uv run python ops/supply_chain/generate_provenance.py",
        ),
    ]


def check_prerequisites(console: Console) -> bool:
    missing = [tool for tool in ("uv", "prefect") if shutil.which(tool) is None]
    if missing:
        console.print(
            "[red]Missing required tooling:[/red] " + ", ".join(sorted(missing)),
        )
        console.print("Install the missing commands and retry the bootstrap.")
        return False
    return True


def execute_plan(steps: list[BootstrapStep], *, execute: bool, console: Console) -> int:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        for step in steps:
            task_id = progress.add_task(step.description, total=1)
            exit_code = step.run(execute, console)
            progress.update(task_id, completed=1)
            if exit_code != 0:
                return exit_code
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Hotpass developer environments")
    parser.add_argument(
        "--extras",
        action="append",
        help="Additional uv extras to install (default: dev, docs)",
    )
    parser.add_argument(
        "--prefect-profile",
        default="hotpass-dev",
        help="Prefect profile name to create",
    )
    parser.add_argument(
        "--vault-address",
        help="Vault address to include in the generated environment file",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env.hotpass"),
        help="Target environment file to create",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute commands instead of printing the plan",
    )
    parser.add_argument(
        "--assume-yes",
        action="store_true",
        help="Skip confirmation prompts when running with --execute",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    console = Console()

    extras = args.extras or DEFAULT_EXTRAS
    plan = build_bootstrap_plan(extras, args.prefect_profile, args.env_file, args.vault_address)

    console.print("[bold]Hotpass bootstrap plan[/bold]")
    for step in plan:
        if step.command:
            console.print(f" • {step.description}: {' '.join(step.command)}")
        else:
            console.print(f" • {step.description}")

    if args.execute:
        if not check_prerequisites(console):
            return 1
        if not args.assume_yes and sys.stdin.isatty():
            confirmed = Confirm.ask("Proceed with executing the bootstrap plan?", default=True)
            if not confirmed:
                console.print("[yellow]Bootstrap aborted by user.[/yellow]")
                return 0

    return execute_plan(plan, execute=args.execute, console=console)


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
