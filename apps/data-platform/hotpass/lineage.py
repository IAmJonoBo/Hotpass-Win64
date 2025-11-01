"""Helpers for emitting OpenLineage events from Hotpass runs."""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, cast
from uuid import uuid4
from importlib import metadata

OpenLineageClient: Any | None
set_lineage_producer: Callable[[str], None] | None
InputDataset: Any
OutputDataset: Any
Job: Any
Run: Any
RunEvent: Any
RunState: Any

try:
    _client_module = importlib.import_module("openlineage.client")
    _events_module = importlib.import_module("openlineage.client.event_v2")
except Exception:  # pragma: no cover - optional dependency
    OpenLineageClient = None
    set_lineage_producer = None
    InputDataset = OutputDataset = Job = Run = RunEvent = None
    RunState = None
else:
    OpenLineageClient = getattr(_client_module, "OpenLineageClient", None)
    set_lineage_producer = getattr(_client_module, "set_producer", None)
    InputDataset = getattr(_events_module, "InputDataset", None)
    OutputDataset = getattr(_events_module, "OutputDataset", None)
    Job = getattr(_events_module, "Job", None)
    Run = getattr(_events_module, "Run", None)
    RunEvent = getattr(_events_module, "RunEvent", None)
    RunState = getattr(_events_module, "RunState", None)

logger = logging.getLogger(__name__)

DEFAULT_NAMESPACE = "hotpass.local"
DEFAULT_PRODUCER = "https://hotpass.dev/lineage"

DatasetSpec = str | Path | Mapping[str, object]

try:
    _HOTPASS_VERSION = metadata.version("hotpass")
except metadata.PackageNotFoundError:  # pragma: no cover - during editable installs
    _HOTPASS_VERSION = "unknown"


def _build_facet_block(facets: Mapping[str, Any] | None, producer: str) -> dict[str, Any]:
    if not facets:
        return {}
    cleaned: dict[str, Any] = {"_producer": producer}
    for key, value in facets.items():
        if value is None:
            continue
        cleaned[key] = value
    return {"hotpass": cleaned}


class LineageEmitter:
    """Thin wrapper around the OpenLineage client with graceful fallbacks."""

    def __init__(
        self,
        job_name: str,
        *,
        run_id: str | None = None,
        namespace: str | None = None,
        producer: str | None = None,
        facets: Mapping[str, Any] | None = None,
    ) -> None:
        self.job_name = job_name
        self.namespace = namespace or os.getenv("HOTPASS_LINEAGE_NAMESPACE", DEFAULT_NAMESPACE)
        self.run_id = str(run_id or uuid4())
        resolved_producer = producer or os.getenv("HOTPASS_LINEAGE_PRODUCER", DEFAULT_PRODUCER)
        self.producer = str(resolved_producer)
        self._inputs: Sequence[Any] | None = None
        self._run_facets = _build_facet_block(facets, self.producer)
        self._job_facets = dict(self._run_facets)

        self._client: Any | None = self._initialise_client()
        self._active = self._client is not None
        if self._active and set_lineage_producer is not None:
            try:
                set_lineage_producer(self.producer)
            except Exception:  # pragma: no cover - defensive guard
                logger.debug("Unable to set OpenLineage producer URI", exc_info=True)

    @property
    def is_enabled(self) -> bool:
        return self._active

    def emit_start(
        self,
        *,
        inputs: Iterable[DatasetSpec] | None = None,
    ) -> None:
        if (
            not self._active
            or InputDataset is None
            or RunEvent is None
            or RunState is None
            or Job is None
            or Run is None
        ):
            return
        self._inputs = self._build_datasets(inputs or (), InputDataset)
        event = RunEvent(
            eventTime=_now(),
            producer=self.producer,
            eventType=RunState.START,
            run=Run(runId=self.run_id, facets=self._run_facets),
            job=Job(namespace=self.namespace, name=self.job_name, facets=self._job_facets),
            inputs=list(self._inputs),
            outputs=[],
        )
        self._emit(event)

    def emit_complete(
        self,
        *,
        outputs: Iterable[DatasetSpec] | None = None,
    ) -> None:
        if (
            not self._active
            or OutputDataset is None
            or RunEvent is None
            or RunState is None
            or Job is None
            or Run is None
        ):
            return
        event = RunEvent(
            eventTime=_now(),
            producer=self.producer,
            eventType=RunState.COMPLETE,
            run=Run(runId=self.run_id, facets=self._run_facets),
            job=Job(namespace=self.namespace, name=self.job_name, facets=self._job_facets),
            inputs=list(self._inputs or []),
            outputs=self._build_datasets(outputs or (), OutputDataset),
        )
        self._emit(event)

    def emit_fail(
        self,
        message: str,
        *,
        outputs: Iterable[DatasetSpec] | None = None,
    ) -> None:
        if (
            not self._active
            or OutputDataset is None
            or RunEvent is None
            or RunState is None
            or Job is None
            or Run is None
        ):
            return
        event = RunEvent(
            eventTime=_now(),
            producer=self.producer,
            eventType=RunState.FAIL,
            run=Run(runId=self.run_id, facets=self._run_facets),
            job=Job(namespace=self.namespace, name=self.job_name, facets=self._job_facets),
            inputs=list(self._inputs or []),
            outputs=self._build_datasets(outputs or (), OutputDataset),
        )
        logger.debug("Emitting OpenLineage FAIL event for %s: %s", self.job_name, message)
        self._emit(event)

    def _initialise_client(self) -> Any | None:
        if OpenLineageClient is None:
            return None
        if os.getenv("HOTPASS_DISABLE_LINEAGE", "0") == "1":
            return None
        try:
            return OpenLineageClient()
        except Exception:  # pragma: no cover - defensive guard
            logger.warning("OpenLineage client unavailable", exc_info=True)
            return None

    def _emit(self, event: Any) -> None:
        if not self._active or self._client is None:
            return
        try:
            self._client.emit(event)
        except Exception:  # pragma: no cover - defensive guard
            logger.warning("Failed to emit OpenLineage event", exc_info=True)

    def _build_datasets(
        self,
        specs: Iterable[DatasetSpec],
        dataset_cls: type[Any] | None,
    ) -> list[Any]:
        datasets: list[Any] = []
        if dataset_cls is None:
            return datasets
        for spec in specs:
            dataset = self._normalise_dataset(spec, dataset_cls)
            if dataset is not None:
                datasets.append(dataset)
        return datasets

    def _normalise_dataset(
        self,
        spec: DatasetSpec,
        dataset_cls: type[Any],
    ) -> Any | None:
        namespace = self.namespace
        facets: Mapping[str, object] | None = None
        name: str | None = None

        try:
            if isinstance(spec, Mapping):
                name = str(spec.get("name") or "").strip() or None
                namespace = str(spec.get("namespace") or namespace)
                facets = cast(Mapping[str, object] | None, spec.get("facets"))
            elif isinstance(spec, Path):
                name = str(spec.expanduser().resolve())
            else:
                candidate = str(spec).strip()
                if candidate:
                    name = _normalise_path_string(candidate)
        except Exception:  # pragma: no cover - defensive guard
            logger.debug(
                "Unable to convert dataset spec '%s' into OpenLineage dataset",
                spec,
                exc_info=True,
            )
            return None

        if not name:
            return None
        try:
            return dataset_cls(namespace=namespace, name=name, facets=facets or {})
        except Exception:  # pragma: no cover - defensive guard
            logger.debug(
                "Failed to instantiate %s for %s",
                dataset_cls.__name__,
                name,
                exc_info=True,
            )
        return None


def discover_input_datasets(
    input_dir: Path, patterns: Sequence[str] | None = None
) -> list[DatasetSpec]:
    """Return the datasets that describe pipeline inputs for lineage."""

    datasets: list[DatasetSpec] = []
    seen: set[str] = set()
    search_patterns = patterns or ("*.parquet", "*.csv", "*.xlsx", "*.xls")

    try:
        for pattern in search_patterns:
            for candidate in sorted(input_dir.glob(pattern)):
                if not candidate.is_file():
                    continue
                try:
                    normalised = str(candidate.expanduser().resolve())
                except Exception:  # pragma: no cover - filesystem edge case
                    normalised = str(candidate)
                if normalised in seen:
                    continue
                seen.add(normalised)
                datasets.append(candidate)
    except Exception:  # pragma: no cover - defensive guard
        logger.debug(
            "Unable to enumerate input datasets in %s for lineage emission",
            input_dir,
            exc_info=True,
        )

    if not datasets:
        datasets.append(input_dir)
    return datasets


def build_output_datasets(*paths: DatasetSpec | None) -> list[DatasetSpec]:
    """Normalise pipeline outputs into lineage dataset specifications."""

    datasets: list[DatasetSpec] = []
    for path in paths:
        if path is None:
            continue
        datasets.append(path)
    return datasets


class NullLineageEmitter(LineageEmitter):
    """No-op variant used when OpenLineage is unavailable."""

    def __init__(self, *args: object, **kwargs: object) -> None:  # noqa: D401
        self.job_name = ""
        self.namespace = DEFAULT_NAMESPACE
        self.run_id = str(uuid4())
        self.producer = DEFAULT_PRODUCER
        self._inputs = None
        self._client = None
        self._active = False

    def emit_start(
        self, *, inputs: Iterable[DatasetSpec] | None = None
    ) -> None:  # noqa: D401, ARG002
        return

    def emit_complete(
        self,
        *,
        outputs: Iterable[DatasetSpec] | None = None,  # noqa: D401, ARG002
    ) -> None:
        return

    def emit_fail(
        self,
        message: str,  # noqa: D401, ARG002
        *,
        outputs: Iterable[DatasetSpec] | None = None,  # noqa: ARG002
    ) -> None:
        return


def create_emitter(
    job_name: str,
    *,
    run_id: str | None = None,
    namespace: str | None = None,
    producer: str | None = None,
    facets: Mapping[str, Any] | None = None,
) -> LineageEmitter:
    facet_payload = facets or {"hotpass_version": _HOTPASS_VERSION}
    emitter = LineageEmitter(
        job_name,
        run_id=run_id,
        namespace=namespace,
        producer=producer,
        facets=facet_payload,
    )
    if emitter.is_enabled:
        return emitter
    return NullLineageEmitter()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _normalise_path_string(value: str) -> str:
    if "://" in value:
        return value
    return str(Path(value).expanduser())


def build_hotpass_run_facet(
    *,
    profile: str | None,
    source_spreadsheet: str | None,
    research_enabled: bool | None,
) -> Mapping[str, Any]:
    facet: dict[str, Any] = {
        "hotpass_version": _HOTPASS_VERSION,
    }
    if profile:
        facet["profile"] = profile
    if source_spreadsheet:
        facet["source_spreadsheet"] = source_spreadsheet
    if research_enabled is not None:
        facet["research_enabled"] = bool(research_enabled)
    return facet


__all__ = [
    "build_output_datasets",
    "create_emitter",
    "discover_input_datasets",
    "LineageEmitter",
    "NullLineageEmitter",
    "build_hotpass_run_facet",
]
