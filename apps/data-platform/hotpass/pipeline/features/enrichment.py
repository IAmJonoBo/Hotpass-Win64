"""External enrichment feature strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pandas import DataFrame

from ...enrichment import (
    CacheManager,
    enrich_dataframe_with_websites,
    enrich_dataframe_with_websites_concurrent,
)
from ..base import PipelineResult
from .base import FeatureContext, PipelineFeatureStrategy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EnrichmentFeature(PipelineFeatureStrategy):
    """Augment organisations with external data sources."""

    name: str = "enrichment"

    def is_enabled(self, context: FeatureContext) -> bool:
        config = context.enhanced_config
        return bool(config.enable_enrichment and config.enrich_websites)

    def apply(self, result: PipelineResult, context: FeatureContext) -> PipelineResult:
        if not self.is_enabled(context):
            return result

        df: DataFrame = result.refined
        with context.trace_factory(self.name):
            logger.info("Running external data enrichment...")
            try:
                cache = CacheManager(db_path=context.enhanced_config.cache_path)
                if "website" in df.columns:
                    concurrency = max(1, context.enhanced_config.enrichment_concurrency)
                    if concurrency > 1 and len(df) > 1:
                        result.refined = enrich_dataframe_with_websites_concurrent(
                            df,
                            website_column="website",
                            cache=cache,
                            concurrency=concurrency,
                        )
                    else:
                        result.refined = enrich_dataframe_with_websites(
                            df,
                            website_column="website",
                            cache=cache,
                        )
                logger.info("External enrichment complete")
                stats = cache.stats()
                logger.info("Cache stats: %s", stats)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("External enrichment failed: %s", exc)
        return result
