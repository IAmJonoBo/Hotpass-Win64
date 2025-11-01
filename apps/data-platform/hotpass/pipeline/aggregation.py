from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
import polars as pl

from ..enrichment.intent import IntentOrganizationSummary
from ..enrichment.validators import ContactValidationService
from ..normalization import clean_string, coalesce, slugify
from ..pipeline_reporting import collect_unique
from ..storage import PolarsDataset
from ..telemetry import pipeline_stage
from ..transform.scoring import LeadScorer
from .config import DEFAULT_LEAD_SCORER, SSOT_COLUMNS as CONFIG_SSOT_COLUMNS, PipelineConfig

SSOT_COLUMNS = CONFIG_SSOT_COLUMNS

logger = logging.getLogger(__name__)

CONTACT_VALIDATION = ContactValidationService()
SOURCE_PRIORITY: dict[str, int] = {
    "SACAA Cleaned": 3,
    "Reachout Database": 2,
    "Contact Database": 1,
}
YEAR_FIRST_PATTERN = re.compile(r"^\s*\d{4}")


@dataclass(frozen=True)
class RowMetadata:
    index: int
    source_dataset: str
    source_record_id: str | None
    source_priority: int
    quality_score: int
    last_interaction: pd.Timestamp | None


@dataclass(frozen=True)
class ValueSelection:
    value: str
    row_metadata: RowMetadata


@dataclass
class AggregationResult:
    refined_df: pd.DataFrame
    combined_polars: pl.DataFrame
    conflicts: list[dict[str, Any]]
    metrics: dict[str, Any]
    source_breakdown: dict[str, int]


def _flatten_series_of_lists(series: pd.Series) -> list[str]:
    items: list[str] = []
    for value in series.dropna():
        if isinstance(value, list):
            for element in value:
                cleaned = clean_string(element)
                if cleaned:
                    items.append(cleaned)
        else:
            cleaned = clean_string(value)
            if cleaned:
                items.append(cleaned)
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _latest_iso_date(values: Iterable[object | None]) -> str | None:
    candidates: list[object] = []
    for value in values:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            candidates.append(stripped)
        else:
            candidates.append(value)

    if not candidates:
        return None

    parsed: list[pd.Timestamp] = []
    for candidate in candidates:
        timestamp: pd.Timestamp | None
        if isinstance(candidate, pd.Timestamp):
            timestamp = cast(pd.Timestamp, pd.to_datetime(candidate, utc=True))
        else:
            text = str(candidate)
            prefer_dayfirst = not YEAR_FIRST_PATTERN.match(text)
            timestamp = cast(
                pd.Timestamp,
                pd.to_datetime(
                    text,
                    errors="coerce",
                    dayfirst=prefer_dayfirst,
                    utc=True,
                ),
            )
            if pd.isna(timestamp):
                timestamp = cast(
                    pd.Timestamp,
                    pd.to_datetime(
                        text,
                        errors="coerce",
                        dayfirst=not prefer_dayfirst,
                        utc=True,
                    ),
                )
        if pd.notna(timestamp):
            parsed.append(timestamp)

    if not parsed:
        return None

    latest = max(parsed)
    if pd.isna(latest):
        return None
    return str(latest.date().isoformat())


def _summarise_quality(row: dict[str, str | None]) -> dict[str, object]:
    checks = {
        "contact_email": bool(row.get("contact_primary_email")),
        "contact_phone": bool(row.get("contact_primary_phone")),
        "website": bool(row.get("website")),
        "province": bool(row.get("province")),
        "address": bool(row.get("address_primary")),
    }
    score = sum(1 for flag in checks.values() if flag) / max(len(checks), 1)
    missing_flags = [
        f"missing_{name}" for name, present in checks.items() if not present
    ]
    return {
        "score": round(score, 2),
        "flags": ";".join(missing_flags) if missing_flags else "none",
    }


def _resolve_intent_summary(
    intent_summaries: Mapping[str, IntentOrganizationSummary] | None,
    slug: str | None,
    organization_name: str | None,
) -> IntentOrganizationSummary | None:
    if not intent_summaries:
        return None
    candidates: list[str] = []
    if slug:
        candidates.append(str(slug).lower())
    if organization_name:
        slug_candidate = slugify(organization_name)
        if slug_candidate:
            candidates.append(slug_candidate)
        candidates.append(organization_name.lower())
    for candidate in candidates:
        summary = intent_summaries.get(candidate)
        if summary:
            return summary
    return None


def _row_quality_score(row: Mapping[str, object | None]) -> int:
    checks = [
        bool(row.get("contact_emails")),
        bool(row.get("contact_phones")),
        bool(row.get("website")),
        bool(row.get("province")),
        bool(row.get("address")),
    ]
    return sum(1 for present in checks if present)


def _aggregate_group(
    slug: str | None,
    rows: Sequence[Mapping[str, Any]],
    *,
    country_code: str,
    intent_summaries: Mapping[str, IntentOrganizationSummary] | None = None,
    lead_scorer: LeadScorer = DEFAULT_LEAD_SCORER,
) -> dict[str, object | None]:
    if not rows:
        raise ValueError("Cannot aggregate empty group")

    entries = [dict(row) for row in rows]
    organization_name = coalesce(*(entry.get("organization_name") for entry in entries))

    row_metadata: list[RowMetadata] = []
    for idx, entry in enumerate(entries):
        raw_dataset = entry.get("source_dataset")
        dataset = clean_string(raw_dataset)
        if not dataset:
            dataset = str(raw_dataset).strip() if raw_dataset else "Unknown"
        record_id = clean_string(entry.get("source_record_id"))
        priority = SOURCE_PRIORITY.get(dataset, 0)
        last_interaction = _parse_last_interaction(entry.get("last_interaction_date"))
        quality_score = _row_quality_score(entry)
        row_metadata.append(
            RowMetadata(
                index=idx,
                source_dataset=dataset,
                source_record_id=record_id,
                source_priority=priority,
                quality_score=quality_score,
                last_interaction=last_interaction,
            )
        )

    def _sort_key(meta: RowMetadata) -> tuple[Any, ...]:
        timestamp_value = (
            meta.last_interaction.value
            if meta.last_interaction is not None
            else pd.Timestamp.min.value
        )
        return (
            meta.source_priority,
            meta.quality_score,
            timestamp_value,
            -meta.index,
            meta.source_record_id or "",
        )

    sorted_indices = sorted(
        range(len(row_metadata)),
        key=lambda idx: _sort_key(row_metadata[idx]),
        reverse=True,
    )

    provenance: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []

    def _normalise_scalar(value: object | None) -> str | None:
        if isinstance(value, str):
            cleaned = clean_string(value)
            return cleaned if cleaned is not None else None
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        cleaned = clean_string(str(value))
        return cleaned if cleaned is not None else None

    def _iter_values(column: str, treat_list: bool = False) -> list[ValueSelection]:
        selections: list[ValueSelection] = []
        seen: set[str] = set()
        for idx in sorted_indices:
            row = entries[idx]
            raw_value = row.get(column)
            values: Iterable[object | None]
            if treat_list and isinstance(raw_value, list):
                values = raw_value
            else:
                values = [raw_value]
            for raw in values:
                normalised = _normalise_scalar(raw)
                if not normalised or normalised in seen:
                    continue
                seen.add(normalised)
                selections.append(ValueSelection(normalised, row_metadata[idx]))
        return selections

    def _build_provenance(
        field: str, selection: ValueSelection, value: str | None
    ) -> dict[str, Any]:
        meta = selection.row_metadata
        return {
            "field": field,
            "value": value,
            "source_dataset": meta.source_dataset,
            "source_record_id": meta.source_record_id,
            "source_priority": meta.source_priority,
            "quality_score": meta.quality_score,
            "last_interaction_date": (
                meta.last_interaction.date().isoformat()
                if meta.last_interaction is not None
                else None
            ),
        }

    def _record_provenance(
        field: str, selections: list[ValueSelection], value: str | None
    ) -> ValueSelection | None:
        if not selections:
            return None
        primary_selection = next(
            (sel for sel in selections if sel.value == value), selections[0]
        )
        entry = _build_provenance(field, primary_selection, value)
        contributors = [sel for sel in selections if sel is not primary_selection]
        if contributors:
            entry["contributors"] = [
                {
                    "source_dataset": sel.row_metadata.source_dataset,
                    "source_record_id": sel.row_metadata.source_record_id,
                    "value": sel.value,
                }
                for sel in contributors
            ]
            conflicts.append(
                {
                    "field": field,
                    "chosen_source": primary_selection.row_metadata.source_dataset,
                    "value": value,
                    "alternatives": [
                        {
                            "source": sel.row_metadata.source_dataset,
                            "value": sel.value,
                        }
                        for sel in contributors
                    ],
                }
            )
        provenance[field] = entry
        return primary_selection

    def _column_values(column: str) -> list[object | None]:
        return [entry.get(column) for entry in entries]

    provinces = _iter_values("province")
    areas = _iter_values("area")
    addresses = _iter_values("address")
    categories = _iter_values("category")
    org_types = _iter_values("organization_type")
    statuses = _iter_values("status")
    websites = _iter_values("website")
    planes = _iter_values("planes")
    descriptions = _iter_values("description")
    notes = _iter_values("notes")
    priorities = _iter_values("priority")

    email_values = _iter_values("contact_emails", treat_list=True)
    phone_values = _iter_values("contact_phones", treat_list=True)
    name_values = _iter_values("contact_names", treat_list=True)
    role_values = _iter_values("contact_roles", treat_list=True)

    dataset_labels = [
        clean_string(value) or (str(value).strip() if value else None)
        for value in _column_values("source_dataset")
    ]
    dataset_labels = [label for label in dataset_labels if label]
    source_datasets = "; ".join(sorted(collect_unique(dataset_labels)))

    record_ids = [
        clean_string(value) or (str(value).strip() if value else None)
        for value in _column_values("source_record_id")
    ]
    record_ids = [value for value in record_ids if value]
    source_record_ids = "; ".join(sorted(collect_unique(record_ids)))

    province = provinces[0].value if provinces else None
    _record_provenance("province", provinces, province)

    area = areas[0].value if areas else None
    _record_provenance("area", areas, area)

    address_primary = addresses[0].value if addresses else None
    _record_provenance("address_primary", addresses, address_primary)

    organization_category = categories[0].value if categories else None
    _record_provenance("organization_category", categories, organization_category)

    organization_type = org_types[0].value if org_types else None
    _record_provenance("organization_type", org_types, organization_type)

    status = statuses[0].value if statuses else None
    _record_provenance("status", statuses, status)

    website = websites[0].value if websites else None
    _record_provenance("website", websites, website)

    planes_value = (
        "; ".join(selection.value for selection in planes) if planes else None
    )
    if planes_value:
        _record_provenance("planes", planes, planes_value)

    description_value = (
        "; ".join(selection.value for selection in descriptions)
        if descriptions
        else None
    )
    if description_value:
        _record_provenance("description", descriptions, description_value)

    notes_value = "; ".join(selection.value for selection in notes) if notes else None
    if notes_value:
        _record_provenance("notes", notes, notes_value)

    priority_value = priorities[0].value if priorities else None
    _record_provenance("priority", priorities, priority_value)

    primary_email_selection = _record_provenance(
        "contact_primary_email",
        email_values,
        email_values[0].value if email_values else None,
    )
    primary_email = primary_email_selection.value if primary_email_selection else None
    secondary_email_values = email_values[1:]
    secondary_emails = ";".join(selection.value for selection in secondary_email_values)
    if secondary_emails:
        _record_provenance(
            "contact_secondary_emails", secondary_email_values, secondary_emails
        )

    primary_phone_selection = _record_provenance(
        "contact_primary_phone",
        phone_values,
        phone_values[0].value if phone_values else None,
    )
    primary_phone = primary_phone_selection.value if primary_phone_selection else None
    secondary_phone_values = phone_values[1:]
    secondary_phones = ";".join(selection.value for selection in secondary_phone_values)
    if secondary_phones:
        _record_provenance(
            "contact_secondary_phones", secondary_phone_values, secondary_phones
        )

    def _first_value_from_row(
        selection: ValueSelection | None, column: str
    ) -> str | None:
        if selection is None:
            return None
        row = entries[selection.row_metadata.index]
        raw_value = row.get(column)
        if isinstance(raw_value, list):
            for item in raw_value:
                candidate = _normalise_scalar(item)
                if candidate:
                    return candidate
            return None
        return _normalise_scalar(raw_value)

    primary_contact_meta = primary_email_selection or primary_phone_selection
    primary_name = _first_value_from_row(primary_contact_meta, "contact_names")
    if primary_name:
        _record_provenance("contact_primary_name", name_values, primary_name)
    else:
        primary_name = name_values[0].value if name_values else None
        if primary_name:
            _record_provenance("contact_primary_name", name_values, primary_name)

    primary_role = _first_value_from_row(primary_contact_meta, "contact_roles")
    if primary_role:
        _record_provenance("contact_primary_role", role_values, primary_role)
    else:
        primary_role = role_values[0].value if role_values else None
        if primary_role:
            _record_provenance("contact_primary_role", role_values, primary_role)

    validation_summary = CONTACT_VALIDATION.validate_contact(
        email=primary_email,
        phone=primary_phone,
        country_code=country_code,
    )
    email_confidence = (
        validation_summary.email.confidence if validation_summary.email else None
    )
    phone_confidence = (
        validation_summary.phone.confidence if validation_summary.phone else None
    )
    email_status = (
        validation_summary.email.status.value if validation_summary.email else None
    )
    phone_status = (
        validation_summary.phone.status.value if validation_summary.phone else None
    )
    validation_flags = validation_summary.flags()
    deliverability_score = validation_summary.deliverability_score()
    completeness_inputs = [primary_name, primary_email, primary_phone, primary_role]
    completeness = (
        sum(1 for value in completeness_inputs if value) / len(completeness_inputs)
        if completeness_inputs
        else 0.0
    )
    primary_meta = primary_email_selection or primary_phone_selection
    if primary_meta is None and name_values:
        primary_meta = name_values[0]
    max_priority = max(SOURCE_PRIORITY.values()) if SOURCE_PRIORITY else 1
    source_priority_norm = (
        primary_meta.row_metadata.source_priority / max_priority
        if primary_meta and max_priority
        else 0.0
    )
    intent_summary = _resolve_intent_summary(intent_summaries, slug, organization_name)
    intent_score = intent_summary.score if intent_summary else 0.0

    lead_score = lead_scorer.score(
        completeness=completeness,
        email_confidence=email_confidence or 0.0,
        phone_confidence=phone_confidence or 0.0,
        source_priority=source_priority_norm,
        intent_score=intent_score,
    ).value

    last_interaction = _latest_iso_date(_column_values("last_interaction_date"))

    quality = _summarise_quality(
        {
            "contact_primary_email": primary_email,
            "contact_primary_phone": primary_phone,
            "website": website,
            "province": province,
            "address_primary": address_primary,
        }
    )

    selection_provenance = json.dumps(provenance, sort_keys=True)

    result = {
        "organization_name": organization_name,
        "organization_slug": slug,
        "province": province,
        "country": "South Africa",
        "area": area,
        "address_primary": address_primary,
        "organization_category": organization_category,
        "organization_type": organization_type,
        "status": status,
        "website": website,
        "planes": planes_value,
        "description": description_value,
        "notes": notes_value,
        "source_datasets": source_datasets,
        "source_record_ids": source_record_ids,
        "contact_primary_name": primary_name,
        "contact_primary_role": primary_role,
        "contact_primary_email": primary_email,
        "contact_primary_phone": primary_phone,
        "contact_primary_email_confidence": email_confidence,
        "contact_primary_email_status": email_status,
        "contact_primary_phone_confidence": phone_confidence,
        "contact_primary_phone_status": phone_status,
        "contact_primary_lead_score": (
            lead_score if primary_name or primary_email or primary_phone else None
        ),
        "contact_email_confidence_avg": email_confidence,
        "contact_phone_confidence_avg": phone_confidence,
        "contact_verification_score_avg": (
            deliverability_score if deliverability_score else None
        ),
        "contact_lead_score_avg": lead_score if lead_score else None,
        "intent_signal_score": round(intent_score, 6) if intent_summary else 0.0,
        "intent_signal_count": intent_summary.signal_count if intent_summary else 0,
        "intent_signal_types": (
            ";".join(intent_summary.signal_types)
            if intent_summary and intent_summary.signal_types
            else None
        ),
        "intent_last_observed_at": (
            intent_summary.last_observed_at.isoformat()
            if intent_summary and intent_summary.last_observed_at
            else None
        ),
        "intent_top_insights": (
            "; ".join(intent_summary.top_insights)
            if intent_summary and intent_summary.top_insights
            else None
        ),
        "contact_validation_flags": (
            ";".join(sorted(set(validation_flags))) if validation_flags else None
        ),
        "contact_secondary_emails": secondary_emails,
        "contact_secondary_phones": secondary_phones,
        "data_quality_score": quality["score"],
        "data_quality_flags": quality["flags"],
        "selection_provenance": selection_provenance,
        "last_interaction_date": last_interaction,
        "priority": priority_value,
        "privacy_basis": "Legitimate Interest",
        "_conflicts": conflicts,
    }
    return result


def _parse_last_interaction(value: object | None) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        timestamp = pd.to_datetime(value, utc=True)
        return timestamp if pd.notna(timestamp) else None
    text = str(value).strip()
    if not text:
        return None
    prefer_dayfirst = not YEAR_FIRST_PATTERN.match(text)
    timestamp = pd.to_datetime(
        text,
        errors="coerce",
        dayfirst=prefer_dayfirst,
        utc=True,
    )
    if pd.isna(timestamp):
        timestamp = pd.to_datetime(
            text,
            errors="coerce",
            dayfirst=not prefer_dayfirst,
            utc=True,
        )
    if pd.isna(timestamp):
        return None
    return timestamp


def aggregate_records(
    config: PipelineConfig,
    combined: pd.DataFrame,
    intent_summaries: Mapping[str, Any] | None,
    notify_progress: Callable[[str, dict[str, Any]], None],
) -> AggregationResult:
    hooks = config.runtime_hooks
    perf_counter = hooks.perf_counter

    combined_polars = pl.from_pandas(combined, include_index=False)
    combined_polars = combined_polars.with_row_count("_row_index")
    null_slug = "__HOTPASS_NULL_SLUG__"
    group_table = (
        combined_polars.with_columns(
            pl.when(pl.col("organization_slug").is_null())
            .then(pl.lit(null_slug))
            .otherwise(pl.col("organization_slug"))
            .alias("_slug_group_key")
        )
        .group_by("_slug_group_key", maintain_order=True)
        .agg(pl.col("_row_index"))
        .with_columns(
            pl.when(pl.col("_slug_group_key") == null_slug)
            .then(pl.lit(None, dtype=pl.Utf8))
            .otherwise(pl.col("_slug_group_key"))
            .alias("organization_slug")
        )
        .select(["organization_slug", "_row_index"])
        .rename({"_row_index": "groups"})
    )

    group_total = int(group_table.height)
    notify_progress("aggregate_started", {"total": group_total})

    metrics: dict[str, Any] = {}
    aggregation_start = perf_counter()
    with pipeline_stage(
        "canonicalise",
        {
            "groups": group_total,
            "records": int(combined_polars.height),
        },
    ):
        aggregated_rows = []
        all_conflicts: list[dict[str, Any]] = []
        slug_series = (
            group_table.get_column("organization_slug") if group_total else None
        )
        index_series = group_table.get_column("groups") if group_total else None

        for index in range(group_total):
            slug = slug_series[index] if slug_series is not None else None
            indices = index_series[index] if index_series is not None else []
            group_frame = combined_polars[indices]
            row_dict = _aggregate_group(
                slug,
                group_frame.to_dicts(),
                country_code=config.country_code,
                intent_summaries=intent_summaries,
            )
            conflicts_obj = row_dict.pop("_conflicts", [])
            if isinstance(conflicts_obj, list):
                all_conflicts.extend(conflicts_obj)
            aggregated_rows.append(row_dict)
            if group_total > 0:
                completed = index + 1
                if (
                    completed == group_total
                    or completed % max(group_total // 10, 1) == 0
                ):
                    notify_progress(
                        "aggregate_progress",
                        {
                            "completed": completed,
                            "total": group_total,
                            "slug": str(slug),
                        },
                    )

        dataset = PolarsDataset.from_rows(aggregated_rows, SSOT_COLUMNS)
        dataset.sort("organization_name")
        pandas_sort_start = perf_counter()
        _ = (
            pd.DataFrame(aggregated_rows, columns=SSOT_COLUMNS)
            .sort_values("organization_name")
            .reset_index(drop=True)
        )
        pandas_sort_seconds = perf_counter() - pandas_sort_start
        metrics["pandas_sort_seconds"] = pandas_sort_seconds
        metrics["polars_transform_seconds"] = (
            dataset.timings.construction_seconds + dataset.timings.sort_seconds
        )
        if dataset.timings.sort_seconds > 0:
            metrics["polars_sort_speedup"] = (
                pandas_sort_seconds / dataset.timings.sort_seconds
            )
        else:
            metrics["polars_sort_speedup"] = (
                float("inf") if pandas_sort_seconds > 0 else 0.0
            )

        materialize_start = perf_counter()
        refined_df = dataset.to_pandas().reset_index(drop=True)
        metrics["polars_materialize_seconds"] = perf_counter() - materialize_start

    metrics["aggregation_seconds"] = perf_counter() - aggregation_start

    notify_progress(
        "aggregate_completed",
        {
            "total": group_total,
            "aggregated_records": len(refined_df),
            "conflicts": len(all_conflicts),
        },
    )

    source_counts = (
        combined_polars.select(pl.col("source_dataset"))
        .drop_nulls()
        .group_by("source_dataset")
        .len()
    )
    source_breakdown = {
        str(row["source_dataset"]): int(row["len"]) for row in source_counts.to_dicts()
    }

    return AggregationResult(
        refined_df=refined_df,
        combined_polars=combined_polars,
        conflicts=all_conflicts,
        metrics=metrics,
        source_breakdown=source_breakdown,
    )


__all__ = ["AggregationResult", "SSOT_COLUMNS", "aggregate_records"]
