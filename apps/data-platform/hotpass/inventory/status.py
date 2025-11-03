from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from .service import InventoryService

_DEFAULT_STATUS_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "inventory" / "feature-status.yaml"
)


class FeatureState(str, Enum):
    IMPLEMENTED = "implemented"
    PLANNED = "planned"
    MISSING = "missing"
    DEGRADED = "degraded"


@dataclass(slots=True)
class InventoryFeatureRequirement:
    id: str
    surface: str
    description: str
    status: FeatureState
    detail: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "surface": self.surface,
            "description": self.description,
            "status": self.status.value,
            "detail": self.detail,
        }


def _load_status_path(path: str | os.PathLike[str] | None) -> Path:
    candidate = (
        Path(path)
        if path is not None
        else Path(os.getenv("HOTPASS_INVENTORY_FEATURE_STATUS_PATH", _DEFAULT_STATUS_PATH))
    )
    return candidate.expanduser().resolve()


def _parse_requirements(payload: dict[str, object]) -> list[InventoryFeatureRequirement]:
    raw_requirements = payload.get("requirements", [])
    requirements: list[InventoryFeatureRequirement] = []

    if not isinstance(raw_requirements, Iterable):
        return requirements

    for raw in raw_requirements:
        if not isinstance(raw, dict):
            continue
        status = raw.get("status", FeatureState.PLANNED.value)
        try:
            feature_state = FeatureState(str(status))
        except ValueError:
            feature_state = FeatureState.PLANNED
        requirements.append(
            InventoryFeatureRequirement(
                id=str(raw.get("id", "unknown")),
                surface=str(raw.get("surface", "unknown")),
                description=str(raw.get("description", "")),
                status=feature_state,
                detail=(str(raw.get("detail")) if raw.get("detail") is not None else None),
            )
        )
    return requirements


def load_feature_requirements(
    *,
    service: InventoryService | None = None,
    status_path: str | os.PathLike[str] | None = None,
) -> list[InventoryFeatureRequirement]:
    """Load feature requirements and adjust their status based on current data."""

    service = service or InventoryService()
    requirements_path = _load_status_path(status_path)

    if not requirements_path.exists():
        raise FileNotFoundError(
            f"Inventory feature status file not found at {requirements_path}. "
            "Set HOTPASS_INVENTORY_FEATURE_STATUS_PATH to override."
        )

    with requirements_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    requirements = _parse_requirements(payload)

    # Adjust backend-related requirement if the manifest is missing or empty.
    backend_ids = {"backend-service", "backend"}
    manifest_error: str | None = None
    try:
        manifest = service.load_manifest()
        if not manifest.assets:
            manifest_error = "Inventory manifest contains no assets"
    except FileNotFoundError as exc:
        manifest_error = str(exc)
    except ValueError as exc:
        manifest_error = str(exc)

    if manifest_error:
        for requirement in requirements:
            if requirement.id in backend_ids or requirement.surface.lower() == "backend":
                requirement.status = FeatureState.DEGRADED
                requirement.detail = manifest_error
                break
        else:
            requirements.append(
                InventoryFeatureRequirement(
                    id="backend",
                    surface="backend",
                    description="Inventory manifest is available",
                    status=FeatureState.DEGRADED,
                    detail=manifest_error,
                )
            )

    return requirements


__all__ = [
    "FeatureState",
    "InventoryFeatureRequirement",
    "load_feature_requirements",
]
