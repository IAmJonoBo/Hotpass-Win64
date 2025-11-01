"""Tests for Vault-backed secret integration helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import pytest

from tests.helpers.fixtures import fixture

pytest.importorskip("frictionless")

from hotpass import secrets  # noqa: E402
from hotpass.secrets import VaultResponse


@dataclass
class StubResponse(VaultResponse):
    """Simple response container mimicking requests.Response."""

    payload: dict[str, Any]
    status_code: int = 200

    def json(self) -> dict[str, Any]:
        return self.payload

    @property
    def text(self) -> str:
        return json.dumps(self.payload)

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise RuntimeError(self.text)


class StubSession:
    """Deterministic HTTP session stub for Vault API interactions."""

    def __init__(self, responses: dict[tuple[str, str], StubResponse]):
        self._responses = responses
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> StubResponse:
        key = (method.upper(), url)
        self.requests.append((method.upper(), url, kwargs))
        if key not in self._responses:
            raise AssertionError(f"Unexpected request: {method} {url}")
        return self._responses[key]

    def get(self, url: str, **kwargs: Any) -> StubResponse:  # pragma: no cover - passthrough
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> StubResponse:  # pragma: no cover - passthrough
        return self.request("POST", url, **kwargs)


@fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Vault-related environment variables are cleared between tests."""

    for key in list(os.environ):
        if key.startswith("HOTPASS_VAULT") or key.startswith("PREFECT_API"):
            monkeypatch.delenv(key, raising=False)


def test_vault_manager_reads_secret_with_env_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Providing a static token should authenticate requests without extra calls."""

    monkeypatch.setenv("HOTPASS_VAULT_ADDR", "https://vault.example.com")
    monkeypatch.setenv("HOTPASS_VAULT_TOKEN", "s3cr3t-token")

    session = StubSession(
        {
            (
                "GET",
                "https://vault.example.com/v1/kv/data/hotpass/pipeline",
            ): StubResponse({"data": {"data": {"api_key": "abc"}}}),
        }
    )

    manager = secrets.VaultSecretManager.from_env(session=session)
    assert manager is not None

    payload = manager.read_kv_secret("hotpass/pipeline")
    assert payload["api_key"] == "abc"

    method, url, kwargs = session.requests[0]
    assert method == "GET"
    assert url.endswith("/kv/data/hotpass/pipeline")
    assert kwargs["headers"]["X-Vault-Token"] == "s3cr3t-token"


def test_vault_manager_oidc_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vault manager should exchange a GitHub OIDC token when configured."""

    monkeypatch.setenv("HOTPASS_VAULT_ADDR", "https://vault.example.com")
    monkeypatch.setenv("HOTPASS_VAULT_ROLE", "hotpass-ci")
    monkeypatch.setenv("HOTPASS_VAULT_AUTH_MOUNT", "github")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://oidc.example.com?id=stub")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "oidc-request-token")

    session = StubSession(
        {
            (
                "GET",
                "https://oidc.example.com?id=stub&audience=hotpass",
            ): StubResponse({"value": "jwt-token"}),
            (
                "POST",
                "https://vault.example.com/v1/auth/github/login",
            ): StubResponse({"auth": {"client_token": "vault-oidc-token"}}),
            (
                "GET",
                "https://vault.example.com/v1/kv/data/hotpass/prefect",
            ): StubResponse(
                {
                    "data": {
                        "data": {
                            # Fixture uses placeholder secret; allowlist for scanners.
                            "prefect_api_key": "vault-key",  # pragma: allowlist secret
                        }
                    }
                }
            ),
        }
    )

    manager = secrets.VaultSecretManager.from_env(session=session)
    assert manager is not None

    payload = manager.read_kv_secret("hotpass/prefect")
    # Fixture uses placeholder secret; allowlist for scanners.
    assert payload["prefect_api_key"] == "vault-key"  # pragma: allowlist secret

    # Ensure login payload used OIDC JWT
    _, _, login_kwargs = session.requests[1]
    assert login_kwargs["json"]["jwt"] == "jwt-token"
    assert login_kwargs["json"]["role"] == "hotpass-ci"


def test_load_prefect_environment_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Helper should expose Prefect secrets in the environment."""

    monkeypatch.setenv("HOTPASS_VAULT_ADDR", "https://vault.example.com")
    monkeypatch.setenv("HOTPASS_VAULT_TOKEN", "token")
    monkeypatch.setenv("HOTPASS_VAULT_PREFECT_PATH", "hotpass/prefect")

    session = StubSession(
        {
            (
                "GET",
                "https://vault.example.com/v1/kv/data/hotpass/prefect",
            ): StubResponse(
                {
                    "data": {
                        "data": {
                            # Fixture uses placeholder secret; allowlist for scanners.
                            "prefect_api_key": "vault-key",  # pragma: allowlist secret
                            "prefect_api_url": "https://prefect.example/api",
                        }
                    }
                }
            ),
        }
    )

    secrets.load_prefect_environment_secrets(session=session)

    # Fixture uses placeholder secret; allowlist for scanners.
    assert os.environ["PREFECT_API_KEY"] == "vault-key"  # pragma: allowlist secret
    assert os.environ["PREFECT_API_URL"] == "https://prefect.example/api"
