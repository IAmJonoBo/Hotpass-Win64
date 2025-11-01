"""Execute probabilistic linkage with Splink and RapidFuzz fallbacks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .blocking import review_payload_fields
from .comparators import (
    add_normalized_columns,
    rapidfuzz_partial_ratio,
    rapidfuzz_token_set_ratio,
    rapidfuzz_token_sort_ratio,
    register_duckdb_functions,
)
from .config import LinkageConfig, LinkagePersistence, LinkageThresholds
from .review import LabelStudioConnector, serialize_review_tasks, write_reviewer_decisions
from .settings import build_splink_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LinkageResult:
    """Outputs from a linkage pass, including review metadata."""

    deduplicated: pd.DataFrame
    matches: pd.DataFrame
    review_queue: pd.DataFrame
    thresholds: LinkageThresholds
    persisted_paths: dict[str, Path] = field(default_factory=dict)

    def persist(self, persistence: LinkagePersistence) -> dict[str, Path]:
        persistence.ensure()
        paths: dict[str, Path] = {}

        matches_path = persistence.matches_path()
        self.matches.to_parquet(matches_path, index=False)
        paths["matches"] = matches_path

        review_path = persistence.review_path()
        self.review_queue.to_parquet(review_path, index=False)
        paths["review_queue"] = review_path

        metadata_path = persistence.metadata_path()
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "thresholds": self.thresholds.as_dict(),
                    "match_count": int(len(self.matches)),
                    "review_count": int(len(self.review_queue)),
                },
                handle,
                indent=2,
            )
        paths["metadata"] = metadata_path

        self.persisted_paths = paths
        return paths


def link_entities(df: pd.DataFrame, config: LinkageConfig) -> LinkageResult:
    """Run the probabilistic entity linkage flow."""

    working = add_normalized_columns(df)
    working = working.reset_index(drop=True).copy()
    working["__linkage_id"] = working.index.astype(int)

    if config.use_splink:
        result = _link_with_splink(working, df, config.thresholds)
    else:
        result = _link_with_rules(working, df, config.thresholds)

    result.persist(config.persistence)

    if config.label_studio is not None:
        connector = LabelStudioConnector(config.label_studio)
        payload_fields = review_payload_fields(config.review_payload_fields)
        review_records = result.review_queue.to_dict("records")
        tasks = serialize_review_tasks(review_records, config.thresholds, payload_fields)
        connector.submit_tasks(tasks)
        decisions = connector.fetch_completed_annotations()
        write_reviewer_decisions(decisions, config.persistence.decisions_path(), config.thresholds)

    return result


def _link_with_splink(
    working: pd.DataFrame,
    original: pd.DataFrame,
    thresholds: LinkageThresholds,
) -> LinkageResult:
    try:
        from splink.duckdb.linker import DuckDBLinker  # type: ignore
    except ImportError:
        logger.warning("Splink not installed; falling back to RapidFuzz rule-based linkage")
        return _link_with_rules(working, original, thresholds)

    try:
        import duckdb
    except ImportError:
        logger.warning("duckdb not available; using RapidFuzz rule-based linkage")
        return _link_with_rules(working, original, thresholds)

    connection = duckdb.connect(database=":memory:")
    register_duckdb_functions(connection)
    settings = build_splink_settings()

    linker = DuckDBLinker(working, settings, connection=connection)
    predictions = linker.predict(threshold_match_probability=thresholds.review)
    predictions_df = predictions.as_pandas_dataframe()

    predictions_df["classification"] = predictions_df["match_probability"].apply(
        thresholds.classify
    )
    matches_df = predictions_df[predictions_df["classification"] != "reject"].copy()
    review_df = matches_df[matches_df["classification"] == "review"].copy()

    matches_df = _attach_pair_context(matches_df, working, original)
    review_df = _attach_pair_context(review_df, working, original)

    clusters = linker.cluster_pairwise_predictions_at_threshold(
        predictions, threshold_match_probability=thresholds.review
    )
    cluster_df = clusters.as_pandas_dataframe()

    deduplicated = _deduplicate_from_clusters(working, original, cluster_df)

    try:  # pragma: no cover - best effort cleanup
        connection.close()
    except Exception:  # pragma: no cover - best effort cleanup
        logger.debug("Failed to close linkage connection cleanly", exc_info=True)

    return LinkageResult(
        deduplicated=deduplicated,
        matches=matches_df.reset_index(drop=True),
        review_queue=review_df.reset_index(drop=True),
        thresholds=thresholds,
    )


def _link_with_rules(
    working: pd.DataFrame,
    original: pd.DataFrame,
    thresholds: LinkageThresholds,
) -> LinkageResult:
    logger.info("Running RapidFuzz rule-based linkage")

    keys = working["linkage_slug"].fillna("")
    composite = (
        working["linkage_name"].fillna("")
        + "|"
        + working["linkage_province"].fillna("")
        + "|"
        + working["linkage_email"].fillna("")
    )
    keys = keys.where(keys.astype(bool), composite)
    fallback = working.index.map(lambda value: f"row-{value}")
    keys = keys.where(keys.astype(bool), fallback)

    pair_records: list[dict[str, Any]] = []

    for _slug, group in working.groupby(keys):
        if len(group) < 2:
            continue
        indices = group.index.to_list()
        for i, left_idx in enumerate(indices):
            for right_idx in indices[i + 1 :]:
                left = working.loc[left_idx]
                right = working.loc[right_idx]
                name_score = rapidfuzz_token_sort_ratio(left["linkage_name"], right["linkage_name"])
                email_score = (
                    1.0
                    if left["linkage_email"] and left["linkage_email"] == right["linkage_email"]
                    else 0.0
                )
                phone_score = rapidfuzz_partial_ratio(left["linkage_phone"], right["linkage_phone"])
                province_score = (
                    1.0
                    if left["linkage_province"]
                    and left["linkage_province"] == right["linkage_province"]
                    else 0.0
                )
                website_score = (
                    1.0
                    if left["linkage_website"]
                    and left["linkage_website"] == right["linkage_website"]
                    else 0.0
                )
                fuzzy_bonus = rapidfuzz_token_set_ratio(left["linkage_name"], right["linkage_name"])

                match_probability = min(
                    1.0,
                    (0.45 * name_score)
                    + (0.2 * email_score)
                    + (0.15 * phone_score)
                    + (0.1 * province_score)
                    + (0.05 * website_score)
                    + (0.05 * fuzzy_bonus),
                )
                classification = thresholds.classify(match_probability)

                record: dict[str, Any] = {
                    "left_index": int(left_idx),
                    "right_index": int(right_idx),
                    "match_probability": match_probability,
                    "classification": classification,
                }
                for column in original.columns:
                    record[f"left_{column}"] = original.iloc[left_idx][column]
                    record[f"right_{column}"] = original.iloc[right_idx][column]
                pair_records.append(record)

    matches_df = pd.DataFrame(pair_records)
    if matches_df.empty:
        review_df = matches_df.copy()
    else:
        review_df = matches_df[matches_df["classification"] == "review"].copy()

    dedupe_mask = ~keys.duplicated(keep="first")
    deduplicated = original.loc[dedupe_mask].reset_index(drop=True)

    return LinkageResult(
        deduplicated=deduplicated,
        matches=matches_df.reset_index(drop=True),
        review_queue=review_df.reset_index(drop=True),
        thresholds=thresholds,
    )


def _rename_pair_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.copy()
    rename_map: dict[str, str] = {}
    for column in list(renamed.columns):
        if column.endswith("_l"):
            rename_map[column] = f"left_{column[:-2]}"
        elif column.endswith("_r"):
            rename_map[column] = f"right_{column[:-2]}"
    if rename_map:
        renamed = renamed.rename(columns=rename_map)
    return renamed


def _attach_pair_context(
    df: pd.DataFrame, working: pd.DataFrame, original: pd.DataFrame
) -> pd.DataFrame:
    if df.empty:
        return df.reset_index(drop=True)

    enriched = _rename_pair_columns(df)
    if "__linkage_id_l" not in enriched.columns or "__linkage_id_r" not in enriched.columns:
        return enriched.reset_index(drop=True)

    left_map = pd.concat([working[["__linkage_id"]], original.add_prefix("left_")], axis=1).rename(
        columns={"__linkage_id": "__linkage_id_l"}
    )
    right_map = pd.concat(
        [working[["__linkage_id"]], original.add_prefix("right_")], axis=1
    ).rename(columns={"__linkage_id": "__linkage_id_r"})

    enriched = enriched.merge(left_map, on="__linkage_id_l", how="left")
    enriched = enriched.merge(right_map, on="__linkage_id_r", how="left")
    return enriched.reset_index(drop=True)


def _deduplicate_from_clusters(
    working: pd.DataFrame,
    original: pd.DataFrame,
    clusters: pd.DataFrame,
) -> pd.DataFrame:
    if clusters.empty:
        return original.copy().reset_index(drop=True)

    id_column = "unique_id" if "unique_id" in clusters.columns else "__linkage_id"
    if id_column not in clusters.columns or "cluster_id" not in clusters.columns:
        return original.copy().reset_index(drop=True)

    cluster_map = clusters[[id_column, "cluster_id"]].dropna()
    cluster_map = cluster_map.astype({id_column: int, "cluster_id": int})

    merged = working.merge(cluster_map, left_on="__linkage_id", right_on=id_column, how="left")
    merged["cluster_id"] = merged["cluster_id"].fillna(-1).astype(int)

    dedup_indices = merged.sort_values("__linkage_id").drop_duplicates("cluster_id", keep="first")[
        "__linkage_id"
    ]
    deduplicated = original.iloc[dedup_indices].copy()
    return deduplicated.reset_index(drop=True)
