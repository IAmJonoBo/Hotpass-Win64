"""Entity resolution helpers bridging legacy APIs with the linkage package."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

from .linkage import LinkageConfig, LinkageThresholds, link_entities
from .linkage.settings import build_splink_settings as _build_linkage_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard mirrors previous behaviour
    import splink  # type: ignore  # noqa: F401

    SPLINK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without extras
    SPLINK_AVAILABLE = False


def build_splink_settings() -> dict[str, Any]:
    """Expose the new linkage settings for compatibility with legacy imports."""

    return _build_linkage_settings()


def resolve_entities_with_splink(
    df: pd.DataFrame,
    threshold: float = 0.75,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resolve duplicate entities using the linkage module configured for Splink."""

    if not SPLINK_AVAILABLE:
        logger.warning("Splink not available, using fallback deduplication")
        return resolve_entities_fallback(df, threshold)

    high_threshold = max(0.9, threshold)
    config = LinkageConfig(
        use_splink=True,
        thresholds=LinkageThresholds(high=high_threshold, review=threshold),
    )
    result = link_entities(df, config)
    return result.deduplicated, result.matches


def _slugify(value: Any) -> str:
    """Generate a deterministic slug for fuzzy keys."""

    if value is None:
        return ""

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""

    normalised = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalised if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower())
    return slug.strip("-")


def _derive_slug_keys(df: pd.DataFrame) -> pd.Series:
    """Return a slug series for deduplication that tolerates missing data."""

    if "organization_slug" in df.columns:
        slug_series = df["organization_slug"].fillna("").astype(str).str.strip()
    else:
        slug_series = pd.Series("", index=df.index, dtype="object")

    slug_series = slug_series.str.lower().replace({"nan": ""})
    missing_mask = slug_series.eq("")

    if missing_mask.any() and "organization_name" in df.columns:
        name_slugs = df["organization_name"].apply(_slugify)
        slug_series = slug_series.mask(missing_mask, name_slugs)
        missing_mask = slug_series.eq("")

    if missing_mask.any():
        composite_source = (
            df.get("organization_name", pd.Series("", index=df.index))
            .fillna("")
            .astype(str)
            .str.strip()
            + " "
            + df.get("province", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()
            + " "
            + df.get("address_primary", pd.Series("", index=df.index))
            .fillna("")
            .astype(str)
            .str.strip()
        )
        composite_slugs = composite_source.apply(_slugify)
        slug_series = slug_series.mask(missing_mask, composite_slugs)
        missing_mask = slug_series.eq("")

    if missing_mask.any():
        fallback_series = pd.Series(
            [f"entity-{i}" for i in range(1, len(df) + 1)],
            index=df.index,
            dtype="object",
        )
        slug_series = slug_series.mask(missing_mask, fallback_series)

    return slug_series.astype("object")


def _load_entity_history(history_file: str) -> pd.DataFrame:
    """Load an existing entity registry history file if available."""

    path = Path(history_file)
    if not path.exists():
        logger.warning("Entity history file %s does not exist", history_file)
        return pd.DataFrame()

    try:
        suffix = path.suffix.lower()
        if suffix in {".json", ".ndjson"}:
            history_df = pd.read_json(path)
        elif suffix in {".csv"}:
            history_df = pd.read_csv(path)
        elif suffix in {".parquet"}:
            history_df = pd.read_parquet(path)
        elif suffix in {".xlsx", ".xls"}:
            history_df = pd.read_excel(path)
        else:
            logger.warning("Unsupported entity history format: %s", suffix or "<none>")
            return pd.DataFrame()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to load entity history from %s: %s", history_file, exc)
        return pd.DataFrame()

    if history_df.empty:
        return history_df

    # Normalise datetime columns
    for column in ("first_seen", "last_updated"):
        if column in history_df.columns:
            history_df[column] = pd.to_datetime(history_df[column], errors="coerce")

    def _ensure_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return [value]
            if isinstance(parsed, list):
                return parsed
            if parsed is None:
                return []
            return [parsed]
        return [value]

    if "name_variants" in history_df.columns:
        history_df["name_variants"] = history_df["name_variants"].apply(_ensure_list)
    else:
        history_df["name_variants"] = [[] for _ in range(len(history_df))]

    def _ensure_status_history(value: Any) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for item in _ensure_list(value):
            if isinstance(item, dict):
                status_value = item.get("status")
                status = str(status_value) if status_value is not None else ""
                entries.append({"status": status, "date": item.get("date")})
            elif item is None or (isinstance(item, float) and pd.isna(item)):
                continue
            else:
                entries.append({"status": str(item), "date": None})
        return entries

    if "status_history" in history_df.columns:
        history_df["status_history"] = history_df["status_history"].apply(_ensure_status_history)
    else:
        history_df["status_history"] = [[] for _ in range(len(history_df))]

    return history_df


def resolve_entities_fallback(
    df: pd.DataFrame,
    threshold: float = 0.75,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fallback entity resolution using simple rules when Splink is unavailable.

    Args:
        df: DataFrame with potential duplicates
        threshold: Unused in fallback mode

    Returns:
        Tuple of (deduplicated DataFrame, empty match pairs DataFrame)
    """
    logger.info("Using fallback entity resolution (slug or synthesized keys)")

    if df.empty:
        logger.info("Fallback resolution received empty dataframe")
        return df.copy(), pd.DataFrame()

    slug_keys = _derive_slug_keys(df)
    deduplicated = df.loc[~slug_keys.duplicated(keep="first")].copy()

    duplicates_removed = len(df) - len(deduplicated)
    logger.info(
        f"Fallback resolution complete: {len(df)} → {len(deduplicated)} records "
        f"({duplicates_removed} duplicates removed)"
    )

    # Return empty predictions dataframe
    predictions_df = pd.DataFrame()

    return deduplicated, predictions_df


def build_entity_registry(
    df: pd.DataFrame,
    history_file: str | None = None,
) -> pd.DataFrame:
    """Build canonical entity registry with history tracking.

    Args:
        df: Current deduplicated DataFrame
        history_file: Optional path to load historical entity data

    Returns:
        Entity registry DataFrame with history
    """
    now = pd.Timestamp.now()
    registry_source = df.copy()

    history_df = pd.DataFrame()
    if history_file:
        logger.info("Loading entity history from %s", history_file)
        history_df = _load_entity_history(history_file)

    def _row_match_keys(row: pd.Series) -> list[str]:
        keys: list[str] = []
        slug_value = str(row.get("organization_slug", "") or "").strip().lower()
        if slug_value and slug_value != "nan":
            keys.append(slug_value)

        name_value = row.get("organization_name")
        if pd.notna(name_value):
            keys.append(_slugify(name_value))
        return [key for key in dict.fromkeys(keys) if key]

    history_key_index: dict[str, list[int]] = {}
    if not history_df.empty:
        if "entity_id" not in history_df.columns:
            history_df["entity_id"] = range(1, len(history_df) + 1)
        for idx, hist_row in history_df.iterrows():
            keys = set(_row_match_keys(hist_row))
            for variant in hist_row.get("name_variants", []):
                keys.add(_slugify(variant))
            for key in keys:
                if key:
                    history_key_index.setdefault(key, []).append(idx)

    used_history_rows: set[int] = set()
    next_entity_id = (
        int(history_df["entity_id"].max()) + 1
        if not history_df.empty and pd.notna(history_df["entity_id"].max())
        else 1
    )

    registry_records: list[dict[str, Any]] = []

    for row in registry_source.itertuples(index=False, name="Row"):
        row_data = row._asdict()
        match_indices: list[int] = []
        for key in _row_match_keys(row_data):
            if key in history_key_index:
                match_indices = [i for i in history_key_index[key] if i not in used_history_rows]
                if match_indices:
                    break

        if match_indices:
            hist_idx = match_indices[0]
            used_history_rows.add(hist_idx)
            hist_row = history_df.loc[hist_idx]

            entity_id = hist_row.get("entity_id")
            if pd.isna(entity_id):
                entity_id = next_entity_id
                next_entity_id += 1

            first_seen = hist_row.get("first_seen")
            if pd.isna(first_seen):
                first_seen = now

            name_variants = list(hist_row.get("name_variants", []))
            current_name = row_data.get("organization_name")
            if pd.notna(current_name) and current_name not in name_variants:
                name_variants.append(current_name)

            status_history = list(hist_row.get("status_history", []))
            current_status = row_data.get("status")
            if pd.notna(current_status):
                status_entry = {"status": current_status, "date": now.isoformat()}
                if not status_history or status_history[-1].get("status") != current_status:
                    status_history.append(status_entry)

            combined = {**hist_row.to_dict(), **row_data}
            combined.update(
                {
                    "entity_id": int(entity_id),
                    "first_seen": first_seen,
                    "last_updated": now,
                    "name_variants": name_variants,
                    "status_history": status_history,
                }
            )
            registry_records.append(combined)
        else:
            entity_id = next_entity_id
            next_entity_id += 1
            current_name = row_data.get("organization_name")
            name_variants = [current_name] if pd.notna(current_name) else []
            current_status = row_data.get("status")
            status_history = (
                [{"status": current_status, "date": now.isoformat()}]
                if pd.notna(current_status)
                else []
            )

            record = {
                **row_data,
                "entity_id": int(entity_id),
                "first_seen": now,
                "last_updated": now,
                "name_variants": name_variants,
                "status_history": status_history,
            }
            registry_records.append(record)

    if not history_df.empty:
        remaining_history = history_df.loc[~history_df.index.isin(used_history_rows)].copy()
        if not remaining_history.empty:
            remaining_history["name_variants"] = remaining_history["name_variants"].apply(
                lambda x: x if isinstance(x, list) else []
            )
            remaining_history["status_history"] = remaining_history["status_history"].apply(
                lambda x: x if isinstance(x, list) else []
            )
            registry_records.extend(remaining_history.to_dict(orient="records"))

    registry = pd.DataFrame(registry_records)

    if not registry.empty and "entity_id" in registry.columns:
        registry["entity_id"] = registry["entity_id"].astype(int)

    logger.info(f"Built entity registry with {len(registry)} entities")

    return registry


def calculate_completeness_score(row: pd.Series) -> float:
    """Calculate a completeness score for an entity record.

    Args:
        row: DataFrame row representing an entity

    Returns:
        Completeness score (0.0 to 1.0)
    """
    # List of important fields to check
    fields = [
        "organization_name",
        "province",
        "contact_primary_email",
        "contact_primary_phone",
        "website",
        "address_primary",
        "organization_category",
    ]

    # Count non-null, non-empty fields
    filled = sum(
        1 for field in fields if field in row and pd.notna(row[field]) and str(row[field]).strip()
    )

    return filled / len(fields) if fields else 0.0


def add_ml_priority_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Add ML-driven priority and completeness scores.

    Args:
        df: DataFrame to enhance with scores

    Returns:
        DataFrame with added score columns
    """
    # Calculate completeness
    df["completeness_score"] = df.apply(calculate_completeness_score, axis=1)

    # Priority score combines completeness with quality score
    # If quality score doesn't exist, use completeness only
    if "data_quality_score" in df.columns:
        df["priority_score"] = df["completeness_score"] * 0.5 + df["data_quality_score"] * 0.5
    else:
        df["priority_score"] = df["completeness_score"]
        logger.warning("data_quality_score column not found, using completeness_score only")

    logger.info(f"Added ML priority scores to {len(df)} records")

    return df
