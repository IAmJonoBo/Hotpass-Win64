from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

pytest.importorskip("stdnum")

from hotpass import cli


def _contract_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "contracts" / "hotpass-cli-contract.yaml"
        if candidate.exists():
            return candidate
    msg = "Unable to locate CLI contract specification"
    raise FileNotFoundError(msg)


def load_contract() -> dict[str, Any]:
    with open(_contract_path(), encoding="utf-8") as handle:
        return cast(dict[str, Any], yaml.safe_load(handle))


def _get_subparsers(
    parser: argparse.ArgumentParser,
) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    msg = "Parser does not define subcommands"
    raise AssertionError(msg)


def _extract_options(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    actions: list[argparse.Action] = []
    for group in parser._action_groups:
        actions.extend(group._group_actions)
    return {action.option_strings[0]: action for action in actions if action.option_strings}


def test_cli_contract_matches_spec() -> None:
    contract = load_contract()
    parser = cli.build_parser()

    expected_default = contract.get("default_subcommand")
    args = parser.parse_args([])
    assert args.command == expected_default

    subparsers = _get_subparsers(parser)

    for command_spec in contract["subcommands"]:
        name = command_spec["name"]
        assert name in subparsers, f"Subcommand {name} missing from parser"
        subparser = subparsers[name]
        options = _extract_options(subparser)

        for option in command_spec.get("options", []):
            opt_name = option["name"]
            assert opt_name in options, f"Option {opt_name} missing from subcommand {name}"
            action = options[opt_name]
            required = option.get("required", False)
            assert action.required == required
