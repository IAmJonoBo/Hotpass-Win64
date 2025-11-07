from __future__ import annotations

from typing import Callable

from hotpass.aws import resolve_localstack_endpoint, resolve_s3_endpoint


def _with_env(monkeypatch, mapping: dict[str, str | None], func: Callable[[], None]) -> None:
    for key, value in mapping.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    func()


def test_resolve_s3_endpoint_prefers_hotpass_env(monkeypatch):
    def assertion() -> None:
        assert resolve_s3_endpoint() == "http://minio:9000"

    _with_env(monkeypatch, {"HOTPASS_S3_ENDPOINT": "http://minio:9000/", "S3_ENDPOINT_URL": "http://ignored"}, assertion)


def test_resolve_s3_endpoint_falls_back(monkeypatch):
    def assertion() -> None:
        assert resolve_s3_endpoint() is None

    _with_env(monkeypatch, {"HOTPASS_S3_ENDPOINT": None, "S3_ENDPOINT_URL": None}, assertion)


def test_resolve_localstack_endpoint_honours_multiple_aliases(monkeypatch):
    def assertion() -> None:
        assert resolve_localstack_endpoint() == "http://localhost:4566"

    _with_env(
        monkeypatch,
        {
            "HOTPASS_LOCALSTACK_ENDPOINT": None,
            "LOCALSTACK_ENDPOINT": "http://localhost:4566/",
            "AWS_ENDPOINT_URL": "http://should-not-be-used",
        },
        assertion,
    )


def test_resolve_localstack_endpoint_uses_default(monkeypatch):
    def assertion() -> None:
        assert resolve_localstack_endpoint(default="http://fallback") == "http://fallback"

    _with_env(
        monkeypatch,
        {
            "HOTPASS_LOCALSTACK_ENDPOINT": None,
            "LOCALSTACK_ENDPOINT": None,
            "AWS_ENDPOINT_URL": None,
        },
        assertion,
    )
