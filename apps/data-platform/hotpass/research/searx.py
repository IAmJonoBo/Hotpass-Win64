"""SearXNG integration utilities for adaptive research flows."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence

try:  # pragma: no cover - optional dependency guard
    import requests
except ImportError:  # pragma: no cover - handled in service constructor
    requests = None  # type: ignore[assignment]

from hotpass.observability import get_pipeline_metrics, trace_operation
from hotpass.telemetry.metrics import PipelineMetrics

LOGGER = logging.getLogger(__name__)


class SearxServiceError(RuntimeError):
    """Raised when the SearXNG API cannot be contacted successfully."""


@dataclass(slots=True)
class SearxServiceSettings:
    """Runtime configuration for SearXNG integration."""

    enabled: bool = False
    base_url: str = "http://localhost:8080"
    api_key: str | None = None
    api_key_header: str = "Authorization"
    api_key_prefix: str | None = "Bearer"
    timeout: float = 10.0
    max_results: int = 25
    categories: tuple[str, ...] = ()
    engines: tuple[str, ...] = ()
    language: str | None = None
    deduplicate: bool = True
    stop_on_first: bool = True
    cache_dir: Path | None = None
    cache_ttl_seconds: float = 3600.0
    min_interval_seconds: float = 1.0
    burst: int | None = None
    trace_queries: bool = True
    metrics_enabled: bool = True
    user_agent: str | None = "Hotpass/Research"
    default_params: Mapping[str, Any] = field(default_factory=dict)
    crawl_retry_attempts: int = 3
    crawl_retry_backoff_seconds: float = 1.5
    auto_crawl: bool = True

    @classmethod
    def from_payload(cls, payload: Any | None) -> SearxServiceSettings:
        """Instantiate settings from a mapping or Pydantic model."""

        if payload is None:
            return cls()
        if isinstance(payload, cls):
            return payload
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(mode="python")  # type: ignore[call-arg]
        elif isinstance(payload, Mapping):
            data = dict(payload)
        else:  # pragma: no cover - defensive guard
            msg = f"Unsupported payload type for SearxServiceSettings: {type(payload)!r}"
            raise TypeError(msg)

        searx_data: MutableMapping[str, Any]
        if "searx" in data and isinstance(data["searx"], Mapping):
            searx_data = dict(data["searx"])
        else:
            searx_data = dict(data)

        categories = _coerce_tuple(searx_data.pop("categories", ()))
        engines = _coerce_tuple(searx_data.pop("engines", ()))
        default_params = dict(searx_data.pop("default_params", {}))

        cache_payload = searx_data.pop("cache", None)
        cache_dir = None
        cache_ttl = None
        if isinstance(cache_payload, Mapping):
            cache_dir_raw = cache_payload.get("directory")
            if cache_dir_raw is not None:
                cache_dir = Path(cache_dir_raw)
            ttl_candidate = cache_payload.get("ttl_seconds")
            if ttl_candidate is not None:
                cache_ttl = float(ttl_candidate)

        throttle_payload = searx_data.pop("throttle", None)
        min_interval = None
        burst = None
        if isinstance(throttle_payload, Mapping):
            min_interval_candidate = throttle_payload.get("min_interval_seconds")
            if min_interval_candidate is not None:
                min_interval = float(min_interval_candidate)
            burst_candidate = throttle_payload.get("burst")
            if burst_candidate is not None:
                burst = int(burst_candidate)

        settings = cls(
            enabled=bool(searx_data.get("enabled", False)),
            base_url=str(searx_data.get("base_url", cls.base_url)),
            api_key=searx_data.get("api_key"),
            api_key_header=str(searx_data.get("api_key_header", cls.api_key_header)),
            api_key_prefix=searx_data.get("api_key_prefix", cls.api_key_prefix),
            timeout=float(searx_data.get("timeout", cls.timeout)),
            max_results=int(searx_data.get("max_results", cls.max_results)),
            categories=categories,
            engines=engines,
            language=searx_data.get("language"),
            deduplicate=bool(searx_data.get("deduplicate", cls.deduplicate)),
            stop_on_first=bool(searx_data.get("stop_on_first", cls.stop_on_first)),
            cache_dir=cache_dir,
            cache_ttl_seconds=float(cache_ttl if cache_ttl is not None else cls.cache_ttl_seconds),
            min_interval_seconds=float(
                min_interval if min_interval is not None else cls.min_interval_seconds
            ),
            burst=burst,
            trace_queries=bool(searx_data.get("trace_queries", cls.trace_queries)),
            metrics_enabled=bool(searx_data.get("metrics_enabled", cls.metrics_enabled)),
            user_agent=searx_data.get("user_agent", cls.user_agent),
            default_params=default_params,
            crawl_retry_attempts=int(
                searx_data.get("crawl_retry_attempts", cls.crawl_retry_attempts)
            ),
            crawl_retry_backoff_seconds=float(
                searx_data.get(
                    "crawl_retry_backoff_seconds", cls.crawl_retry_backoff_seconds
                )
            ),
            auto_crawl=bool(searx_data.get("auto_crawl", cls.auto_crawl)),
        )
        return settings

    @classmethod
    def from_environment(cls) -> SearxServiceSettings:
        """Derive settings from conventional environment variables."""

        env = os.getenv
        enabled = env("HOTPASS_SEARX_ENABLED")
        base_url = env("HOTPASS_SEARX_URL")
        api_key = env("HOTPASS_SEARX_API_KEY")
        api_key_header = env("HOTPASS_SEARX_API_KEY_HEADER")
        api_key_prefix = env("HOTPASS_SEARX_API_KEY_PREFIX")
        timeout = env("HOTPASS_SEARX_TIMEOUT")
        max_results = env("HOTPASS_SEARX_MAX_RESULTS")
        categories = env("HOTPASS_SEARX_CATEGORIES")
        engines = env("HOTPASS_SEARX_ENGINES")
        language = env("HOTPASS_SEARX_LANGUAGE")
        deduplicate = env("HOTPASS_SEARX_DEDUPLICATE")
        stop_on_first = env("HOTPASS_SEARX_STOP_ON_FIRST")
        cache_dir = env("HOTPASS_SEARX_CACHE_DIR")
        cache_ttl = env("HOTPASS_SEARX_CACHE_TTL")
        min_interval = env("HOTPASS_SEARX_MIN_INTERVAL")
        burst = env("HOTPASS_SEARX_BURST")
        crawl_attempts = env("HOTPASS_SEARX_CRAWL_ATTEMPTS")
        crawl_backoff = env("HOTPASS_SEARX_CRAWL_BACKOFF")
        auto_crawl = env("HOTPASS_SEARX_AUTO_CRAWL")

        settings = cls()
        if enabled is not None:
            settings.enabled = _coerce_bool(enabled)
        if base_url:
            settings.base_url = base_url
        if api_key:
            settings.api_key = api_key
        if api_key_header:
            settings.api_key_header = api_key_header
        if api_key_prefix is not None:
            settings.api_key_prefix = api_key_prefix
        if timeout:
            settings.timeout = float(timeout)
        if max_results:
            settings.max_results = int(max_results)
        if categories:
            settings.categories = _split_tokens(categories)
        if engines:
            settings.engines = _split_tokens(engines)
        if language:
            settings.language = language
        if deduplicate is not None:
            settings.deduplicate = _coerce_bool(deduplicate)
        if stop_on_first is not None:
            settings.stop_on_first = _coerce_bool(stop_on_first)
        if cache_dir:
            settings.cache_dir = Path(cache_dir)
        if cache_ttl:
            settings.cache_ttl_seconds = float(cache_ttl)
        if min_interval:
            settings.min_interval_seconds = float(min_interval)
        if burst:
            try:
                settings.burst = int(burst)
            except ValueError:  # pragma: no cover - defensive guard
                LOGGER.warning("Invalid HOTPASS_SEARX_BURST value: %s", burst)
        if crawl_attempts:
            settings.crawl_retry_attempts = max(1, int(float(crawl_attempts)))
        if crawl_backoff:
            settings.crawl_retry_backoff_seconds = float(crawl_backoff)
        if auto_crawl is not None:
            settings.auto_crawl = _coerce_bool(auto_crawl)
        return settings


@dataclass(slots=True)
class SearxQuery:
    """Query payload sent to SearXNG."""

    term: str
    categories: tuple[str, ...] = ()
    engines: tuple[str, ...] = ()
    language: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)

    def cache_key(self) -> str:
        payload = {
            "term": self.term,
            "categories": list(self.categories),
            "engines": list(self.engines),
            "language": self.language,
            "params": dict(self.params),
        }
        serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    def as_params(self, defaults: Mapping[str, Any]) -> dict[str, Any]:
        merged = dict(defaults)
        merged.update(self.params)
        merged.setdefault("q", self.term)
        if self.categories:
            merged.setdefault("categories", ",".join(self.categories))
        if self.engines:
            merged.setdefault("engines", ",".join(self.engines))
        if self.language:
            merged.setdefault("language", self.language)
        merged.setdefault("format", "json")
        return merged


@dataclass(slots=True)
class SearxResult:
    """Result item returned by SearXNG."""

    title: str
    url: str
    engine: str | None = None
    score: float | None = None
    snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "engine": self.engine,
            "score": self.score,
            "snippet": self.snippet,
        }


@dataclass(slots=True)
class SearxResponse:
    """Aggregated response after executing one or more queries."""

    queries: tuple[SearxQuery, ...]
    results: tuple[SearxResult, ...]
    from_cache: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "queries": [
                {
                    "term": query.term,
                    "categories": list(query.categories),
                    "engines": list(query.engines),
                    "language": query.language,
                }
                for query in self.queries
            ],
            "results": [result.to_dict() for result in self.results],
            "from_cache": self.from_cache,
        }


class SearxService:
    """Client responsible for coordinating SearXNG queries and caching."""

    def __init__(
        self,
        settings: SearxServiceSettings,
        *,
        cache_root: Path,
        session_factory: Callable[[], requests.Session] | None = None,
        metrics: PipelineMetrics | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests is None:  # pragma: no cover - defensive guard
            msg = "requests must be installed to use the SearxService"
            raise RuntimeError(msg)

        self.settings = settings
        self.cache_root = cache_root / "searx"
        if settings.cache_dir is not None:
            self.cache_root = settings.cache_dir
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self._session_factory = session_factory or requests.Session
        self._session: requests.Session | None = None
        self._metrics = metrics if metrics is not None else get_pipeline_metrics()
        self._clock = clock
        self._sleep = sleeper
        self._last_request: float | None = None
        self._burst_tokens: int | None = None

    def build_queries(self, terms: Iterable[str]) -> list[SearxQuery]:
        """Construct queries using configured defaults."""

        queries: list[SearxQuery] = []
        for term in terms:
            cleaned = str(term).strip()
            if not cleaned:
                continue
            queries.append(
                SearxQuery(
                    term=cleaned,
                    categories=self.settings.categories,
                    engines=self.settings.engines,
                    language=self.settings.language,
                )
            )
        return queries

    def search(self, queries: Sequence[SearxQuery]) -> SearxResponse:
        """Execute the provided queries and aggregate unique results."""

        if not self.settings.enabled:
            return SearxResponse(tuple(queries), (), False)

        if not queries:
            return SearxResponse((), (), False)

        aggregated: list[SearxResult] = []
        seen_urls: set[str] = set()
        from_cache = True

        for query in queries:
            results, cached = self._execute_query(query)
            from_cache = from_cache and cached
            for result in results:
                url_key = _normalise_url(result.url)
                if not self.settings.deduplicate or url_key not in seen_urls:
                    seen_urls.add(url_key)
                    aggregated.append(result)
            if aggregated and self.settings.stop_on_first:
                break

        limited_results = tuple(aggregated[: self.settings.max_results])
        return SearxResponse(tuple(queries), limited_results, from_cache)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _execute_query(self, query: SearxQuery) -> tuple[list[SearxResult], bool]:
        cache_key = query.cache_key()
        cached_payload = self._load_from_cache(cache_key)
        if cached_payload is not None:
            self._record_cache_hit(query.term)
            results = [self._to_result(item) for item in cached_payload]
            return results, True

        self._record_cache_miss(query.term)
        self._respect_rate_limit()
        session = self._get_session()
        params = query.as_params(self.settings.default_params)
        headers = self._build_headers()

        duration = 0.0
        start = self._clock()
        status = "success"
        try:
            with trace_operation(
                "research.searx.query",
                {
                    "hotpass.research.query": query.term,
                    "hotpass.research.categories": ",".join(query.categories)
                    if query.categories
                    else "",
                    "hotpass.research.engines": ",".join(query.engines)
                    if query.engines
                    else "",
                },
            ) if self.settings.trace_queries else _null_context():
                response = session.get(
                    _build_endpoint(self.settings.base_url),
                    params=params,
                    headers=headers,
                    timeout=self.settings.timeout,
                )
                duration = self._clock() - start
                response.raise_for_status()
                payload = response.json()
        except requests.RequestException as exc:  # pragma: no cover - defensive guard
            duration = self._clock() - start
            status = "error"
            self._record_query(duration, query.term, 0, False, status)
            raise SearxServiceError(f"SearXNG request failed: {exc}") from exc
        except ValueError as exc:  # pragma: no cover - unexpected payload
            duration = self._clock() - start
            status = "error"
            self._record_query(duration, query.term, 0, False, status)
            raise SearxServiceError("SearXNG returned invalid JSON") from exc
        else:
            results = self._parse_results(payload)
            self._store_in_cache(cache_key, [result.to_dict() for result in results])
            self._record_query(duration, query.term, len(results), False, status)
            return results, False

    def _parse_results(self, payload: Mapping[str, Any]) -> list[SearxResult]:
        raw_results = payload.get("results", []) if isinstance(payload, Mapping) else []
        results: list[SearxResult] = []
        for item in raw_results:
            if not isinstance(item, Mapping):
                continue
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", url or "Unnamed result")).strip()
            if not url:
                continue
            results.append(
                SearxResult(
                    title=title or url,
                    url=url,
                    engine=str(item.get("engine")) if item.get("engine") else None,
                    score=_coerce_float(item.get("score")),
                    snippet=str(item.get("content")) if item.get("content") else None,
                )
            )
        return results

    def _store_in_cache(self, cache_key: str, payload: list[dict[str, Any]]) -> None:
        if self.settings.cache_ttl_seconds <= 0:
            return
        try:
            path = self.cache_root / f"{cache_key}.json"
            envelope = {
                "timestamp": time.time(),
                "results": payload,
            }
            path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        except Exception:  # pragma: no cover - best effort persistence
            LOGGER.debug("Failed to write SearX cache entry", exc_info=True)

    def _load_from_cache(self, cache_key: str) -> list[dict[str, Any]] | None:
        if self.settings.cache_ttl_seconds <= 0:
            return None
        path = self.cache_root / f"{cache_key}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - corrupted cache
            LOGGER.warning("Invalid SearX cache payload at %s", path)
            return None
        timestamp = payload.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            return None
        age = time.time() - float(timestamp)
        if age > self.settings.cache_ttl_seconds:
            return None
        results = payload.get("results", [])
        if not isinstance(results, list):
            return None
        return [item for item in results if isinstance(item, Mapping)]

    def _respect_rate_limit(self) -> None:
        min_interval = max(0.0, self.settings.min_interval_seconds)
        if min_interval <= 0 and not self.settings.burst:
            self._last_request = self._clock()
            return
        now = self._clock()
        if self.settings.burst is not None:
            if self._burst_tokens is None:
                self._burst_tokens = self.settings.burst
            if self._last_request is None:
                self._last_request = now
            else:
                elapsed = now - self._last_request
                if elapsed >= min_interval:
                    self._burst_tokens = self.settings.burst
            if self._burst_tokens and self._burst_tokens > 0:
                self._burst_tokens -= 1
                self._last_request = self._clock()
                return
        if self._last_request is not None:
            elapsed = now - self._last_request
            if elapsed < min_interval:
                self._sleep(min_interval - elapsed)
        self._last_request = self._clock()

    def _get_session(self) -> requests.Session:
        if self._session is None:
            self._session = self._session_factory()
        return self._session

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.user_agent:
            headers["User-Agent"] = self.settings.user_agent
        if self.settings.api_key:
            header_name = self.settings.api_key_header or "Authorization"
            token = self.settings.api_key
            if self.settings.api_key_prefix:
                token = f"{self.settings.api_key_prefix} {token}"
            headers[header_name] = token
        return headers

    def _record_query(
        self,
        seconds: float,
        query: str,
        result_count: int,
        cached: bool,
        status: str,
    ) -> None:
        if not self._metrics or not self.settings.metrics_enabled:
            return
        self._metrics.record_research_query(
            seconds,
            query=query,
            result_count=result_count,
            cached=cached,
            status=status,
        )

    def _record_cache_hit(self, query: str) -> None:
        if not self._metrics or not self.settings.metrics_enabled:
            return
        self._metrics.record_research_cache_hit(query)

    def _record_cache_miss(self, query: str) -> None:
        if not self._metrics or not self.settings.metrics_enabled:
            return
        self._metrics.record_research_cache_miss(query)

    @staticmethod
    def _to_result(payload: Mapping[str, Any]) -> SearxResult:
        return SearxResult(
            title=str(payload.get("title") or payload.get("url") or ""),
            url=str(payload.get("url", "")),
            engine=str(payload.get("engine")) if payload.get("engine") else None,
            score=_coerce_float(payload.get("score")),
            snippet=str(payload.get("snippet")) if payload.get("snippet") else None,
        )


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _split_tokens(value: str) -> tuple[str, ...]:
    tokens = [token.strip() for token in value.split(",")]
    return tuple(token for token in tokens if token)


def _coerce_tuple(values: Iterable[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = values.split(",")
    cleaned: list[str] = []
    for item in values:
        candidate = str(item).strip()
        if candidate and candidate not in cleaned:
            cleaned.append(candidate)
    return tuple(cleaned)


def _coerce_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return bool(lowered)


def _normalise_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    return cleaned.casefold()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return None


def _build_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    return f"{trimmed}/search"


class _null_context:
    """Fallback context manager used when tracing is disabled."""

    def __enter__(self) -> None:  # pragma: no cover - trivial
        return None

    def __exit__(self, *exc: object) -> None:  # pragma: no cover - trivial
        return None


__all__ = [
    "SearxQuery",
    "SearxResponse",
    "SearxResult",
    "SearxService",
    "SearxServiceError",
    "SearxServiceSettings",
]
