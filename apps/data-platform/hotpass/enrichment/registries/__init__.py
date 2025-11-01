"""Registry adapter factory and exports."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from .base import (
    BaseRegistryAdapter,
    RegistryConfigurationError,
    RegistryError,
    RegistryRateLimitError,
    RegistryResponse,
    RegistryTransportError,
)
from .cipc import CIPCRegistryAdapter
from .sacaa import SACAARegistryAdapter

_ADAPTERS: MutableMapping[str, type[BaseRegistryAdapter]] = {
    CIPCRegistryAdapter.registry: CIPCRegistryAdapter,
    SACAARegistryAdapter.registry: SACAARegistryAdapter,
}


def register_adapter(name: str, adapter: type[BaseRegistryAdapter]) -> None:
    """Register a custom registry adapter."""

    _ADAPTERS[name.lower()] = adapter


def available_adapters() -> Mapping[str, type[BaseRegistryAdapter]]:
    """Return the currently registered adapters."""

    return dict(_ADAPTERS)


def get_registry_adapter(name: str, **kwargs: Any) -> BaseRegistryAdapter:
    """Instantiate the adapter for ``name`` using the supplied kwargs."""

    try:
        adapter_cls = _ADAPTERS[name.lower()]
    except KeyError as exc:  # pragma: no cover - defensive
        raise RegistryConfigurationError(f"Unknown registry adapter: {name}") from exc
    return adapter_cls(**kwargs)


__all__ = [
    "available_adapters",
    "BaseRegistryAdapter",
    "CIPCRegistryAdapter",
    "get_registry_adapter",
    "register_adapter",
    "RegistryConfigurationError",
    "RegistryError",
    "RegistryRateLimitError",
    "RegistryResponse",
    "RegistryTransportError",
    "SACAARegistryAdapter",
]
