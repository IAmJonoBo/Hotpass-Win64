"""Automation helpers for delivering pipeline outputs."""

from .hooks import dispatch_webhooks, push_crm_updates
from .http import (
    AutomationCircuitBreakerPolicy,
    AutomationHTTPCircuitOpenError,
    AutomationHTTPClient,
    AutomationHTTPConfig,
    AutomationHTTPError,
    AutomationHTTPResponseError,
    AutomationHTTPTransportError,
    AutomationRetryPolicy,
    DeadLetterQueue,
    DeliveryAttempt,
    DeliveryReport,
    HTTPResult,
)

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
    "dispatch_webhooks",
    "push_crm_updates",
]
