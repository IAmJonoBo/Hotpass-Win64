"""Reusable HTTP client for automation deliveries with resilience controls."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

DEFAULT_RETRY_STATUSES: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)


@dataclass(slots=True, frozen=True)
class AutomationRetryPolicy:
    """Retry controls for automation deliveries."""

    attempts: int = 3
    backoff_factor: float = 0.5
    backoff_max: float = 30.0
    status_forcelist: tuple[int, ...] = DEFAULT_RETRY_STATUSES

    def __post_init__(self) -> None:  # pragma: no cover - validation branch
        if self.attempts < 1:
            msg = "attempts must be at least 1"
            raise ValueError(msg)
        if self.backoff_factor < 0:
            msg = "backoff_factor must be non-negative"
            raise ValueError(msg)
        if self.backoff_max < 0:
            msg = "backoff_max must be non-negative"
            raise ValueError(msg)


@dataclass(slots=True, frozen=True)
class AutomationCircuitBreakerPolicy:
    """Circuit breaking settings to avoid hammering unstable endpoints."""

    failure_threshold: int = 5
    recovery_time: float = 60.0

    def __post_init__(self) -> None:  # pragma: no cover - validation branch
        if self.failure_threshold < 1:
            msg = "failure_threshold must be at least 1"
            raise ValueError(msg)
        if self.recovery_time < 0:
            msg = "recovery_time must be non-negative"
            raise ValueError(msg)


@dataclass(slots=True, frozen=True)
class AutomationHTTPConfig:
    """Concrete settings applied by :class:`AutomationHTTPClient`."""

    timeout: float = 10.0
    retry: AutomationRetryPolicy = field(default_factory=AutomationRetryPolicy)
    circuit_breaker: AutomationCircuitBreakerPolicy = field(
        default_factory=AutomationCircuitBreakerPolicy
    )
    idempotency_header: str = "Idempotency-Key"
    dead_letter_path: Path | None = None
    dead_letter_enabled: bool = False

    def is_dead_letter_enabled(self) -> bool:
        return self.dead_letter_enabled and self.dead_letter_path is not None


@dataclass(slots=True)
class HTTPResult:
    """Metadata returned for a successful automation delivery."""

    url: str
    status_code: int
    headers: dict[str, str]
    elapsed: float
    attempts: int
    idempotency_key: str


@dataclass(slots=True)
class DeliveryAttempt:
    """Captured summary of an automation delivery attempt."""

    target: str
    endpoint: str
    status: str
    attempts: int
    status_code: int | None = None
    elapsed: float | None = None
    idempotency_key: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "target": self.target,
            "endpoint": self.endpoint,
            "status": self.status,
            "attempts": self.attempts,
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.elapsed is not None:
            payload["elapsed"] = self.elapsed
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(slots=True)
class DeliveryReport:
    """Aggregate report across automation delivery attempts."""

    attempts: list[DeliveryAttempt] = field(default_factory=list)

    def add(self, attempt: DeliveryAttempt) -> None:
        self.attempts.append(attempt)

    def successes(self) -> list[DeliveryAttempt]:
        return [attempt for attempt in self.attempts if attempt.status == "delivered"]

    def failures(self) -> list[DeliveryAttempt]:
        return [attempt for attempt in self.attempts if attempt.status != "delivered"]

    def as_dict(self) -> dict[str, Any]:
        return {"attempts": [attempt.as_dict() for attempt in self.attempts]}


class AutomationHTTPError(RuntimeError):
    """Base error type for automation delivery failures."""

    def __init__(
        self,
        message: str,
        *,
        url: str,
        status_code: int | None = None,
        attempts: int = 0,
        idempotency_key: str | None = None,
        elapsed: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.attempts = attempts
        self.idempotency_key = idempotency_key
        self.elapsed = elapsed
        if cause is not None:
            self.__cause__ = cause


class AutomationHTTPResponseError(AutomationHTTPError):
    """Raised when the upstream endpoint returns an error status code."""


class AutomationHTTPTransportError(AutomationHTTPError):
    """Raised when the request cannot reach the upstream endpoint."""


class AutomationHTTPCircuitOpenError(AutomationHTTPError):
    """Raised when the circuit breaker short-circuits delivery attempts."""

    def __init__(self, message: str, *, url: str, retry_after: float | None) -> None:
        super().__init__(message, url=url, attempts=0)
        self.retry_after = retry_after


class AutomationHTTPClient:
    """HTTP client with retry, backoff, and circuit breaking controls."""

    def __init__(
        self,
        config: AutomationHTTPConfig | None = None,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        idempotency_key_factory: Callable[[], str] | None = None,
    ) -> None:
        self._config = config or AutomationHTTPConfig()
        self._session = session or requests.Session()
        self._sleep = sleep
        self._monotonic = monotonic
        self._idempotency_key_factory = idempotency_key_factory or (lambda: uuid.uuid4().hex)

        self._consecutive_failures = 0
        self._circuit_open_until: float | None = None

    @property
    def config(self) -> AutomationHTTPConfig:
        return self._config

    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HTTPResult:
        if self._is_circuit_open():
            retry_after = None
            if self._circuit_open_until is not None:
                retry_after = max(self._circuit_open_until - self._monotonic(), 0.0)
            raise AutomationHTTPCircuitOpenError(
                "circuit breaker open for automation delivery",
                url=url,
                retry_after=retry_after,
            )

        attempt_headers: MutableMapping[str, str] = {"Content-Type": "application/json"}
        if headers:
            attempt_headers.update(dict(headers))

        idempotency_key = attempt_headers.setdefault(
            self._config.idempotency_header, self._idempotency_key_factory()
        )

        attempts = 0
        start = self._monotonic()
        last_error: AutomationHTTPError | None = None

        for attempt in range(1, self._config.retry.attempts + 1):
            attempts = attempt
            try:
                response = self._session.request(
                    "POST",
                    url,
                    json=payload,
                    headers=dict(attempt_headers),
                    timeout=timeout or self._config.timeout,
                )
            except requests.RequestException as exc:
                last_error = AutomationHTTPTransportError(
                    str(exc),
                    url=url,
                    attempts=attempt,
                    idempotency_key=idempotency_key,
                    cause=exc,
                )
                if not self._should_retry_exception(attempt):
                    break
            else:
                if response.status_code >= 400:
                    error = AutomationHTTPResponseError(
                        f"HTTP {response.status_code}",
                        url=url,
                        status_code=response.status_code,
                        attempts=attempt,
                        idempotency_key=idempotency_key,
                    )
                    if (
                        response.status_code in self._config.retry.status_forcelist
                        and self._should_retry_status(attempt)
                    ):
                        last_error = error
                    else:
                        self._record_failure()
                        raise error
                else:
                    elapsed = self._monotonic() - start
                    self._reset_circuit()
                    return HTTPResult(
                        url=url,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        elapsed=elapsed,
                        attempts=attempt,
                        idempotency_key=idempotency_key,
                    )

            backoff = self._backoff_for_attempt(attempt)
            if backoff > 0:
                self._sleep(backoff)

        self._record_failure()
        if last_error is not None:
            raise last_error
        raise AutomationHTTPError(
            "automation request failed without response",
            url=url,
            attempts=attempts,
            idempotency_key=idempotency_key,
        )

    def _backoff_for_attempt(self, attempt: int) -> float:
        factor = self._config.retry.backoff_factor
        if factor <= 0:
            return 0.0
        backoff = factor * (2 ** (attempt - 1))
        return float(min(backoff, self._config.retry.backoff_max))

    def _should_retry_exception(self, attempt: int) -> bool:
        return attempt < self._config.retry.attempts

    def _should_retry_status(self, attempt: int) -> bool:
        return attempt < self._config.retry.attempts

    def _is_circuit_open(self) -> bool:
        if self._circuit_open_until is None:
            return False
        if self._monotonic() >= self._circuit_open_until:
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return False
        return True

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._config.circuit_breaker.failure_threshold:
            self._circuit_open_until = (
                self._monotonic() + self._config.circuit_breaker.recovery_time
            )

    def _reset_circuit(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = None


@dataclass(slots=True)
class DeadLetterQueue:
    """Persist failed automation payloads for later replay."""

    path: Path

    def record(
        self,
        *,
        target: str,
        endpoint: str,
        payload: Mapping[str, Any],
        error: str,
        idempotency_key: str | None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "target": target,
            "endpoint": endpoint,
            "error": error,
            "idempotency_key": idempotency_key,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, default=_json_default))
            handle.write("\n")


def _json_default(value: Any) -> Any:  # pragma: no cover - defensive helper
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serialisable")


__all__ = [
    "AutomationCircuitBreakerPolicy",
    "AutomationHTTPClient",
    "AutomationHTTPConfig",
    "AutomationHTTPError",
    "AutomationHTTPResponseError",
    "AutomationHTTPTransportError",
    "AutomationHTTPCircuitOpenError",
    "AutomationRetryPolicy",
    "DeadLetterQueue",
    "DeliveryAttempt",
    "DeliveryReport",
    "HTTPResult",
]
