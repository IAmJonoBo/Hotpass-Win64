"""AWS helper utilities for Hotpass."""

from .endpoints import resolve_localstack_endpoint, resolve_s3_endpoint

__all__ = ["resolve_localstack_endpoint", "resolve_s3_endpoint"]
