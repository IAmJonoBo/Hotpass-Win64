"""Intent signal collectors powering enrichment automation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from ...normalization import slugify
from .storage import IntentSignalStore


@dataclass(slots=True)
class IntentCollectorContext:
    """Contextual information passed to collectors."""

    country_code: str
    credentials: Mapping[str, str]
    issued_at: datetime
    store: IntentSignalStore | None = None


@dataclass(slots=True)
class IntentSignal:
    """Structured signal emitted by collectors."""

    target_identifier: str
    target_slug: str | None
    signal_type: str
    score: float
    observed_at: datetime
    metadata: Mapping[str, Any]
    collector: str
    retrieved_at: datetime
    provenance: Mapping[str, Any]


class IntentCollectorError(RuntimeError):
    """Raised when collector configuration is invalid."""


class BaseIntentCollector:
    """Base class for all intent collectors."""

    name: ClassVar[str]

    def __init__(self, options: Mapping[str, Any] | None = None) -> None:
        self.options = dict(options or {})

    def _cache_ttl(self) -> timedelta:
        minutes = float(self.options.get("cache_ttl_minutes", 180) or 0.0)
        return timedelta(minutes=max(minutes, 0.0))

    def _cached_signals(
        self,
        target_identifier: str,
        target_slug: str | None,
        context: IntentCollectorContext,
    ) -> list[IntentSignal]:
        store = context.store
        if store is None:
            return []
        ttl = self._cache_ttl()
        if ttl.total_seconds() <= 0:
            return []
        return store.fetch_cached(
            target_identifier=target_identifier,
            target_slug=target_slug,
            collector=self.name,
            max_age=ttl,
            issued_at=context.issued_at,
        )

    def _gather_events(
        self, target_identifier: str, target_slug: str | None
    ) -> list[Mapping[str, Any]]:
        dataset = self.options.get("events", {})
        if not isinstance(dataset, Mapping):
            return []
        events: list[Mapping[str, Any]] = []
        seen: set[int] = set()
        for key in self._normalise_key(target_identifier, target_slug):
            raw_entries = dataset.get(key)
            if not raw_entries:
                continue
            for entry in raw_entries:
                identifier = id(entry)
                if identifier in seen:
                    continue
                seen.add(identifier)
                if isinstance(entry, Mapping):
                    events.append(dict(entry))
        return events

    def _persist_signals(
        self, signals: Iterable[IntentSignal], context: IntentCollectorContext
    ) -> None:
        store = context.store
        if store is None:
            return
        buffer = list(signals)
        if not buffer:
            return
        store.persist(buffer)

    def _base_provenance(
        self,
        event: Mapping[str, Any],
        context: IntentCollectorContext,
    ) -> dict[str, Any]:
        provenance = {
            "collector": self.name,
            "retrieved_at": context.issued_at.astimezone(UTC).isoformat(),
            "provider": self.options.get("provider", self.name),
        }
        if event.get("url"):
            provenance["url"] = str(event["url"])
        return provenance

    def _build_signal(
        self,
        *,
        target_identifier: str,
        target_slug: str | None,
        signal_type: str,
        score: float,
        observed_at: datetime,
        metadata: Mapping[str, Any],
        context: IntentCollectorContext,
        provenance: Mapping[str, Any],
    ) -> IntentSignal:
        cleaned_metadata = {
            key: value for key, value in metadata.items() if value not in (None, "", [], {}, ())
        }
        bounded = max(0.0, min(1.0, score))
        return IntentSignal(
            target_identifier=target_identifier,
            target_slug=target_slug,
            signal_type=signal_type,
            score=bounded,
            observed_at=observed_at,
            metadata=cleaned_metadata,
            collector=self.name,
            retrieved_at=context.issued_at,
            provenance=dict(provenance),
        )

    def _normalise_key(self, target_identifier: str, target_slug: str | None) -> tuple[str, ...]:
        keys = []
        if target_slug:
            keys.append(target_slug.lower())
        identifier_slug = slugify(target_identifier)
        if identifier_slug:
            keys.append(identifier_slug)
        keys.append(target_identifier.lower())
        return tuple(dict.fromkeys(keys))

    def collect(
        self,
        target_identifier: str,
        target_slug: str | None,
        context: IntentCollectorContext,
    ) -> Iterable[IntentSignal]:  # pragma: no cover - abstract
        raise NotImplementedError


class NewsMentionCollector(BaseIntentCollector):
    """Collector parsing news-like events from static configuration."""

    name = "news"

    def collect(
        self,
        target_identifier: str,
        target_slug: str | None,
        context: IntentCollectorContext,
    ) -> Iterable[IntentSignal]:
        cached = self._cached_signals(target_identifier, target_slug, context)
        if cached:
            return cached

        signals: list[IntentSignal] = []
        for event in self._gather_events(target_identifier, target_slug):
            headline = str(event.get("headline") or "").strip()
            intent = float(event.get("intent", 0.0) or 0.0)
            sentiment = float(event.get("sentiment", 0.0) or 0.0)
            score = intent + 0.25 * max(sentiment, 0.0)
            observed_at = _parse_timestamp(event.get("timestamp"), context.issued_at)
            metadata = {
                "headline": headline or None,
                "url": event.get("url"),
                "sentiment": sentiment if sentiment else None,
            }
            provenance = self._base_provenance(event, context)
            signal = self._build_signal(
                target_identifier=target_identifier,
                target_slug=target_slug,
                signal_type="news",
                score=score,
                observed_at=observed_at,
                metadata=metadata,
                context=context,
                provenance=provenance,
            )
            signals.append(signal)

        self._persist_signals(signals, context)
        return signals


class HiringPulseCollector(BaseIntentCollector):
    """Collector summarising hiring signals for key roles."""

    name = "hiring"

    def collect(
        self,
        target_identifier: str,
        target_slug: str | None,
        context: IntentCollectorContext,
    ) -> Iterable[IntentSignal]:
        cached = self._cached_signals(target_identifier, target_slug, context)
        if cached:
            return cached

        signals: list[IntentSignal] = []
        for event in self._gather_events(target_identifier, target_slug):
            role = str(event.get("role") or "").strip()
            seniority = float(event.get("seniority", 0.6) or 0.6)
            intent = float(event.get("intent", 0.0) or 0.0)
            score = intent + 0.2 * max(0.0, seniority)
            observed_at = _parse_timestamp(event.get("timestamp"), context.issued_at)
            metadata = {
                "role": role or None,
                "location": event.get("location"),
            }
            provenance = self._base_provenance(event, context)
            signal = self._build_signal(
                target_identifier=target_identifier,
                target_slug=target_slug,
                signal_type="hiring",
                score=score,
                observed_at=observed_at,
                metadata=metadata,
                context=context,
                provenance=provenance,
            )
            signals.append(signal)

        self._persist_signals(signals, context)
        return signals


class TrafficSpikeCollector(BaseIntentCollector):
    """Collector summarising digital traffic spikes."""

    name = "traffic"

    def collect(
        self,
        target_identifier: str,
        target_slug: str | None,
        context: IntentCollectorContext,
    ) -> Iterable[IntentSignal]:
        cached = self._cached_signals(target_identifier, target_slug, context)
        if cached:
            return cached

        signals: list[IntentSignal] = []
        for event in self._gather_events(target_identifier, target_slug):
            magnitude = float(event.get("magnitude", 0.0) or 0.0)
            intent = float(event.get("intent", 0.0) or 0.0)
            score = intent + 0.1 * max(0.0, magnitude)
            observed_at = _parse_timestamp(event.get("timestamp"), context.issued_at)
            metadata = {
                "source": event.get("source"),
                "magnitude": magnitude if magnitude else None,
            }
            provenance = self._base_provenance(event, context)
            signal = self._build_signal(
                target_identifier=target_identifier,
                target_slug=target_slug,
                signal_type="traffic",
                score=score,
                observed_at=observed_at,
                metadata=metadata,
                context=context,
                provenance=provenance,
            )
            signals.append(signal)

        self._persist_signals(signals, context)
        return signals


class TechAdoptionCollector(BaseIntentCollector):
    """Collector capturing technology adoption and upgrade signals."""

    name = "tech-adoption"

    def collect(
        self,
        target_identifier: str,
        target_slug: str | None,
        context: IntentCollectorContext,
    ) -> Iterable[IntentSignal]:
        cached = self._cached_signals(target_identifier, target_slug, context)
        if cached:
            return cached

        signals: list[IntentSignal] = []
        for event in self._gather_events(target_identifier, target_slug):
            technology = str(event.get("technology") or "").strip()
            stage_raw = (
                str(event.get("stage") or event.get("adoption_stage") or event.get("status") or "")
                .strip()
                .lower()
            )
            stage_bonus = {
                "trial": 0.15,
                "pilot": 0.25,
                "production": 0.4,
                "upgrade": 0.35,
            }.get(stage_raw, 0.2)
            intent = float(event.get("intent", 0.0) or 0.0)
            score = intent + stage_bonus
            observed_at = _parse_timestamp(event.get("timestamp"), context.issued_at)
            metadata = {
                "technology": technology or None,
                "stage": stage_raw or None,
                "provider": event.get("provider"),
            }
            provenance = self._base_provenance(event, context)
            if technology:
                provenance["technology"] = technology
            signal = self._build_signal(
                target_identifier=target_identifier,
                target_slug=target_slug,
                signal_type="tech-adoption",
                score=score,
                observed_at=observed_at,
                metadata=metadata,
                context=context,
                provenance=provenance,
            )
            signals.append(signal)

        self._persist_signals(signals, context)
        return signals


def _parse_timestamp(candidate: Any, fallback: datetime) -> datetime:
    if isinstance(candidate, datetime):
        return candidate.astimezone(UTC)
    if isinstance(candidate, str):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return fallback


class IntentCollectorRegistry:
    """Registry managing collector implementations."""

    def __init__(self) -> None:
        self._collectors: dict[str, type[BaseIntentCollector]] = {}

    def register(self, name: str, collector: type[BaseIntentCollector]) -> None:
        self._collectors[name.lower()] = collector

    def create(self, name: str, options: Mapping[str, Any] | None = None) -> BaseIntentCollector:
        try:
            collector_cls = self._collectors[name.lower()]
        except KeyError as exc:  # pragma: no cover - defensive
            raise IntentCollectorError(f"Unknown collector: {name}") from exc
        return collector_cls(options)


COLLECTOR_REGISTRY = IntentCollectorRegistry()
COLLECTOR_REGISTRY.register(NewsMentionCollector.name, NewsMentionCollector)
COLLECTOR_REGISTRY.register(HiringPulseCollector.name, HiringPulseCollector)
COLLECTOR_REGISTRY.register(TrafficSpikeCollector.name, TrafficSpikeCollector)
COLLECTOR_REGISTRY.register(TechAdoptionCollector.name, TechAdoptionCollector)


__all__ = [
    "BaseIntentCollector",
    "COLLECTOR_REGISTRY",
    "HiringPulseCollector",
    "IntentCollectorContext",
    "IntentCollectorError",
    "IntentSignal",
    "NewsMentionCollector",
    "TrafficSpikeCollector",
    "TechAdoptionCollector",
]
