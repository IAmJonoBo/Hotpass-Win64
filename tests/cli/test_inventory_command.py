from __future__ import annotations

from typing import cast

import pytest

from hotpass import cli
from hotpass.cli.builder import CommandHandler
from tests.helpers.assertions import expect


def _invoke(argv: list[str]) -> int:
    parser = cli.build_parser()
    args = parser.parse_args(argv)
    handler = cast(CommandHandler | None, getattr(args, "handler", None))
    expect(handler is not None, "inventory command should resolve to a handler")
    return handler(args, None)


def test_inventory_list_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = _invoke(["inventory", "list", "--json"])
    captured = capsys.readouterr()

    expect(exit_code == 0, "inventory list --json should succeed")
    expect("\"manifest\"" in captured.out, "JSON output should include manifest metadata")
    expect("\"assets\"" in captured.out, "JSON output should include asset list")


def test_inventory_list_table_output(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = _invoke(["inventory", "list"])
    captured = capsys.readouterr()

    expect(exit_code == 0, "inventory list should succeed")
    expect("Asset inventory" in captured.out, "table output should include heading")
    expect("Total assets:" in captured.out, "table output should include summary")


def test_inventory_status_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = _invoke(["inventory", "status", "--json"])
    captured = capsys.readouterr()

    expect(exit_code == 0, "inventory status --json should succeed")
    expect("\"requirements\"" in captured.out, "JSON output should include requirements")
