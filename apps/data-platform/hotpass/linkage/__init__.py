"""Probabilistic linkage utilities exposed by Hotpass."""

from __future__ import annotations

from .config import LabelStudioConfig, LinkageConfig, LinkagePersistence, LinkageThresholds
from .runner import LinkageResult, link_entities

__all__ = [
    "LabelStudioConfig",
    "LinkageConfig",
    "LinkagePersistence",
    "LinkageResult",
    "LinkageThresholds",
    "link_entities",
]
