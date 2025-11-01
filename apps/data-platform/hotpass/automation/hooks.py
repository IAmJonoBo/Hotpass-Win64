"""Automation hooks for delivering pipeline outputs to external systems."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd

from hotpass.automation.http import (
    AutomationHTTPCircuitOpenError,
    AutomationHTTPClient,
    AutomationHTTPError,
    DeadLetterQueue,
    DeliveryAttempt,
    DeliveryReport,
)
from hotpass.telemetry.metrics import PipelineMetrics

try:  # pragma: no cover - optional dependency during CLI only usage
    from hotpass.observability import get_pipeline_metrics as _get_metrics

    get_pipeline_metrics: Callable[[], PipelineMetrics] | None = _get_metrics
except Exception:  # pragma: no cover - fallback in minimal environments
    get_pipeline_metrics = None


def _ensure_metrics(metrics: PipelineMetrics | None) -> PipelineMetrics | None:
    if metrics is not None:
        return metrics
    if get_pipeline_metrics is None:  # pragma: no cover - defensive fallback
        return None
    try:
        return get_pipeline_metrics()
    except Exception:  # pragma: no cover - registry misconfiguration
        return None


def dispatch_webhooks(
    digest: pd.DataFrame,
    *,
    webhooks: Sequence[str],
    daily_list: pd.DataFrame | None = None,
    logger: Any | None = None,
    http_client: AutomationHTTPClient | None = None,
    metrics: PipelineMetrics | None = None,
    dead_letter: DeadLetterQueue | None = None,
) -> DeliveryReport:
    """Send intent digest payloads to configured webhook endpoints."""

    report = DeliveryReport()
    if not webhooks:
        return report

    intent_records = digest.to_dict(orient="records") if not digest.empty else []
    if not intent_records and daily_list is None:
        return report

    payload: dict[str, Any] = {"intent_digest": intent_records}
    if daily_list is not None:
        payload["daily_list"] = daily_list.to_dict(orient="records")

    client = http_client or AutomationHTTPClient()
    telemetry = _ensure_metrics(metrics)

    for url in webhooks:
        try:
            result = client.post_json(url, payload=payload)
        except AutomationHTTPCircuitOpenError as exc:
            attempt = DeliveryAttempt(
                target="webhook",
                endpoint=url,
                status="circuit_open",
                attempts=0,
                error=str(exc),
            )
            if logger is not None:
                logger.log_error(f"Webhook delivery skipped for {url}: circuit open")
            if telemetry is not None:
                telemetry.record_automation_delivery(
                    target="webhook",
                    status="circuit_open",
                    endpoint=url,
                    attempts=0,
                    latency=None,
                    idempotency="absent",
                )
        except AutomationHTTPError as exc:
            attempt = DeliveryAttempt(
                target="webhook",
                endpoint=url,
                status="failed",
                attempts=exc.attempts,
                status_code=exc.status_code,
                elapsed=exc.elapsed,
                idempotency_key=exc.idempotency_key,
                error=str(exc),
            )
            if logger is not None:
                logger.log_error(f"Webhook delivery failed for {url}: {exc}")
                logger.log_event(
                    "automation.webhook.failure",
                    attempt.as_dict(),
                )
            if telemetry is not None:
                telemetry.record_automation_delivery(
                    target="webhook",
                    status="failed",
                    endpoint=url,
                    attempts=exc.attempts,
                    latency=exc.elapsed,
                    idempotency="present" if exc.idempotency_key else "absent",
                )
            if dead_letter is not None:
                dead_letter.record(
                    target="webhook",
                    endpoint=url,
                    payload=payload,
                    error=str(exc),
                    idempotency_key=exc.idempotency_key,
                )
        else:
            attempt = DeliveryAttempt(
                target="webhook",
                endpoint=url,
                status="delivered",
                attempts=result.attempts,
                status_code=result.status_code,
                elapsed=result.elapsed,
                idempotency_key=result.idempotency_key,
            )
            if logger is not None:
                logger.log_event(
                    "automation.webhook.delivered",
                    attempt.as_dict(),
                )
            if telemetry is not None:
                telemetry.record_automation_delivery(
                    target="webhook",
                    status="delivered",
                    endpoint=url,
                    attempts=result.attempts,
                    latency=result.elapsed,
                    idempotency="present",
                )

        report.add(attempt)

    return report


def push_crm_updates(
    daily_list: pd.DataFrame,
    endpoint: str,
    *,
    token: str | None = None,
    logger: Any | None = None,
    http_client: AutomationHTTPClient | None = None,
    metrics: PipelineMetrics | None = None,
    dead_letter: DeadLetterQueue | None = None,
) -> DeliveryReport:
    """Send the daily prospect list to a CRM endpoint."""

    report = DeliveryReport()
    if daily_list.empty:
        return report

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {"prospects": daily_list.to_dict(orient="records")}
    client = http_client or AutomationHTTPClient()
    telemetry = _ensure_metrics(metrics)

    try:
        result = client.post_json(endpoint, payload=payload, headers=headers)
    except AutomationHTTPCircuitOpenError as exc:
        attempt = DeliveryAttempt(
            target="crm",
            endpoint=endpoint,
            status="circuit_open",
            attempts=0,
            error=str(exc),
        )
        if logger is not None:
            logger.log_error(f"CRM update skipped for {endpoint}: circuit open")
        if telemetry is not None:
            telemetry.record_automation_delivery(
                target="crm",
                status="circuit_open",
                endpoint=endpoint,
                attempts=0,
                latency=None,
                idempotency="absent",
            )
    except AutomationHTTPError as exc:
        attempt = DeliveryAttempt(
            target="crm",
            endpoint=endpoint,
            status="failed",
            attempts=exc.attempts,
            status_code=exc.status_code,
            elapsed=exc.elapsed,
            idempotency_key=exc.idempotency_key,
            error=str(exc),
        )
        if logger is not None:
            logger.log_error(f"CRM update failed for {endpoint}: {exc}")
            logger.log_event("automation.crm.failure", attempt.as_dict())
        if telemetry is not None:
            telemetry.record_automation_delivery(
                target="crm",
                status="failed",
                endpoint=endpoint,
                attempts=exc.attempts,
                latency=exc.elapsed,
                idempotency="present" if exc.idempotency_key else "absent",
            )
        if dead_letter is not None:
            dead_letter.record(
                target="crm",
                endpoint=endpoint,
                payload=payload,
                error=str(exc),
                idempotency_key=exc.idempotency_key,
            )
    else:
        attempt = DeliveryAttempt(
            target="crm",
            endpoint=endpoint,
            status="delivered",
            attempts=result.attempts,
            status_code=result.status_code,
            elapsed=result.elapsed,
            idempotency_key=result.idempotency_key,
        )
        if logger is not None:
            logger.log_event("automation.crm.delivered", attempt.as_dict())
        if telemetry is not None:
            telemetry.record_automation_delivery(
                target="crm",
                status="delivered",
                endpoint=endpoint,
                attempts=result.attempts,
                latency=result.elapsed,
                idempotency="present",
            )

    report.add(attempt)
    return report


__all__ = ["dispatch_webhooks", "push_crm_updates"]
