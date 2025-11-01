from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..enrichment.intent import (
    IntentOrganizationSummary,
    IntentRunResult,
    IntentSignalStore,
    run_intent_plan,
)
from .config import PipelineConfig


def collect_intent_signals(
    config: PipelineConfig,
) -> tuple[
    IntentRunResult | None,
    Mapping[str, IntentOrganizationSummary] | None,
]:
    if not (config.intent_plan and config.intent_plan.enabled):
        return None, None

    store = (
        IntentSignalStore(config.intent_signal_store_path)
        if config.intent_signal_store_path is not None
        else None
    )
    result = run_intent_plan(
        config.intent_plan,
        country_code=config.country_code,
        credentials=config.intent_credentials,
        issued_at=config.runtime_hooks.datetime_factory(),
        storage=store,
    )
    return result, result.summary


def write_intent_digest(result: IntentRunResult, path: Path) -> None:
    frame = result.digest
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame.to_parquet(path, index=False)
    elif suffix == ".csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_json(path, orient="records", indent=2)
