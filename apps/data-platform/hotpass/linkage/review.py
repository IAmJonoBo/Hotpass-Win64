"""Connector utilities for routing uncertain linkage pairs to Label Studio."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import requests

from .config import LabelStudioConfig, LinkageThresholds

logger = logging.getLogger(__name__)


class LabelStudioConnector:
    """Minimal API client for Label Studio tasks."""

    def __init__(self, config: LabelStudioConfig) -> None:
        self.config = config

    def submit_tasks(self, tasks: Sequence[Mapping[str, Any]]) -> None:
        if not tasks:
            logger.debug("No review tasks to submit to Label Studio")
            return

        url = f"{self.config.api_url.rstrip('/')}/api/projects/{self.config.project_id}/tasks"
        response = requests.post(
            url,
            headers=self.config.headers(),
            data=json.dumps(tasks),
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - network failures in production
            logger.warning("Label Studio task submission failed: %s", exc)
            return
        logger.info("Submitted %s review tasks to Label Studio", len(tasks))

    def fetch_completed_annotations(self) -> list[dict[str, Any]]:
        url = f"{self.config.api_url.rstrip('/')}/api/projects/{self.config.project_id}/tasks"
        params = {"completed": True}
        try:
            response = requests.get(
                url,
                headers=self.config.headers(),
                params=params,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - defensive logging
            logger.warning("Label Studio fetch failed: %s", exc)
            return []
        payload = response.json()
        if isinstance(payload, list):
            return payload
        logger.debug("Unexpected Label Studio payload: %s", payload)
        return []


def serialize_review_tasks(
    review_pairs: Iterable[Mapping[str, Any]],
    thresholds: LinkageThresholds,
    fields: Iterable[str],
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    lower, upper = thresholds.bounds()
    for pair in review_pairs:
        record: dict[str, Any] = {
            "data": {
                "match_probability": pair.get("match_probability"),
                "left_record": {field: pair.get(f"left_{field}") for field in fields},
                "right_record": {field: pair.get(f"right_{field}") for field in fields},
                "thresholds": {"review_lower": lower, "match": upper},
            }
        }
        tasks.append(record)
    return tasks


def write_reviewer_decisions(
    decisions: Sequence[Mapping[str, Any]],
    path: Path,
    thresholds: LinkageThresholds,
) -> None:
    if not decisions:
        logger.debug("No reviewer decisions to persist")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for decision in decisions:
            payload = dict(decision)
            payload.setdefault("thresholds", thresholds.as_dict())
            handle.write(json.dumps(payload))
            handle.write("\n")
    logger.info("Persisted %s reviewer decisions to %s", len(decisions), path)
