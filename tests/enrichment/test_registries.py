from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import requests
from hotpass.enrichment import CacheManager, RegistryLookupError, enrich_from_registry
from requests import Response
from requests.structures import CaseInsensitiveDict

from tests.helpers.assertions import expect

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "enrichment"


class DummySession:
    """Minimal requests-compatible session for fixture responses."""

    def __init__(
        self,
        responses: dict[tuple[str, tuple[tuple[str, str], ...] | None], dict[str, Any]],
        error: Exception | None = None,
    ) -> None:
        self._responses = responses
        self._error = error
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, Any] | None = None,
        timeout: float | tuple[float | None, float | None] | None = None,
        **_: Any,
    ) -> Response:
        if self._error is not None:
            raise self._error
        key = (url, tuple(sorted((params or {}).items())) if params else None)
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        try:
            payload = self._responses[key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AssertionError(f"Unexpected request: {key}") from exc
        response = Response()
        response.status_code = payload["status"]
        # Direct assignment to _content is necessary here to mock the response body for tests.
        response._content = json.dumps(payload["body"]).encode("utf-8")
        response.headers = CaseInsensitiveDict({"Content-Type": "application/json"})
        response.url = url
        return response


def _load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURE_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


def test_cipc_lookup_success(tmp_path: Path) -> None:
    payload = _load_fixture("cipc_company.json")
    base_url = "https://cipc.example/api"
    dummy_session = DummySession(
        {(base_url, (("search", "Aero Tech"),)): {"status": 200, "body": payload}}
    )
    session = cast(requests.Session, dummy_session)
    cache = CacheManager(db_path=str(tmp_path / "cache.db"), ttl_hours=1)

    result = enrich_from_registry(
        "Aero Tech",
        registry_type="cipc",
        cache=cache,
        session=session,
        config={"base_url": base_url},
    )

    expect(result["success"] is True, "Lookup should succeed")
    expect(result["status_code"] == 200, "Status code should reflect success")
    expect(
        result["payload"]["registered_name"] == "Aero Tech (Pty) Ltd",
        "Registered name mismatch",
    )
    expect(len(result["payload"]["addresses"]) == 2, "Two addresses expected")
    expect(result["payload"]["officers"][0]["name"] == "Jane Doe", "Officer name mismatch")


def test_cipc_not_found_returns_structured_error(tmp_path: Path) -> None:
    base_url = "https://cipc.example/api"
    dummy_session = DummySession(
        {
            (base_url, (("search", "Unknown"),)): {
                "status": 404,
                "body": {"message": "No match"},
            }
        }
    )
    session = cast(requests.Session, dummy_session)
    cache = CacheManager(db_path=str(tmp_path / "cache.db"), ttl_hours=1)

    result = enrich_from_registry(
        "Unknown",
        registry_type="cipc",
        cache=cache,
        session=session,
        config={"base_url": base_url},
    )

    expect(result["success"] is False, "Lookup should fail for missing id")
    expect(result["status_code"] == 404, "Status code should indicate missing record")
    expect(result["errors"][0]["code"] == "not_found", "Error code mismatch")


def test_sacaa_lookup_success(tmp_path: Path) -> None:
    payload = _load_fixture("sacaa_operator.json")
    base_url = "https://sacaa.example/operators"
    dummy_session = DummySession(
        {(base_url, (("query", "Sky Charter"),)): {"status": 200, "body": payload}}
    )
    session = cast(requests.Session, dummy_session)
    cache = CacheManager(db_path=str(tmp_path / "cache.db"), ttl_hours=1)

    result = enrich_from_registry(
        "Sky Charter",
        registry_type="sacaa",
        cache=cache,
        session=session,
        config={"base_url": base_url},
    )

    expect(result["success"] is True, "Lookup should succeed")
    expect(result["payload"]["trading_name"] == "Sky Charter", "Trading name mismatch")
    expect(
        result["payload"]["contacts"]["email"] == "ops@skycharter.test",
        "Contact email mismatch",
    )
    expect(
        result["payload"]["officers"][0]["name"] == "Lerato Mokoena",
        "Officer name mismatch",
    )
    expect(result["meta"]["provider_meta"]["source"] == "SACAA API", "Meta source mismatch")


def test_enrich_from_registry_raises_on_transport_error(tmp_path: Path) -> None:
    base_url = "https://cipc.example/api"
    dummy_session = DummySession({}, error=requests.ConnectionError("boom"))
    session = cast(requests.Session, dummy_session)
    cache = CacheManager(db_path=str(tmp_path / "cache.db"), ttl_hours=1)

    with pytest.raises(RegistryLookupError):
        enrich_from_registry(
            "Failure",
            registry_type="cipc",
            cache=cache,
            session=session,
            config={"base_url": base_url},
        )


def test_enrich_from_registry_uses_cache_before_rate_limit(tmp_path: Path) -> None:
    payload = _load_fixture("cipc_company.json")
    base_url = "https://cipc.example/api"
    dummy_session = DummySession(
        {(base_url, (("search", "Aero Tech"),)): {"status": 200, "body": payload}}
    )
    session = cast(requests.Session, dummy_session)
    cache = CacheManager(db_path=str(tmp_path / "cache.db"), ttl_hours=1)

    # First call populates the cache and advances the rate limiter
    result_first = enrich_from_registry(
        "Aero Tech",
        registry_type="cipc",
        cache=cache,
        session=session,
        config={"base_url": base_url, "throttle_seconds": 10},
    )
    expect(result_first["success"] is True, "First call should succeed")

    # Second call should read from cache without invoking the session again
    result_second = enrich_from_registry(
        "Aero Tech",
        registry_type="cipc",
        cache=cache,
        session=session,
        config={"base_url": base_url, "throttle_seconds": 10},
    )

    expect(result_second == result_first, "Second call should return cached result")
    expect(len(dummy_session.calls) == 1, "Session should be called once due to caching")
