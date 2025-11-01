"""Dataset contract registry and helpers for Hotpass."""

from __future__ import annotations

from .datasets import DATASET_BY_NAME, DATASET_CONTRACTS
from .generator import regenerate_json_schemas, regenerate_reference_doc
from .types import ContractRowModel, DatasetContract, FieldContract, render_reference_markdown

__all__ = [
    "ContractRowModel",
    "DatasetContract",
    "FieldContract",
    "DATASET_CONTRACTS",
    "DATASET_BY_NAME",
    "get_contract",
    "regenerate_json_schemas",
    "regenerate_reference_doc",
    "render_reference_markdown",
]


def get_contract(name: str) -> DatasetContract:
    """Return the dataset contract registered under ``name``."""

    try:
        return DATASET_BY_NAME[name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown dataset contract: {name}") from exc
