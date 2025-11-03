from __future__ import annotations

from pathlib import Path

from hotpass.inventory import FeatureState, InventoryService, load_feature_requirements
from tests.helpers.assertions import expect


STATUS_FILE = """
requirements:
  - id: backend-service
    surface: backend
    description: Backend loader
    status: implemented
  - id: cli
    surface: cli
    description: CLI command available
    status: implemented
"""

MANIFEST = """
version: 2025-11-18
maintainer: Platform
review_cadence: quarterly
assets:
  - id: storage
    name: Storage Bucket
    type: filesystem
    location: ./data
    classification: confidential
    owner: Data
    custodian: Platform
    description: Core dataset storage
"""


def test_load_feature_requirements_with_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "asset-register.yaml"
    status_path = tmp_path / "feature-status.yaml"
    manifest_path.write_text(MANIFEST)
    status_path.write_text(STATUS_FILE)

    service = InventoryService(manifest_path=manifest_path, cache_ttl=0)
    requirements = load_feature_requirements(service=service, status_path=status_path)

    expect(len(requirements) == 2, "two requirements should be loaded from status file")
    expect(
        requirements[0].status == FeatureState.IMPLEMENTED,
        "backend requirement should report implemented when manifest is present",
    )


def test_load_feature_requirements_degraded_when_manifest_missing(tmp_path: Path) -> None:
    status_path = tmp_path / "feature-status.yaml"
    status_path.write_text(STATUS_FILE)

    service = InventoryService(manifest_path=tmp_path / "missing.yaml", cache_ttl=0)
    requirements = load_feature_requirements(service=service, status_path=status_path)

    backend = next(req for req in requirements if req.surface == "backend")
    expect(
        backend.status == FeatureState.DEGRADED,
        "missing manifest should degrade backend requirement",
    )
    expect(backend.detail is not None, "degraded backend requirement should include detail")
