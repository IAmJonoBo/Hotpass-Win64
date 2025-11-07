"""Environment-driven helpers for AWS-compatible endpoints."""

from __future__ import annotations

import os
from typing import Final

_S3_ENV_VARS: Final[tuple[str, ...]] = (
    "HOTPASS_S3_ENDPOINT",
    "S3_ENDPOINT_URL",
)
_LOCALSTACK_ENV_VARS: Final[tuple[str, ...]] = (
    "HOTPASS_LOCALSTACK_ENDPOINT",
    "LOCALSTACK_ENDPOINT",
    "AWS_ENDPOINT_URL",
)


def _normalise(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("/"):
        cleaned = cleaned.rstrip("/")
    return cleaned or None


def resolve_s3_endpoint(default: str | None = None) -> str | None:
    """Return the preferred S3/MinIO endpoint, if configured."""

    for var in _S3_ENV_VARS:
        resolved = _normalise(os.getenv(var))
        if resolved:
            return resolved
    return default


def resolve_localstack_endpoint(default: str | None = None) -> str | None:
    """Return the preferred LocalStack endpoint for AWS SDK calls."""

    for var in _LOCALSTACK_ENV_VARS:
        resolved = _normalise(os.getenv(var))
        if resolved:
            return resolved
    return default
