"""Telemetry metric helpers for the Hotpass pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class PipelineMetrics:
    """Metrics collector for pipeline operations."""

    def __init__(self, meter: Any, observation_factory: Callable[[float], Any]) -> None:
        self._meter = meter
        self.meter = meter
        self._observation_factory = observation_factory

        self.records_processed = meter.create_counter(
            name="hotpass.records.processed",
            description="Total number of records processed",
            unit="records",
        )

        self.validation_failures = meter.create_counter(
            name="hotpass.validation.failures",
            description="Number of validation failures",
            unit="failures",
        )

        self.load_duration = meter.create_histogram(
            name="hotpass.load.duration",
            description="Duration of data loading operations",
            unit="seconds",
        )

        self.aggregation_duration = meter.create_histogram(
            name="hotpass.aggregation.duration",
            description="Duration of aggregation operations",
            unit="seconds",
        )

        self.validation_duration = meter.create_histogram(
            name="hotpass.validation.duration",
            description="Duration of validation operations",
            unit="seconds",
        )

        self.write_duration = meter.create_histogram(
            name="hotpass.write.duration",
            description="Duration of write operations",
            unit="seconds",
        )

        self.automation_requests = meter.create_counter(
            name="hotpass.automation.requests",
            description="Automation delivery attempts",
            unit="requests",
        )

        self.automation_failures = meter.create_counter(
            name="hotpass.automation.failures",
            description="Failed automation deliveries",
            unit="requests",
        )

        self.automation_latency = meter.create_histogram(
            name="hotpass.automation.duration",
            description="Delivery latency for automation requests",
            unit="seconds",
        )

        self.acquisition_duration = meter.create_histogram(
            name="hotpass.acquisition.duration",
            description="Duration of acquisition activity by scope (plan, agent, provider)",
            unit="seconds",
        )

        self.acquisition_records = meter.create_counter(
            name="hotpass.acquisition.records",
            description="Number of records produced during acquisition",
            unit="records",
        )

        self.acquisition_warnings = meter.create_counter(
            name="hotpass.acquisition.warnings",
            description="Number of compliance or runtime warnings raised during acquisition",
            unit="warnings",
        )

        self.data_quality_score = meter.create_observable_gauge(
            name="hotpass.data.quality_score",
            description="Overall data quality score",
            callbacks=[self._get_quality_score],
        )

        self._latest_quality_score = 0.0

    def _get_quality_score(self, *_: Any) -> list[Any]:
        return [self._observation_factory(self._latest_quality_score)]

    def record_records_processed(self, count: int, source: str = "unknown") -> None:
        self.records_processed.add(count, {"source": source})

    def record_validation_failure(self, rule_name: str) -> None:
        self.validation_failures.add(1, {"rule": rule_name})

    def record_load_duration(self, seconds: float, source: str = "unknown") -> None:
        self.load_duration.record(seconds, {"source": source})

    def record_aggregation_duration(self, seconds: float) -> None:
        self.aggregation_duration.record(seconds)

    def record_validation_duration(self, seconds: float) -> None:
        self.validation_duration.record(seconds)

    def record_write_duration(self, seconds: float) -> None:
        self.write_duration.record(seconds)

    def update_quality_score(self, score: float) -> None:
        self._latest_quality_score = score

    def record_automation_delivery(
        self,
        *,
        target: str,
        status: str,
        endpoint: str | None,
        attempts: int,
        latency: float | None,
        idempotency: str,
    ) -> None:
        attributes: dict[str, Any] = {
            "target": target,
            "status": status,
            "attempts": attempts,
            "idempotency": idempotency,
        }
        if endpoint:
            attributes["endpoint"] = endpoint

        self.automation_requests.add(1, attributes)
        if status != "delivered":
            self.automation_failures.add(1, attributes)
        if latency is not None:
            self.automation_latency.record(latency, attributes)

    def record_acquisition_duration(
        self,
        seconds: float,
        *,
        scope: str,
        agent: str | None = None,
        provider: str | None = None,
        extra_attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = self._acquisition_attributes(scope, agent, provider, extra_attributes)
        self.acquisition_duration.record(seconds, attributes)

    def record_acquisition_records(
        self,
        count: int,
        *,
        scope: str,
        agent: str | None = None,
        provider: str | None = None,
        extra_attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = self._acquisition_attributes(scope, agent, provider, extra_attributes)
        self.acquisition_records.add(count, attributes)

    def record_acquisition_warnings(
        self,
        count: int,
        *,
        scope: str,
        agent: str | None = None,
        provider: str | None = None,
        extra_attributes: Mapping[str, Any] | None = None,
    ) -> None:
        attributes = self._acquisition_attributes(scope, agent, provider, extra_attributes)
        self.acquisition_warnings.add(count, attributes)

    @staticmethod
    def _acquisition_attributes(
        scope: str,
        agent: str | None,
        provider: str | None,
        extra_attributes: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        attributes: dict[str, Any] = {"scope": scope}
        if agent:
            attributes["agent"] = agent
        if provider:
            attributes["provider"] = provider
        if extra_attributes:
            attributes.update(extra_attributes)
        return attributes

    def record_enrichment_duration(
        self,
        seconds: float,
        *,
        fetcher: str,
        strategy: str = "unknown",
        network_used: bool = False,
    ) -> None:
        """Record duration of an enrichment operation.

        Args:
            seconds: Duration in seconds
            fetcher: Name of the fetcher used
            strategy: Enrichment strategy (deterministic, research, backfill)
            network_used: Whether network was accessed
        """
        if not hasattr(self, "enrichment_duration"):
            self.enrichment_duration = self._meter.create_histogram(
                name="hotpass.enrichment.duration",
                description="Duration of enrichment operations",
                unit="seconds",
            )

        attributes = {
            "fetcher": fetcher,
            "strategy": strategy,
            "network_used": str(network_used),
        }
        self.enrichment_duration.record(seconds, attributes)

    def record_enrichment_cache_hit(self, fetcher: str) -> None:
        """Record a cache hit for an enrichment fetcher.

        Args:
            fetcher: Name of the fetcher
        """
        if not hasattr(self, "enrichment_cache_hits"):
            self.enrichment_cache_hits = self._meter.create_counter(
                name="hotpass.enrichment.cache_hits",
                description="Number of enrichment cache hits",
                unit="hits",
            )

        self.enrichment_cache_hits.add(1, {"fetcher": fetcher})

    def record_enrichment_cache_miss(self, fetcher: str) -> None:
        """Record a cache miss for an enrichment fetcher.

        Args:
            fetcher: Name of the fetcher
        """
        if not hasattr(self, "enrichment_cache_misses"):
            self.enrichment_cache_misses = self._meter.create_counter(
                name="hotpass.enrichment.cache_misses",
                description="Number of enrichment cache misses",
                unit="misses",
            )

        self.enrichment_cache_misses.add(1, {"fetcher": fetcher})

    def record_enrichment_records(
        self,
        count: int,
        *,
        fetcher: str,
        strategy: str = "unknown",
        confidence: float | None = None,
    ) -> None:
        """Record number of records enriched.

        Args:
            count: Number of records enriched
            fetcher: Name of the fetcher used
            strategy: Enrichment strategy
            confidence: Optional average confidence score
        """
        if not hasattr(self, "enrichment_records"):
            self.enrichment_records = self._meter.create_counter(
                name="hotpass.enrichment.records",
                description="Number of records enriched",
                unit="records",
            )

        attributes: dict[str, Any] = {
            "fetcher": fetcher,
            "strategy": strategy,
        }
        if confidence is not None:
            attributes["confidence_bucket"] = f"{int(confidence * 10) * 10}%"

        self.enrichment_records.add(count, attributes)

    def _ensure_research_instruments(self) -> None:
        if hasattr(self, "research_queries"):
            return
        self.research_queries = self._meter.create_counter(
            name="hotpass.research.queries",
            description="Number of SearXNG queries executed",
            unit="queries",
        )
        self.research_query_duration = self._meter.create_histogram(
            name="hotpass.research.query.duration",
            description="Duration of SearXNG queries",
            unit="seconds",
        )
        self.research_query_results = self._meter.create_counter(
            name="hotpass.research.query.results",
            description="Result count returned by SearXNG queries",
            unit="results",
        )
        self.research_cache_hits = self._meter.create_counter(
            name="hotpass.research.cache.hits",
            description="Number of cached SearXNG responses reused",
            unit="hits",
        )
        self.research_cache_misses = self._meter.create_counter(
            name="hotpass.research.cache.misses",
            description="Number of SearXNG cache misses",
            unit="misses",
        )
        self.research_crawl_duration = self._meter.create_histogram(
            name="hotpass.research.crawl.duration",
            description="Duration of research crawl attempts",
            unit="seconds",
        )
        self.research_crawl_retries = self._meter.create_counter(
            name="hotpass.research.crawl.retries",
            description="Retry attempts during research crawls",
            unit="retries",
        )
        self.research_crawl_failures = self._meter.create_counter(
            name="hotpass.research.crawl.failures",
            description="Failed research crawl attempts",
            unit="failures",
        )

    def record_research_query(
        self,
        seconds: float,
        *,
        query: str,
        result_count: int,
        cached: bool,
        status: str,
    ) -> None:
        self._ensure_research_instruments()
        attributes = {
            "query": query,
            "cached": str(cached),
            "status": status,
        }
        self.research_queries.add(1, attributes)
        self.research_query_duration.record(seconds, attributes)
        self.research_query_results.add(result_count, attributes)

    def record_research_cache_hit(self, query: str) -> None:
        self._ensure_research_instruments()
        self.research_cache_hits.add(1, {"query": query})

    def record_research_cache_miss(self, query: str) -> None:
        self._ensure_research_instruments()
        self.research_cache_misses.add(1, {"query": query})

    def record_research_crawl(
        self,
        seconds: float,
        *,
        url: str,
        status: str,
        attempts: int,
    ) -> None:
        self._ensure_research_instruments()
        attributes = {"url": url, "status": status, "attempts": attempts}
        self.research_crawl_duration.record(seconds, attributes)

    def record_research_crawl_retry(self, *, url: str, attempt: int) -> None:
        self._ensure_research_instruments()
        self.research_crawl_retries.add(1, {"url": url, "attempt": attempt})

    def record_research_crawl_failure(self, *, url: str, reason: str) -> None:
        self._ensure_research_instruments()
        self.research_crawl_failures.add(1, {"url": url, "reason": reason})
