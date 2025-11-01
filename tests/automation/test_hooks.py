"""Regression tests for automation delivery hooks and HTTP client behaviour."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from hotpass.automation.hooks import dispatch_webhooks, push_crm_updates
from hotpass.automation.http import (
    AutomationCircuitBreakerPolicy,
    AutomationHTTPClient,
    AutomationHTTPConfig,
    AutomationRetryPolicy,
    DeadLetterQueue,
)
from hotpass.telemetry.metrics import PipelineMetrics
from requests.auth import AuthBase
from requests.cookies import RequestsCookieJar
from requests.models import PreparedRequest
from requests.structures import CaseInsensitiveDict

AuthLike = tuple[str, str] | AuthBase | Callable[[PreparedRequest], PreparedRequest] | None
HookMap = (
    Mapping[
        str,
        Iterable[Callable[[requests.Response], Any]] | Callable[[requests.Response], Any],
    ]
    | None
)


def _make_response(status_code: int, *, headers: dict[str, str] | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = b"{}"
    response.headers = CaseInsensitiveDict(headers or {})
    response.url = "https://automation.test/endpoint"
    return response


class StubMetrics(PipelineMetrics):
    __slots__ = ("calls",)

    def __init__(self) -> None:
        # Avoid initialising the full PipelineMetrics machinery for tests.
        self.calls: list[dict[str, Any]] = []

    def record_automation_delivery(
        self,
        *,
        target: str,
        status: str,
        endpoint: str | None = None,
        attempts: int,
        latency: float | None,
        idempotency: str,
    ) -> None:
        self.calls.append(
            {
                "target": target,
                "status": status,
                "endpoint": endpoint,
                "attempts": attempts,
                "latency": latency,
                "idempotency": idempotency,
            }
        )


@dataclass(slots=True)
class StubLogger:
    events: list[tuple[str, dict[str, Any]]]
    errors: list[str]

    def __init__(self) -> None:
        self.events = []
        self.errors = []

    def log_event(self, name: str, payload: dict[str, Any]) -> None:
        self.events.append((name, payload))

    def log_error(self, message: str) -> None:
        self.errors.append(message)


class FakeSession(requests.Session):
    """Deterministic session stub to drive retry behaviour."""

    def __init__(self, responses: list[requests.Response | Exception]) -> None:
        super().__init__()
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str | bytes,
        url: str | bytes,
        params: Any = None,
        data: Any = None,
        headers: Mapping[str, str | bytes | None] | None = None,
        cookies: RequestsCookieJar | MutableMapping[str, str] | None = None,
        files: Any = None,
        auth: AuthLike = None,
        timeout: float | tuple[float | None, float | None] | None = None,
        allow_redirects: bool = True,
        proxies: MutableMapping[str, str] | None = None,
        hooks: HookMap = None,
        stream: bool | None = None,
        verify: bool | str | None = None,
        cert: str | tuple[str, str] | None = None,
        json: Any = None,
        **kwargs: Any,
    ) -> requests.Response:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "data": data,
                "headers": headers,
                "cookies": cookies,
                "files": files,
                "auth": auth,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
                "proxies": proxies,
                "hooks": hooks,
                "stream": stream,
                "verify": verify,
                "cert": cert,
                "json": json,
                **kwargs,
            }
        )
        index = len(self.calls) - 1
        outcome = self._responses[index]
        if isinstance(outcome, Exception):  # pragma: no cover - defensive for clarity
            raise outcome
        return outcome


def test_http_client_retries_and_preserves_idempotency() -> None:
    responses: list[requests.Response | Exception] = [
        requests.Timeout("first timeout"),
        _make_response(503),
        _make_response(200, headers={"X-Test": "true"}),
    ]

    session = FakeSession(responses)
    config = AutomationHTTPConfig(
        timeout=1.0,
        retry=AutomationRetryPolicy(attempts=3, backoff_factor=0, status_forcelist=(503,)),
        circuit_breaker=AutomationCircuitBreakerPolicy(failure_threshold=5, recovery_time=1.0),
    )

    client = AutomationHTTPClient(
        config,
        session=session,
        monotonic=lambda: 1.0,
        sleep=lambda _: None,
        idempotency_key_factory=lambda: "fixed-key",
    )

    result = client.post_json("https://automation.test/webhook", payload={"hello": "world"})

    assert result.status_code == 200
    assert result.attempts == 3
    assert result.idempotency_key == "fixed-key"
    assert session.calls[0]["headers"][config.idempotency_header] == "fixed-key"
    assert all(call["headers"][config.idempotency_header] == "fixed-key" for call in session.calls)


def test_dispatch_webhooks_records_metrics_and_logs_success() -> None:
    logger = StubLogger()
    metrics = StubMetrics()
    digest = pd.DataFrame([{"id": 1, "score": 0.9}])

    session = FakeSession([_make_response(200), _make_response(200)])
    client = AutomationHTTPClient(AutomationHTTPConfig(), session=session, sleep=lambda _: None)

    report = dispatch_webhooks(
        digest,
        webhooks=("https://automation.test/a", "https://automation.test/b"),
        logger=logger,
        http_client=client,
        metrics=metrics,
    )

    assert len(report.attempts) == 2
    assert {attempt.status for attempt in report.attempts} == {"delivered"}
    assert all(attempt.status_code == 200 for attempt in report.attempts)
    assert logger.events
    assert not logger.errors
    assert len(metrics.calls) == 2
    assert metrics.calls[0]["status"] == "delivered"


def test_push_crm_updates_persists_dead_letter_on_failure(tmp_path: Path) -> None:
    logger = StubLogger()
    metrics = StubMetrics()
    queue = DeadLetterQueue(tmp_path / "dead_letter.ndjson")

    failing_session = FakeSession([_make_response(503)])
    failing_client = AutomationHTTPClient(
        AutomationHTTPConfig(
            timeout=1.0,
            retry=AutomationRetryPolicy(attempts=1, backoff_factor=0.0, backoff_max=0.0),
        ),
        session=failing_session,
        sleep=lambda _: None,
    )

    daily = pd.DataFrame([{"id": 1, "score": 0.9}])

    report = push_crm_updates(
        daily,
        "https://automation.test/crm",
        logger=logger,
        http_client=failing_client,
        metrics=metrics,
        dead_letter=queue,
    )

    assert report.attempts and report.attempts[0].status == "failed"
    assert logger.errors
    assert metrics.calls and metrics.calls[0]["status"] == "failed"
    assert queue.path.exists()
    contents = queue.path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(contents[-1])
    assert record["endpoint"] == "https://automation.test/crm"
    assert record["error"] == "HTTP 503"
