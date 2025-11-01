"""Explain provenance metadata for rows in enriched datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile

PROVENANCE_COLUMNS = [
    "provenance_source",
    "provenance_timestamp",
    "provenance_confidence",
    "provenance_strategy",
    "provenance_network_status",
]


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    """Register the explain-provenance command."""
    parser = subparsers.add_parser(
        "explain-provenance",
        help="Inspect provenance metadata for a specific row",
        description=(
            "Display provenance columns for a given row in an enriched workbook. "
            "Supports Excel (.xlsx/.xlsm/.xls) and CSV inputs."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to the enriched dataset (Excel or CSV)",
    )
    parser.add_argument(
        "--row-id",
        required=True,
        help="Row index (0-based) or identifier from the dataset's 'id' column",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit provenance details as JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON output to this file (implies --json when set)",
    )
    parser.set_defaults(handler=_command_handler)
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="explain-provenance",
        help="Explain provenance metadata for dataset rows",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    """Handle explain-provenance execution."""
    console = Console()
    _ = profile  # unused; provenance is dataset-driven

    dataset = namespace.dataset
    row_identifier = namespace.row_id
    as_json = namespace.json or namespace.output is not None

    try:
        frame = _load_dataset(dataset)
        row_index, row = _locate_row(frame, row_identifier)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    payload = _build_payload(row_identifier, row_index, row)

    if namespace.output:
        namespace.output.parent.mkdir(parents=True, exist_ok=True)

    if as_json:
        output_text = json.dumps(payload, indent=2)
        if namespace.output:
            namespace.output.write_text(output_text, encoding="utf-8")
        console.print(output_text)
    else:
        _render_table(console, payload)

    return 0 if payload.get("provenance") else 2


def _load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise ValueError(f"Dataset not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported dataset type for provenance inspection: {path}")


def _locate_row(frame: pd.DataFrame, row_identifier: str) -> tuple[int, pd.Series]:
    if frame.empty:
        raise ValueError("Dataset is empty; cannot explain provenance")

    try:
        index = int(row_identifier)
        if index < 0 or index >= len(frame):
            raise ValueError(f"Row index {index} out of range (dataset has {len(frame)} rows)")
        return index, frame.iloc[index]
    except ValueError:
        pass

    if "id" in frame.columns:
        matches = frame[frame["id"].astype(str) == row_identifier]
        if not matches.empty:
            index = int(matches.index[0])
            return index, matches.iloc[0]

    raise ValueError(f"Unable to locate row '{row_identifier}' in dataset")


def _build_payload(row_identifier: str, row_index: int, row: pd.Series) -> dict[str, Any]:
    provenance = {
        column: str(row.get(column, "N/A")) for column in PROVENANCE_COLUMNS if column in row.index
    }
    payload: dict[str, Any] = {
        "success": bool(provenance),
        "row_id": row_identifier,
        "row_index": row_index,
        "organization_name": str(row.get("organization_name", "N/A")),
    }
    if provenance:
        payload["provenance"] = provenance
    else:
        payload["message"] = "No provenance columns present in dataset"
    return payload


def _render_table(console: Console, payload: dict[str, Any]) -> None:
    console.print(
        f"[cyan]Row:[/cyan] {payload.get('row_id')} "
        f"(index {payload.get('row_index')}, organization "
        f"{payload.get('organization_name')})"
    )
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        console.print("[yellow]No provenance metadata found[/yellow]")
        return

    table = Table(title="Provenance details")
    table.add_column("Field", style="magenta")
    table.add_column("Value", style="white")
    for key, value in provenance.items():
        table.add_row(key, str(value))
    console.print(table)
