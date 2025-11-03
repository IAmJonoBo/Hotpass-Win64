from __future__ import annotations

from pathlib import Path

import pytest

from hotpass.inventory import InventoryService
from tests.helpers.assertions import expect


SAMPLE_MANIFEST = """
version: 2025-10-26
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
    dependencies: [vault]
    controls: [encryption]
  - id: vault
    name: Vault Secrets
    type: secret
    location: vault://hotpass
    classification: sensitive
    owner: Security
    custodian: Platform
    description: Secrets store
"""


def test_load_manifest_and_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "asset-register.yaml"
    manifest_path.write_text(SAMPLE_MANIFEST)

    service = InventoryService(manifest_path=manifest_path, cache_ttl=60)
    manifest = service.load_manifest()
    summary = service.summary()

    expect(manifest.version == "2025-10-26", "manifest version should match file contents")
    expect(len(manifest.assets) == 2, "manifest should expose both assets")
    expect(summary.total_assets == 2, "summary should include both assets")
    expect(summary.by_type["filesystem"] == 1, "filesystem count should match manifest")

    # Update manifest and ensure cache invalidation picks up new asset
    manifest_path.write_text(
        SAMPLE_MANIFEST
        + "  - id: db\n    name: Analytics DB\n    type: database\n    location: ./dist\n    classification: internal\n    owner: Analytics\n    custodian: Platform\n    description: Derived metrics\n"
    )

    refreshed = service.load_manifest()
    expect(len(refreshed.assets) == 3, "updated manifest should include new asset")
    expect(service.summary().total_assets == 3, "summary should refresh after cache invalidation")


def test_missing_manifest_raises(tmp_path: Path) -> None:
    service = InventoryService(manifest_path=tmp_path / "missing.yaml", cache_ttl=0)
    with pytest.raises(FileNotFoundError):
        service.load_manifest()


def test_invalid_manifest_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "asset-register.yaml"
    manifest_path.write_text("{ invalid: true }")

    service = InventoryService(manifest_path=manifest_path, cache_ttl=0)
    with pytest.raises(ValueError):
        service.load_manifest()


def test_invalid_cache_ttl_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_INVENTORY_CACHE_TTL", "not-a-number")

    with pytest.raises(ValueError):
        InventoryService()


def test_negative_cache_ttl_raises() -> None:
    with pytest.raises(ValueError):
        InventoryService(cache_ttl=-5)
