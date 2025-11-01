"""Execution helpers for intent signal collection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from ...normalization import slugify
from ..validators import logistic_scale
from .collectors import COLLECTOR_REGISTRY, IntentCollectorContext, IntentCollectorError
from .config import IntentPlan
from .storage import IntentSignalStore


@dataclass(slots=True)
class IntentCollectorTiming:
    """Timing information for collector execution."""

    collector_name: str
    seconds: float


@dataclass(slots=True)
class IntentOrganizationSummary:
    """Aggregated summary for a single organisation."""

    identifier: str
    slug: str | None
    score: float
    signal_count: int
    signal_types: tuple[str, ...]
    last_observed_at: datetime | None
    top_insights: tuple[str, ...]


@dataclass(slots=True)
class IntentRunResult:
    """Container returned after executing an intent plan."""

    signals: pd.DataFrame
    digest: pd.DataFrame
    summary: dict[str, IntentOrganizationSummary]
    timings: tuple[IntentCollectorTiming, ...]
    warnings: tuple[str, ...]


def run_intent_plan(
    plan: IntentPlan,
    *,
    country_code: str,
    credentials: Mapping[str, str],
    issued_at: datetime | None = None,
    storage: IntentSignalStore | None = None,
) -> IntentRunResult:
    """Execute the configured collectors and aggregate signals."""

    if not plan.enabled or not plan.active_collectors() or not plan.active_targets():
        empty = pd.DataFrame(
            columns=[
                "target_identifier",
                "target_slug",
                "signal_type",
                "score",
                "observed_at",
                "collector",
                "metadata",
                "retrieved_at",
                "provenance",
            ]
        )
        digest = pd.DataFrame(
            columns=[
                "target_identifier",
                "target_slug",
                "intent_signal_score",
                "intent_signal_count",
                "intent_signal_types",
                "intent_last_observed_at",
                "intent_top_insights",
            ]
        )
        return IntentRunResult(
            signals=empty,
            digest=digest,
            summary={},
            timings=(),
            warnings=(),
        )

    issued_at = (issued_at or datetime.now(tz=UTC)).astimezone(UTC)
    active_store = storage
    if active_store is None and plan.storage_path is not None:
        active_store = IntentSignalStore(plan.storage_path)
    context = IntentCollectorContext(
        country_code=country_code,
        credentials=credentials,
        issued_at=issued_at,
        store=active_store,
    )

    signal_rows: list[dict[str, Any]] = []
    timing_records: list[IntentCollectorTiming] = []
    warnings: list[str] = []

    # Aggregation buckets keyed by canonical slug
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "identifier": None,
            "slug": None,
            "weighted_score": 0.0,
            "weight_total": 0.0,
            "count": 0,
            "types": set(),
            "last_observed": None,
            "insights": [],
        }
    )

    for collector_def in plan.active_collectors():
        try:
            collector = COLLECTOR_REGISTRY.create(collector_def.name, collector_def.options)
        except IntentCollectorError as exc:
            warnings.append(str(exc))
            continue

        start = datetime.now(tz=UTC)
        for target in plan.active_targets():
            key = _canonical_key(target.identifier, target.slug)
            bucket = buckets[key]
            bucket["identifier"] = target.identifier
            bucket["slug"] = target.slug or bucket["slug"]

            for signal in collector.collect(target.identifier, target.slug, context):
                bucket["weighted_score"] += signal.score * max(collector_def.weight, 0.0)
                bucket["weight_total"] += max(collector_def.weight, 0.0)
                bucket["count"] += 1
                bucket["types"].add(signal.signal_type)
                if bucket["last_observed"] is None or (
                    signal.observed_at and signal.observed_at > bucket["last_observed"]
                ):
                    bucket["last_observed"] = signal.observed_at
                insight = _summarise_metadata(signal.metadata)
                if insight:
                    bucket["insights"].append(insight)
                signal_rows.append(
                    {
                        "target_identifier": signal.target_identifier,
                        "target_slug": target.slug,
                        "signal_type": signal.signal_type,
                        "score": signal.score,
                        "observed_at": signal.observed_at.isoformat(),
                        "collector": signal.collector,
                        "metadata": signal.metadata,
                        "retrieved_at": signal.retrieved_at.isoformat(),
                        "provenance": signal.provenance,
                    }
                )
        elapsed = (datetime.now(tz=UTC) - start).total_seconds()
        timing_records.append(
            IntentCollectorTiming(
                collector_name=collector_def.name,
                seconds=elapsed,
            )
        )

    if plan.deduplicate and signal_rows:
        deduped = {
            (
                row["target_slug"],
                row["signal_type"],
                row["observed_at"],
                row["collector"],
            ): row
            for row in signal_rows
        }
        signal_rows = list(deduped.values())

    signals_df = pd.DataFrame(signal_rows)
    if not signal_rows:
        signals_df = pd.DataFrame(
            columns=[
                "target_identifier",
                "target_slug",
                "signal_type",
                "score",
                "observed_at",
                "collector",
                "metadata",
                "retrieved_at",
                "provenance",
            ]
        )

    summary: dict[str, IntentOrganizationSummary] = {}
    digest_rows: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        weight_total = bucket["weight_total"] or 0.0
        if weight_total <= 0:
            score = 0.0
        else:
            score = logistic_scale(bucket["weighted_score"] / weight_total)
        types = tuple(sorted(bucket["types"]))
        insights = tuple(bucket["insights"][:5])
        last_observed = bucket["last_observed"]
        summary_obj = IntentOrganizationSummary(
            identifier=bucket["identifier"] or key,
            slug=bucket["slug"],
            score=score,
            signal_count=bucket["count"],
            signal_types=types,
            last_observed_at=last_observed,
            top_insights=insights,
        )
        for alias in _aliases(summary_obj.identifier, summary_obj.slug):
            summary[alias] = summary_obj
        digest_rows.append(
            {
                "target_identifier": summary_obj.identifier,
                "target_slug": summary_obj.slug,
                "intent_signal_score": score,
                "intent_signal_count": summary_obj.signal_count,
                "intent_signal_types": ";".join(types) if types else None,
                "intent_last_observed_at": (
                    summary_obj.last_observed_at.isoformat()
                    if summary_obj.last_observed_at
                    else None
                ),
                "intent_top_insights": "; ".join(insights) if insights else None,
            }
        )

    digest_df = pd.DataFrame(digest_rows)
    if digest_df.empty:
        digest_df = pd.DataFrame(
            columns=[
                "target_identifier",
                "target_slug",
                "intent_signal_score",
                "intent_signal_count",
                "intent_signal_types",
                "intent_last_observed_at",
                "intent_top_insights",
            ]
        )

    return IntentRunResult(
        signals=signals_df,
        digest=digest_df,
        summary=summary,
        timings=tuple(timing_records),
        warnings=tuple(warnings),
    )


def _summarise_metadata(metadata: Mapping[str, Any]) -> str | None:
    if not metadata:
        return None
    for key in ("headline", "role", "source"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _canonical_key(identifier: str, slug_value: str | None) -> str:
    if slug_value:
        return slug_value.lower()
    slug_candidate = slugify(identifier)
    return slug_candidate or identifier.lower()


def _aliases(identifier: str, slug_value: str | None) -> tuple[str, ...]:
    aliases = []
    if slug_value:
        aliases.append(slug_value.lower())
    slug_candidate = slugify(identifier)
    if slug_candidate:
        aliases.append(slug_candidate)
    aliases.append(identifier.lower())
    return tuple(dict.fromkeys(aliases))


__all__ = [
    "IntentCollectorTiming",
    "IntentOrganizationSummary",
    "IntentRunResult",
    "run_intent_plan",
]
