from __future__ import annotations

from pathlib import Path

import pytest
import requests

from hotpass.research.searx import (
    SearxQuery,
    SearxService,
    SearxServiceError,
    SearxServiceSettings,
)


class _StubResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.status_code = 200
        self.content = b"payload"
        self.url = "https://search.test"

    def raise_for_status(self) -> None:  # pragma: no cover - behaviour exercised implicitly
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _StubSession:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def get(
        self, url: str, params: dict[str, object], headers: dict[str, str], timeout: float
    ) -> _StubResponse:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return _StubResponse(self.payload)


class _ErrorSession:
    def get(self, *args, **kwargs):  # noqa: ANN201 - match requests.Session signature
        raise requests.RequestException("boom")


def test_searx_service_caches_results(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    payload = {
        "results": [
            {"title": "Example", "url": "https://example.test", "engine": "google"},
            {"title": "Duplicate", "url": "https://example.test/", "engine": "bing"},
        ]
    }
    session = _StubSession(payload)
    settings = SearxServiceSettings(
        enabled=True,
        cache_ttl_seconds=300.0,
        deduplicate=True,
        max_results=10,
    )
    service = SearxService(
        settings,
        cache_root=cache_root,
        session_factory=lambda: session,
    )

    queries = [SearxQuery(term="Example Org")]
    first = service.search(queries)
    assert len(first.results) == 1
    assert first.results[0].url == "https://example.test"
    assert session.calls, "HTTP call should occur on first invocation"

    second = service.search(queries)
    assert second.from_cache is True
    assert len(session.calls) == 1, "Cached calls should avoid HTTP requests"


def test_searx_service_raises_on_error(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()

    settings = SearxServiceSettings(enabled=True)
    service = SearxService(
        settings,
        cache_root=cache_root,
        session_factory=lambda: _ErrorSession(),
    )

    with pytest.raises(SearxServiceError):
        service.search([SearxQuery(term="test")])
