"""Composable CLI builder used to assemble the unified Hotpass command surface."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import shared


@dataclass(slots=True)
class SharedParsers:
    """Parent parsers shared across individual command registrations."""

    base: argparse.ArgumentParser = field(default_factory=shared.make_base_parser)
    pipeline: argparse.ArgumentParser = field(default_factory=shared.make_pipeline_parser)
    reporting: argparse.ArgumentParser = field(default_factory=shared.make_reporting_parser)
    excel: argparse.ArgumentParser = field(default_factory=shared.make_excel_parser)


CommandHandler = Callable[[argparse.Namespace, Any], int]


@dataclass(slots=True)
class CLICommand:
    """Represents a subcommand registered with the CLI builder."""

    name: str
    help: str
    builder: Callable[
        [argparse._SubParsersAction[argparse.ArgumentParser], SharedParsers],
        argparse.ArgumentParser,
    ]
    handler: CommandHandler
    is_default: bool = False


class CLIBuilder:
    """Aggregate shared option parsers and command registrations."""

    def __init__(self, *, description: str | None = None, epilog: str | None = None) -> None:
        self.description = description
        self.epilog = epilog
        self.shared = SharedParsers()
        self._commands: list[CLICommand] = []

    def register(self, command: CLICommand) -> None:
        self._commands.append(command)

    def build(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="hotpass",
            description=self.description,
            epilog=self.epilog,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        subparsers = parser.add_subparsers(dest="command")
        default_handler: CommandHandler | None = None
        default_command: str | None = None

        for command in self._commands:
            subparser = command.builder(subparsers, self.shared)
            subparser.set_defaults(handler=command.handler, command=command.name)
            if command.is_default:
                default_handler = command.handler
                default_command = command.name

        if default_handler is not None:
            parser.set_defaults(handler=default_handler, command=default_command)

        return parser


__all__ = ["CLIBuilder", "CLICommand", "SharedParsers", "CommandHandler"]
