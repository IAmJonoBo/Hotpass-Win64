"""Entity resolution feature strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pandas import DataFrame

from ...entity_resolution import add_ml_priority_scores, resolve_entities_fallback
from ...linkage import LinkageConfig, LinkageResult, LinkageThresholds, link_entities
from ...telemetry import pipeline_stage
from ..base import PipelineResult
from .base import FeatureContext, PipelineFeatureStrategy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EntityResolutionFeature(PipelineFeatureStrategy):
    """Apply probabilistic and rule-based entity resolution when enabled."""

    name: str = "entity_resolution"

    def is_enabled(self, context: FeatureContext) -> bool:  # noqa: D401 - Protocol contract
        return context.enhanced_config.enable_entity_resolution

    def apply(self, result: PipelineResult, context: FeatureContext) -> PipelineResult:
        if not self.is_enabled(context):
            return result

        config = context.enhanced_config
        df: DataFrame = result.refined
        linkage_result: LinkageResult | None = None

        with context.trace_factory(self.name):
            with pipeline_stage("link", {"records": len(df)}):
                logger.info("Running entity resolution...")
                try:
                    match_threshold = config.linkage_match_threshold or max(
                        0.9, config.entity_resolution_threshold
                    )
                    high_value = max(match_threshold, config.entity_resolution_threshold)
                    thresholds = LinkageThresholds(
                        high=high_value,
                        review=config.entity_resolution_threshold,
                    )
                    base_linkage_config = config.linkage_config or LinkageConfig()
                    root_dir = (
                        Path(config.linkage_output_dir)
                        if config.linkage_output_dir
                        else base_linkage_config.persistence.root_dir
                    )
                    configured = base_linkage_config.with_output_root(root_dir)
                    configured.use_splink = config.use_splink
                    configured.thresholds = thresholds

                    linkage_result = link_entities(df, configured)
                    df = linkage_result.deduplicated
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.error("Entity resolution failed: %s", exc)
                    logger.warning(
                        "Falling back to rule-based entity resolution using threshold %.2f",
                        config.entity_resolution_threshold,
                    )
                    df, _ = resolve_entities_fallback(df, config.entity_resolution_threshold)
                    linkage_result = None

                df = add_ml_priority_scores(df)
                logger.info("Entity resolution complete: %s unique entities", len(df))

        result.refined = df
        result.linkage = linkage_result
        return result
