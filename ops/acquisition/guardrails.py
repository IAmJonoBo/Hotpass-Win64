"""Guardrails for compliant data acquisition scripts."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib import request
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

__all__ = [
    "CollectionGuards",
    "ProviderPolicy",
    "ProvenanceLedger",
    "RobotsTxtGuard",
    "TermsOfServicePolicy",
]


def _default_fetcher(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme for fetcher: {parsed.scheme or 'none'}")
    if not parsed.netloc:
        raise ValueError("Remote fetches require a hostname")

    with request.urlopen(url) as response:  # noqa: S310 - validated scheme  # nosec B310
        content_bytes = response.read()
    return cast(str, content_bytes.decode("utf-8"))


@dataclass(slots=True)
class TermsOfServicePolicy:
    """Snapshot of a terms-of-service artefact with a stable hash."""

    identifier: str
    hash: str
    retrieved_at: float = field(default_factory=lambda: time.time())

    @classmethod
    def from_text(cls, identifier: str, text: str) -> TermsOfServicePolicy:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return cls(identifier=identifier, hash=digest)

    @classmethod
    def from_path(cls, path: Path) -> TermsOfServicePolicy:
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_text(str(path), text)


@dataclass(slots=True)
class ProviderPolicy:
    """Allowlist of providers with compliance metadata."""

    providers: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_path(cls, path: Path) -> ProviderPolicy:
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = {
            name.lower(): dict(metadata) for name, metadata in data.get("providers", {}).items()
        }
        return cls(providers=allowed)

    def ensure_allowed(self, name: str) -> Mapping[str, Any]:
        try:
            return self.providers[name.lower()]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise PermissionError(f"Provider '{name}' is not allowlisted for acquisition") from exc


class RobotsTxtGuard:
    """Evaluate robots.txt rules for acquisition targets."""

    def __init__(
        self,
        robots_location: str,
        *,
        user_agent: str = "HotpassDataCollector",
        fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self._robots_location = robots_location
        self._user_agent = user_agent
        self._fetcher = fetcher or _default_fetcher
        self._parser: RobotFileParser | None = None

    def _load(self) -> RobotFileParser:
        if self._parser is not None:
            return self._parser

        parser = RobotFileParser()
        location = self._robots_location
        parsed = urlparse(location)
        if parsed.scheme in {"", "file"}:
            path = Path(parsed.path)
            content = path.read_text(encoding="utf-8")
            parser.parse(content.splitlines())
        else:
            content = self._fetcher(location)
            parser.parse(content.splitlines())
        parser.set_url(location)
        self._parser = parser
        return parser

    def ensure_allowed(self, url: str) -> None:
        parser = self._load()
        if not parser.can_fetch(self._user_agent, url):
            raise PermissionError(
                f"Robots.txt disallows fetching {url} for agent {self._user_agent}"
            )


@dataclass(slots=True)
class ProvenanceLedger:
    """Append-only ledger capturing data acquisition provenance."""

    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        record_id: str,
        source: str,
        license: str,
        policy_hash: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        entry = {
            "record_id": record_id,
            "source": source,
            "license": license,
            "policy_hash": policy_hash,
            "metadata": dict(metadata or {}),
            "timestamp": time.time(),
        }
        serialized = json.dumps(entry, sort_keys=True)
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.write("\n")
        finally:
            if os.path.exists(self.path):
                os.utime(self.path, None)


@dataclass(slots=True)
class CollectionGuards:
    """Coordinate robots.txt enforcement and provenance logging."""

    robots_guard: RobotsTxtGuard
    ledger: ProvenanceLedger
    tos_policy: TermsOfServicePolicy

    def guard_record(
        self,
        *,
        record_id: str,
        source_url: str,
        license: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.robots_guard.ensure_allowed(source_url)
        self.ledger.append(
            record_id=record_id,
            source=source_url,
            license=license,
            policy_hash=self.tos_policy.hash,
            metadata=metadata,
        )

    def guard_many(
        self,
        records: Iterable[tuple[str, Mapping[str, Any]]],
        *,
        source_url: str,
        license: str,
    ) -> None:
        for record_id, metadata in records:
            self.guard_record(
                record_id=record_id,
                source_url=source_url,
                license=license,
                metadata=metadata,
            )
