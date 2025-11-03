from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Asset, InventoryManifest, InventorySummary

_DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "inventory" / "asset-register.yaml"
)
_DEFAULT_CACHE_TTL_SECONDS = 300


def _resolve_manifest_path(path: str | os.PathLike[str] | None) -> Path:
    candidate = (
        Path(path)
        if path is not None
        else Path(os.getenv("HOTPASS_INVENTORY_PATH", _DEFAULT_MANIFEST_PATH))
    )
    return candidate.expanduser().resolve()


@dataclass(slots=True)
class _CacheEntry:
    manifest: InventoryManifest
    summary: InventorySummary
    mtime_ns: int
    expires_at: float


def _resolve_cache_ttl(ttl_override: int | None) -> int:
    if ttl_override is not None:
        if ttl_override < 0:
            raise ValueError("cache_ttl must be greater than or equal to zero")
        return ttl_override

    raw_env = os.getenv("HOTPASS_INVENTORY_CACHE_TTL")
    if raw_env is None:
        return _DEFAULT_CACHE_TTL_SECONDS

    try:
        parsed = int(raw_env)
    except ValueError as exc:  # pragma: no cover - defensive path
        raise ValueError(
            "HOTPASS_INVENTORY_CACHE_TTL must be an integer number of seconds"
        ) from exc

    if parsed < 0:
        raise ValueError("HOTPASS_INVENTORY_CACHE_TTL must be >= 0")

    return parsed


class InventoryService:
    """Loads and summarises the asset inventory manifest with caching."""

    def __init__(
        self, *, manifest_path: str | os.PathLike[str] | None = None, cache_ttl: int | None = None
    ) -> None:
        self._manifest_path = _resolve_manifest_path(manifest_path)
        self._cache_ttl = _resolve_cache_ttl(cache_ttl)
        self._lock = threading.RLock()
        self._cache: _CacheEntry | None = None

    @property
    def manifest_path(self) -> Path:
        return self._manifest_path

    def load_manifest(self) -> InventoryManifest:
        """Load and validate the inventory manifest from disk."""
        with self._lock:
            cache = self._maybe_get_cache()
            if cache is not None:
                return cache.manifest

            manifest = self._read_manifest()
            summary = InventorySummary.from_assets(manifest.assets)
            self._cache = _CacheEntry(
                manifest=manifest,
                summary=summary,
                mtime_ns=self._manifest_path.stat().st_mtime_ns,
                expires_at=time.time() + max(self._cache_ttl, 0),
            )
            return manifest

    def summary(self) -> InventorySummary:
        """Return the cached or freshly computed inventory summary."""
        with self._lock:
            cache = self._maybe_get_cache()
            if cache is not None:
                return cache.summary

            manifest = self._read_manifest()
            summary = InventorySummary.from_assets(manifest.assets)
            self._cache = _CacheEntry(
                manifest=manifest,
                summary=summary,
                mtime_ns=self._manifest_path.stat().st_mtime_ns,
                expires_at=time.time() + max(self._cache_ttl, 0),
            )
            return summary

    def _maybe_get_cache(self) -> _CacheEntry | None:
        cache = self._cache
        if cache is None:
            return None
        try:
            mtime_ns = self._manifest_path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

        if cache.mtime_ns != mtime_ns:
            return None
        if cache.expires_at < time.time():
            return None
        return cache

    def _read_manifest(self) -> InventoryManifest:
        if not self._manifest_path.exists():
            raise FileNotFoundError(
                f"Inventory manifest not found at {self._manifest_path}. "
                "Set HOTPASS_INVENTORY_PATH to override."
            )

        with self._manifest_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        try:
            manifest = InventoryManifest.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - exercised by tests
            raise ValueError(f"Invalid inventory manifest: {exc}") from exc

        # Normalise optional collections (guaranteed by pydantic, but re-iterate to remove duplicates)
        normalised_assets: list[Asset] = []
        for asset in manifest.assets:
            normalised_assets.append(
                asset.model_copy(
                    update={
                        "dependencies": list(dict.fromkeys(asset.dependencies)),
                        "controls": list(dict.fromkeys(asset.controls)),
                    }
                )
            )

        return InventoryManifest(
            version=manifest.version,
            maintainer=manifest.maintainer,
            review_cadence=manifest.review_cadence,
            assets=normalised_assets,
        )


__all__ = ["InventoryService"]
