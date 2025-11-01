"""Shared primitives for registry enrichment adapters."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Any, cast

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency guard
    requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class RegistryError(RuntimeError):
    """Base error for registry adapters."""


class RegistryConfigurationError(RegistryError):
    """Raised when required configuration is missing."""


class RegistryTransportError(RegistryError):
    """Raised when an HTTP transport error occurs."""


class RegistryRateLimitError(RegistryError):
    """Raised when a request would violate the configured rate limit."""


def _iso_datetime() -> str:
    """Return a timezone-aware ISO 8601 timestamp."""

    return datetime.now(UTC).isoformat()


def normalise_date(value: Any) -> str | None:
    """Attempt to coerce assorted date strings into ISO format."""

    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    # Accept already formatted ISO strings.
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    else:
        return parsed.date().isoformat()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text or None


def normalise_address(
    payload: Mapping[str, Any] | None, *, kind: str | None = None
) -> dict[str, Any] | None:
    """Normalise address payloads into a consistent schema."""

    if not isinstance(payload, Mapping):
        return None
    return {
        "type": kind or clean_text(payload.get("type") or payload.get("address_type")),
        "line1": clean_text(payload.get("line1") or payload.get("address_line1")),
        "line2": clean_text(payload.get("line2") or payload.get("address_line2")),
        "city": clean_text(payload.get("city") or payload.get("town")),
        "province": clean_text(payload.get("province") or payload.get("state")),
        "postal_code": clean_text(payload.get("postal_code") or payload.get("postalCode")),
        "country": clean_text(payload.get("country")),
    }


def normalise_officer(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Normalise officer/director payloads."""

    if not isinstance(payload, Mapping):
        return None
    name = clean_text(
        payload.get("full_name") or payload.get("name") or payload.get("display_name")
    )
    if not name:
        return None
    return {
        "name": name,
        "role": clean_text(payload.get("role") or payload.get("position")),
        "appointment_date": normalise_date(
            payload.get("appointment_date") or payload.get("appointed")
        ),
        "resignation_date": normalise_date(
            payload.get("resignation_date") or payload.get("resigned")
        ),
    }


def clean_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


class RateLimiter:
    """Simple monotonic-based rate limiter.

    The limiter raises :class:`RegistryRateLimitError` if a call occurs before the
    configured interval has elapsed. This avoids blocking pipeline execution while
    still protecting upstream APIs.
    """

    def __init__(self, min_interval: float | int | None = None) -> None:
        interval = float(min_interval or 0.0)
        self.min_interval = max(interval, 0.0)
        if self.min_interval <= 0:
            logger.warning(
                "RateLimiter initialized with min_interval=%r; rate limiting is disabled.",
                min_interval,
            )
        self._lock = Lock()
        self._next_available: float = 0.0

    def check(self) -> None:
        if self.min_interval <= 0:
            return
        now = monotonic()
        with self._lock:
            if now < self._next_available:
                remaining = self._next_available - now
                raise RegistryRateLimitError(
                    f"Rate limit active for another {remaining:.2f} seconds"
                )
            self._next_available = now + self.min_interval


@dataclass(slots=True)
class RegistryResponse:
    """Container for normalised registry lookup results."""

    registry: str
    organization: str
    success: bool
    status_code: int | None
    payload: dict[str, Any] | None
    errors: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.meta.setdefault("looked_up_at", _iso_datetime())

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry": self.registry,
            "organization": self.organization,
            "success": self.success,
            "status_code": self.status_code,
            "payload": self.payload,
            "errors": self.errors,
            "raw": self.raw,
            "meta": self.meta,
        }


class BaseRegistryAdapter(ABC):
    """Abstract base class for registry lookups."""

    registry: str
    default_base_url: str | None = None
    default_timeout: float = 10.0
    default_headers: MutableMapping[str, str]

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_header: str | None = None,
        throttle_seconds: float | int | None = None,
        timeout: float | int | None = None,
        session: requests.Session | None = None,
        headers: Mapping[str, str] | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> None:
        if requests is None:  # pragma: no cover - guarded by optional dependency
            raise RegistryConfigurationError(
                "The 'requests' library is required for registry lookups"
            )
        self.base_url = (base_url or self.default_base_url or "").strip()
        if not self.base_url:
            raise RegistryConfigurationError(f"{self.registry} adapter requires a base_url")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.timeout = float(timeout or self.default_timeout)
        self.session = session or requests.Session()
        self._rate_limiter = RateLimiter(throttle_seconds)
        self.default_headers = {**(headers or {})}
        self.extra_params = dict(extra_params or {})
        if self.api_key:
            if self.api_key_header:
                self.default_headers.setdefault(self.api_key_header, self.api_key)
            else:
                self.default_headers.setdefault("Authorization", f"Bearer {self.api_key}")

    @property
    def throttle_seconds(self) -> float:
        return self._rate_limiter.min_interval

    def _apply_rate_limit(self) -> None:
        self._rate_limiter.check()

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> requests.Response:
        self._apply_rate_limit()
        merged_headers: dict[str, str] = {**self.default_headers}
        if headers:
            merged_headers.update({k: v for k, v in headers.items() if v is not None})
        try:
            response = self.session.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RegistryTransportError(str(exc)) from exc
        return response

    def _base_meta(self) -> dict[str, Any]:
        return {
            "registry": self.registry,
            "endpoint": self.base_url,
            "throttle_seconds": self.throttle_seconds,
        }

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], response.json())
        except ValueError as exc:
            raise RegistryTransportError("Registry response was not valid JSON") from exc

    @abstractmethod
    def lookup(self, organization: str) -> RegistryResponse:
        """Lookup registry data for the supplied organisation."""
        raise NotImplementedError


__all__ = [
    "BaseRegistryAdapter",
    "clean_text",
    "RegistryConfigurationError",
    "RegistryError",
    "RegistryRateLimitError",
    "RegistryResponse",
    "RegistryTransportError",
    "normalise_address",
    "normalise_date",
    "normalise_officer",
]
