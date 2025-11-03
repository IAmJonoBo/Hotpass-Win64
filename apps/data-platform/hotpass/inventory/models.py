from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Asset(BaseModel):
    """Represents a single asset entry from the inventory manifest."""

    id: str
    name: str
    type: str
    location: str
    classification: str
    owner: str
    custodian: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)

    @field_validator("dependencies", "controls", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> list[str]:  # pragma: no cover - validation hook
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        return [str(value)]


class InventoryManifest(BaseModel):
    """Typed representation of the asset inventory manifest."""

    version: str
    maintainer: str
    review_cadence: str
    assets: list[Asset]

    @field_validator("version", "maintainer", "review_cadence", mode="before")
    @classmethod
    def _coerce_to_str(cls, value: Any) -> str:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, (str, int, float)):
            text = str(value).strip()
            if not text:
                raise ValueError("value must not be empty")
            return text
        if value is None:
            raise ValueError("value is required")
        return str(value)


@dataclass(slots=True)
class InventorySummary:
    """Aggregated statistics for the current inventory snapshot."""

    total_assets: int
    by_type: dict[str, int]
    by_classification: dict[str, int]

    @classmethod
    def from_assets(cls, assets: Iterable[Asset]) -> InventorySummary:
        asset_list = list(assets)
        by_type: dict[str, int] = {}
        by_classification: dict[str, int] = {}

        for asset in asset_list:
            by_type[asset.type] = by_type.get(asset.type, 0) + 1
            by_classification[asset.classification] = (
                by_classification.get(asset.classification, 0) + 1
            )
        return cls(
            total_assets=len(asset_list),
            by_type=dict(sorted(by_type.items())),
            by_classification=dict(sorted(by_classification.items())),
        )
