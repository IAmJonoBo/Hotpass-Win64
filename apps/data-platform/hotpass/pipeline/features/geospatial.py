"""Geospatial feature strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pandas import DataFrame

from ...geospatial import geocode_dataframe, normalize_address
from ...telemetry import pipeline_stage
from ..base import PipelineResult
from .base import FeatureContext, PipelineFeatureStrategy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeospatialFeature(PipelineFeatureStrategy):
    """Normalise and enrich addresses with latitude/longitude metadata."""

    name: str = "geospatial"

    def is_enabled(self, context: FeatureContext) -> bool:
        config = context.enhanced_config
        return bool(config.enable_geospatial and config.geocode_addresses)

    def apply(self, result: PipelineResult, context: FeatureContext) -> PipelineResult:
        if not self.is_enabled(context):
            return result

        df: DataFrame = result.refined
        with context.trace_factory(self.name):
            logger.info("Running geospatial enrichment...")
            try:
                with pipeline_stage("geospatial", {"records": len(df)}):
                    if "address_primary" in df.columns:
                        df["address_primary"] = df["address_primary"].apply(normalize_address)
                    result.refined = geocode_dataframe(
                        df,
                        address_column="address_primary",
                        country_column="country",
                    )
                    logger.info("Geospatial enrichment complete")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Geospatial enrichment failed: %s", exc)
        return result
