from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile

SAMPLE_CONFIG = dedent(
    """
    # config/pipeline.quickstart.toml
    [pipeline]
    input_dir = "./data"
    output_path = "./dist/refined.xlsx"
    archive = true
    dist_dir = "./dist"

    [governance]
    intent = ["Bootstrap Hotpass workspace"]
    data_owner = "Data Governance"
    classification = "internal"
    """
).strip()

SAMPLE_PROFILE = dedent(
    """
    # config/profiles/quickstart.toml
    name = "quickstart"
    summary = "Sample profile aligned with the quickstart tutorial"
    expectation_suite = "default"
    country_code = "ZA"
    log_format = "rich"

    [features]
    compliance = false
    enrichment = false
    geospatial = false
    dashboards = false
    """
).strip()

SAMPLE_PREFECT_DEPLOYMENT = dedent(
    """
    # prefect/deployments/quickstart.yaml
    name: hotpass-quickstart
    description: Bootstrap deployment that exercises the sample configuration.
    flow_name: hotpass.quickstart
    entrypoint: ops/process_data.py:main
    parameters:
      config_path: "./config/pipeline.quickstart.toml"
      profile: "quickstart"
    actions:
      - name: run-hotpass
        command: "uv run hotpass run --config ./config/pipeline.quickstart.toml --archive"
      - name: verify-environment
        command: "uv run hotpass doctor --config ./config/pipeline.quickstart.toml"
    """
).strip()

SAMPLE_DATA_README = dedent(
    """
    # data/README.md
    The `hotpass init` command created this directory so you can drop spreadsheets in
    before running the pipeline. Copy one of the anonymised fixtures from the Hotpass
    repository or place your own workbook here.
    """
).strip()


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "init",
        help="Bootstrap a project workspace with sample configuration",
        description=(
            "Create configuration, profile, and Prefect deployment scaffolding in the "
            "target directory. Use --force to overwrite existing files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Destination directory for the bootstrap workspace",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files when the target directory already exists",
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="init",
        help="Bootstrap a project workspace with sample configuration",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    del profile  # Unused; profiles are not applied during bootstrap.

    target = Path(namespace.path).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not namespace.force:
        print(
            "Error: target directory is not empty. Re-run with --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    target.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    created.extend(_ensure_directories(target))
    created.extend(
        path
        for path, wrote in (
            _write_file(
                target / "config" / "pipeline.quickstart.toml",
                SAMPLE_CONFIG,
                namespace.force,
            ),
            _write_file(
                target / "config" / "profiles" / "quickstart.toml",
                SAMPLE_PROFILE,
                namespace.force,
            ),
            _write_file(
                target / "prefect" / "deployments" / "quickstart.yaml",
                SAMPLE_PREFECT_DEPLOYMENT,
                namespace.force,
            ),
            _write_file(target / "data" / "README.md", SAMPLE_DATA_README, namespace.force),
        )
        if wrote
    )

    print(f"Hotpass workspace initialised at {target}")
    if created:
        print("Generated artefacts:")
        for path in created:
            print(f"  - {path.relative_to(target)}")
    return 0


def _ensure_directories(target: Path) -> list[Path]:
    directories = [
        target / "config",
        target / "config" / "profiles",
        target / "data",
        target / "dist",
        target / "prefect",
        target / "prefect" / "deployments",
    ]
    created: list[Path] = []
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    return created


def _write_file(path: Path, content: str, force: bool) -> tuple[Path, bool]:
    if path.exists() and not force:
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{content}\n", encoding="utf-8")
    return path, True


__all__ = ["register", "build"]
