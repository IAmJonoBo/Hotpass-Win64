"""Entry point for the unified Hotpass CLI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

# Ensure repository-local automation packages (ops/*) are importable when the CLI is
# executed via the installed entry point (uv run hotpass ...).
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from .builder import CLIBuilder
from .commands import (
    arc,
    aws,
    backfill,
    contracts,
    crawl,
    ctx,
    dashboard,
    deploy,
    distro,
    doctor,
    enrich,
    env,
    explain_provenance,
    imports,
    init,
    inventory,
    net,
    orchestrate,
    overview,
    plan,
    qa,
    refine,
    resolve,
    run,
    setup,
    version,
)
from .configuration import (
    DEFAULT_PROFILE_DIRS,
    CLIProfile,
    ProfileIntentError,
    ProfileNotFoundError,
    ProfileValidationError,
    load_profile,
)

EPILOG = (
    "Profiles may be defined as TOML or YAML files. Use --profile-search-path to locate "
    "custom profiles."
)


class CommandHandler(Protocol):
    """Callable interface implemented by CLI subcommand handlers."""

    def __call__(self, args: argparse.Namespace, profile: CLIProfile | None) -> int: ...


def build_parser() -> argparse.ArgumentParser:
    builder = CLIBuilder(
        description="Hotpass CLI",
        epilog=EPILOG,
    )
    # Register new UPGRADE.md commands first
    builder.register(overview.register())
    builder.register(refine.register())
    builder.register(enrich.register())
    builder.register(explain_provenance.register())
    builder.register(qa.register())
    builder.register(contracts.register())
    builder.register(imports.register())
    builder.register(inventory.register())
    builder.register(plan.register())
    builder.register(crawl.register())
    builder.register(setup.register())
    builder.register(net.register())
    builder.register(aws.register())
    builder.register(ctx.register())
    builder.register(env.register())
    builder.register(arc.register())
    builder.register(distro.register())

    # Register existing commands
    builder.register(run.register())
    builder.register(backfill.register())
    builder.register(doctor.register())
    builder.register(orchestrate.register())
    builder.register(resolve.register())
    builder.register(dashboard.register())
    builder.register(deploy.register())
    builder.register(init.register())
    builder.register(version.register())
    parser = builder.build()
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = cast(CommandHandler | None, getattr(args, "handler", None))
    if handler is None:
        parser.print_help()
        return 1

    try:
        profile = _load_profile(args)
    except (ProfileNotFoundError, ProfileValidationError, ProfileIntentError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    return handler(args, profile)


def _load_profile(args: argparse.Namespace) -> CLIProfile | None:
    identifier = getattr(args, "profile", None)
    if not identifier:
        return None

    search_paths: list[Path] = []
    raw_search_paths = getattr(args, "profile_search_paths", None)
    if raw_search_paths:
        search_paths.extend(Path(path) for path in raw_search_paths)
    search_paths.extend(DEFAULT_PROFILE_DIRS)

    return load_profile(identifier, search_paths=search_paths)


__all__ = ["build_parser", "main"]
