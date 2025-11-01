from __future__ import annotations

import importlib
import sys
import argparse
from pathlib import Path
from types import ModuleType
from typing import cast

from pytest import CaptureFixture

from tests.helpers.assertions import expect

CLI_DIR = Path(__file__).resolve().parents[2] / "apps/data-platform/hotpass/cli"
HOTPASS_DIR = CLI_DIR.parent


def _bootstrap_cli_namespace() -> None:
    if "hotpass" not in sys.modules:
        pkg = ModuleType("hotpass")
        pkg.__path__ = [str(HOTPASS_DIR)]
        sys.modules["hotpass"] = pkg
    if "hotpass.cli" not in sys.modules:
        cli_pkg = ModuleType("hotpass.cli")
        cli_pkg.__path__ = [str(CLI_DIR)]
        sys.modules["hotpass.cli"] = cli_pkg
    if "hotpass.cli.commands" not in sys.modules:
        commands_pkg = ModuleType("hotpass.cli.commands")
        commands_pkg.__path__ = [str(CLI_DIR / "commands")]
        sys.modules["hotpass.cli.commands"] = commands_pkg


def _load_setup_parser() -> argparse.ArgumentParser:
    _bootstrap_cli_namespace()
    builder_module = importlib.import_module("hotpass.cli.builder")
    setup_module = importlib.import_module("hotpass.cli.commands.setup")
    builder = builder_module.CLIBuilder(description="Hotpass CLI", epilog=None)
    builder.register(setup_module.register())
    return cast(argparse.ArgumentParser, builder.build())


_SETUP_PARSER = _load_setup_parser()


def _run_setup(args: list[str]) -> int:
    parser = _SETUP_PARSER
    parsed = parser.parse_args(args)
    from hotpass.cli.builder import CommandHandler  # imported lazily after bootstrap

    handler_obj = getattr(parsed, "handler", None)
    if not callable(handler_obj):
        raise AssertionError("Parsed setup command should include a handler")
    handler = cast(CommandHandler, handler_obj)
    return int(handler(parsed, None))


def test_setup_wizard_dry_run_minimal(capsys: CaptureFixture[str]) -> None:
    exit_code = _run_setup(
        [
            "setup",
            "--skip-prereqs",
            "--skip-deps",
            "--skip-tunnels",
            "--skip-aws",
            "--skip-ctx",
            "--skip-env",
            "--skip-arc",
            "--dry-run",
        ]
    )
    expect(
        exit_code == 0,
        "Dry-run should complete successfully when all steps are skipped",
    )
    out = capsys.readouterr().out
    expect("Setup Plan" in out, "Wizard should render a plan table during dry-run")


def test_setup_wizard_renders_env_step(capsys: CaptureFixture[str]) -> None:
    exit_code = _run_setup(
        [
            "setup",
            "--skip-prereqs",
            "--skip-deps",
            "--skip-tunnels",
            "--skip-aws",
            "--skip-arc",
            "--prefect-profile",
            "demo-profile",
            "--env-target",
            "demo",
            "--dry-run",
        ]
    )
    expect(exit_code == 0, "Dry-run should succeed when env step is requested")
    out = capsys.readouterr().out
    expect(
        "hotpass env --target demo" in out,
        "Plan should include environment generation step with the requested target",
    )
