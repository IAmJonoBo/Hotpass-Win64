from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from ..compliance import redact_dataframe
from ..data_sources import (
    ExcelReadOptions,
    load_contact_database,
    load_reachout_database,
    load_sacaa_cleaned,
)
from ..data_sources.agents import run_plan as run_acquisition_plan
from ..normalization import normalize_province, slugify
from .config import PipelineConfig

_SOURCE_COLUMNS: list[str] = [
    "organization_name",
    "source_dataset",
    "source_record_id",
    "province",
    "area",
    "address",
    "category",
    "organization_type",
    "status",
    "website",
    "planes",
    "description",
    "notes",
    "last_interaction_date",
    "priority",
    "contact_names",
    "contact_roles",
    "contact_emails",
    "contact_phones",
]


def _deduplicate_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.columns.is_unique:
        return frame
    deduped = frame.copy()
    new_columns: list[str] = []
    occurrences: dict[str, int] = {}
    for name in deduped.columns:
        count = occurrences.get(name, 0)
        if count == 0:
            new_columns.append(name)
        else:
            new_columns.append(f"{name}__dup{count}")
        occurrences[name] = count + 1
    deduped.columns = new_columns
    return deduped


def _ensure_source_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if not frame.empty:
        missing = [column for column in _SOURCE_COLUMNS if column not in frame.columns]
        if not missing:
            return frame
        for column in missing:
            frame[column] = pd.Series([pd.NA] * len(frame), dtype="object")
        return frame
    for column in _SOURCE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.Series(dtype="object")
    return frame


def _normalise_source_frame(frame: pd.DataFrame) -> pd.DataFrame:
    attrs = dict(frame.attrs)

    if frame.columns.is_unique:
        working = frame.copy(deep=True)
    else:
        # Pandas returns a DataFrame when selecting columns with duplicate
        # labels, which breaks downstream expectations that individual column
        # access yields row data. Deduplicate the working copy and mirror the
        # updated labels back onto the original frame so any callers sharing the
        # reference observe consistent column names.
        working = _deduplicate_columns(frame)
        frame.columns = working.columns

    working = _ensure_source_columns(working)
    ordered = _SOURCE_COLUMNS + [
        column for column in working.columns if column not in _SOURCE_COLUMNS
    ]
    normalised = working.loc[:, ordered]
    normalised.attrs = attrs
    return normalised


def _load_agent_frame(config: PipelineConfig) -> tuple[pd.DataFrame, dict[str, float]]:
    if config.preloaded_agent_frame is not None:
        frame = _normalise_source_frame(config.preloaded_agent_frame)
        timings = {
            f"agent:{timing.agent_name}": timing.seconds
            for timing in config.preloaded_agent_timings
        }
        return frame, timings

    if not (config.acquisition_plan and config.acquisition_plan.enabled):
        return pd.DataFrame(), {}

    frame, agent_timings, warnings = run_acquisition_plan(
        config.acquisition_plan,
        country_code=config.country_code,
        credentials=config.agent_credentials,
    )
    frame = _normalise_source_frame(frame)
    config.preloaded_agent_frame = frame.copy(deep=True)
    config.preloaded_agent_timings = list(agent_timings)
    config.preloaded_agent_warnings.extend(warnings)
    timings = {f"agent:{timing.agent_name}": timing.seconds for timing in agent_timings}
    return frame, timings


def load_sources(
    input_dir: Path,
    country_code: str,
    excel_options: ExcelReadOptions | None,
) -> Mapping[str, pd.DataFrame]:
    loaders = {
        "Reachout Database": load_reachout_database,
        "Contact Database": load_contact_database,
        "SACAA Cleaned": load_sacaa_cleaned,
    }
    frames: dict[str, pd.DataFrame] = {}
    for label, loader in loaders.items():
        try:
            frame = loader(input_dir, country_code, excel_options)
        except FileNotFoundError:
            continue
        if frame.empty:
            continue
        frames[label] = _normalise_source_frame(frame)
    return frames


def ingest_sources(
    config: PipelineConfig,
) -> tuple[pd.DataFrame, dict[str, float], list[dict[str, Any]]]:
    agent_frame, agent_timings = _load_agent_frame(config)

    source_timings: dict[str, float] = dict(agent_timings)
    frames: list[pd.DataFrame] = []
    if not agent_frame.empty:
        frames.append(agent_frame)

    contract_notices: list[dict[str, Any]] = []
    for label, frame in load_sources(
        config.input_dir, config.country_code, config.excel_options
    ).items():
        frames.append(frame)
        source_timings[label] = frame.attrs.get("load_seconds", 0.0)
        notices = frame.attrs.get("contract_notices", [])
        for notice in notices:
            enriched_notice = dict(notice)
            enriched_notice.setdefault("source_dataset", label)
            contract_notices.append(enriched_notice)

    if not frames:
        return _empty_sources_frame(), source_timings, contract_notices

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = _normalise_source_frame(combined)
    combined["organization_slug"] = combined["organization_name"].apply(slugify)
    combined["province"] = combined["province"].apply(normalize_province)
    return combined, source_timings, contract_notices


def apply_redaction(
    config: PipelineConfig, frame: pd.DataFrame
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    if not config.pii_redaction.enabled:
        return frame, []
    return redact_dataframe(frame, config.pii_redaction)


def _empty_sources_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_SOURCE_COLUMNS)
