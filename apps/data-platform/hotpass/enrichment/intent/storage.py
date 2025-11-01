"""Persistence helpers for intent signal collectors."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .collectors import IntentSignal


def _parse_datetime(value: str) -> datetime:
    candidate = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _as_string(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _as_optional_string(value: object | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _as_float(value: object | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


@dataclass(slots=True)
class StoredSignal:
    """Serialised representation for persisted intent signals."""

    data: Mapping[str, object]

    def key(self) -> tuple[str, ...]:
        collector = str(self.data.get("collector", ""))
        identifier = str(self.data.get("target_identifier", "")).lower()
        slug = str(self.data.get("target_slug") or "").lower()
        signal_type = str(self.data.get("signal_type", ""))
        observed = str(self.data.get("observed_at", ""))
        return (collector, identifier, slug, signal_type, observed)


class IntentSignalStore:
    """Persist and retrieve intent signals for caching and provenance."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: dict[tuple[str, ...], StoredSignal] = {}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = []
            if isinstance(payload, list):
                for entry in payload:
                    record = StoredSignal(dict(entry))
                    self._records[record.key()] = record

    def fetch_cached(
        self,
        *,
        target_identifier: str,
        target_slug: str | None,
        collector: str,
        max_age: timedelta,
        issued_at: datetime | None = None,
    ) -> list[IntentSignal]:
        """Return cached signals within the allowed age window."""

        if max_age.total_seconds() <= 0:
            return []

        reference = issued_at or datetime.now(tz=UTC)
        matches: list[IntentSignal] = []
        identifier_lower = target_identifier.lower()
        slug_lower = (target_slug or "").lower()

        for stored in self._records.values():
            data = stored.data
            if str(data.get("collector")) != collector:
                continue
            if str(data.get("target_identifier", "")).lower() != identifier_lower:
                continue
            stored_slug = str(data.get("target_slug") or "").lower()
            if slug_lower and stored_slug != slug_lower:
                continue
            retrieved_raw = data.get("retrieved_at")
            if not isinstance(retrieved_raw, str):
                continue
            retrieved_at = _parse_datetime(retrieved_raw)
            if reference - retrieved_at > max_age:
                continue
            matches.append(self._to_signal(data))
        return matches

    def persist(self, signals: Sequence[IntentSignal]) -> None:
        """Persist the provided signals, deduplicating existing entries."""

        if not signals:
            return

        for signal in signals:
            record = StoredSignal(self._serialise(signal))
            self._records[record.key()] = record

        self._flush()

    def _serialise(self, signal: IntentSignal) -> dict[str, object]:
        return {
            "target_identifier": signal.target_identifier,
            "target_slug": signal.target_slug,
            "signal_type": signal.signal_type,
            "score": signal.score,
            "observed_at": signal.observed_at.astimezone(UTC).isoformat(),
            "retrieved_at": signal.retrieved_at.astimezone(UTC).isoformat(),
            "metadata": dict(signal.metadata),
            "provenance": dict(signal.provenance),
            "collector": signal.collector,
        }

    def _to_signal(self, record: Mapping[str, object]) -> IntentSignal:
        from .collectors import IntentSignal  # Local import to avoid circular dependency

        observed_at = _parse_datetime(str(record.get("observed_at", "")))
        retrieved_at = _parse_datetime(str(record.get("retrieved_at", "")))
        metadata = record.get("metadata") or {}
        provenance = record.get("provenance") or {}
        return IntentSignal(
            target_identifier=_as_string(record.get("target_identifier")),
            target_slug=_as_optional_string(record.get("target_slug")),
            signal_type=_as_string(record.get("signal_type")),
            score=_as_float(record.get("score")),
            observed_at=observed_at,
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
            collector=_as_string(record.get("collector")),
            retrieved_at=retrieved_at,
            provenance=dict(provenance) if isinstance(provenance, Mapping) else {},
        )

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = [record.data for record in self._records.values()]
        ordered.sort(
            key=lambda entry: (
                str(entry.get("retrieved_at", "")),
                str(entry.get("collector", "")),
            )
        )
        self.path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")


__all__ = ["IntentSignalStore"]
