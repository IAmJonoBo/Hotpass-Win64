"""Exercise MLflow tracking helpers without the real dependency installed."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from hotpass.ml.tracking import (MLflowConfig, ModelStage, get_model_metadata,
                                 init_mlflow, load_production_model,
                                 log_training_run, promote_model)



def expect(condition: bool, message: str) -> None:
    """Project-wide assert helper to keep Bandit checks green."""

    if not condition:
        raise AssertionError(message)


@dataclass(slots=True)
class _RunRecord:
    """Capture run metadata stored by the fake mlflow implementation."""

    run_id: str
    params: dict[str, Any]
    metrics: dict[str, float]
    tags: dict[str, str]
    artifacts: dict[str, list[str]]


@dataclass(slots=True)
class _VersionRecord:
    """Represent a registered model version."""

    name: str
    version: str
    current_stage: str
    run_id: str
    creation_timestamp: int
    last_updated_timestamp: int


class _FakeMlflowState:
    """Mutable state shared between stubbed mlflow APIs."""

    def __init__(self) -> None:
        self.tracking_uri: str | None = None
        self.registry_uri: str | None = None
        self.experiments: dict[str, SimpleNamespace] = {}
        self._next_experiment_id = 1
        self.active_experiment: str | None = None
        self._next_run_id = 1
        self.active_run_id: str | None = None
        self.runs: dict[str, _RunRecord] = {}
        self.logged_models: list[dict[str, Any]] = []
        self.logged_artifacts: list[tuple[str, str, str]] = []
        self.model_versions: dict[str, list[_VersionRecord]] = {}
        self._next_version_timestamp = 1
        self.loaded_models: list[str] = []

    # Experiment helpers -------------------------------------------------
    def get_experiment(self, name: str) -> SimpleNamespace | None:
        return self.experiments.get(name)

    def create_experiment(
        self, name: str, *, artifact_location: str | None
    ) -> SimpleNamespace:
        experiment = SimpleNamespace(
            name=name,
            experiment_id=str(self._next_experiment_id),
            artifact_location=artifact_location,
        )
        self._next_experiment_id += 1
        self.experiments[name] = experiment
        return experiment

    def set_active_experiment(self, name: str) -> None:
        self.active_experiment = name

    # Run helpers --------------------------------------------------------
    def begin_run(self, run_name: str | None) -> _RunRecord:
        run_id = f"run-{self._next_run_id}"
        self._next_run_id += 1
        record = _RunRecord(
            run_id=run_id,
            params={},
            metrics={},
            tags={"mlflow.runName": run_name or run_id},
            artifacts={},
        )
        self.active_run_id = run_id
        self.runs[run_id] = record
        return record

    def end_run(self) -> None:
        self.active_run_id = None

    def update_params(self, params: Mapping[str, Any]) -> None:
        if self.active_run_id is None:
            raise RuntimeError("No active run to update parameters")
        record = self.runs[self.active_run_id]
        record.params.update({key: str(value) for key, value in params.items()})

    def update_metrics(self, metrics: Mapping[str, float]) -> None:
        if self.active_run_id is None:
            raise RuntimeError("No active run to update metrics")
        record = self.runs[self.active_run_id]
        record.metrics.update({key: float(value) for key, value in metrics.items()})

    def set_tag(self, key: str, value: Any) -> None:
        if self.active_run_id is None:
            raise RuntimeError("No active run to set tags")
        record = self.runs[self.active_run_id]
        record.tags[key] = str(value)

    def record_artifact(
        self, run_id: str, artifact_path: str, destination: str
    ) -> None:
        entries = self.runs[run_id].artifacts.setdefault(destination, [])
        entries.append(artifact_path)
        self.logged_artifacts.append((run_id, destination, artifact_path))

    # Model registry helpers --------------------------------------------
    def register_version(
        self, name: str, version: int, stage: str, run_id: str
    ) -> None:
        record = _VersionRecord(
            name=name,
            version=str(version),
            current_stage=stage,
            run_id=run_id,
            creation_timestamp=self._next_version_timestamp,
            last_updated_timestamp=self._next_version_timestamp,
        )
        self._next_version_timestamp += 1
        self.model_versions.setdefault(name, []).append(record)

    def update_stage(self, name: str, version: str, stage: str) -> None:
        for record in self.model_versions.get(name, []):
            if record.version == str(version):
                record.current_stage = stage
                record.last_updated_timestamp = self._next_version_timestamp
                self._next_version_timestamp += 1
                break


class _RunContext:
    """Context manager used by the fake mlflow start_run implementation."""

    def __init__(self, state: _FakeMlflowState, run_name: str | None) -> None:
        self._state = state
        self.info = SimpleNamespace(run_id=state.begin_run(run_name).run_id)

    def __enter__(self) -> _RunContext:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self._state.end_run()


class _FakeMlflowClient:
    """Subset of MlflowClient used by the tracking helpers."""

    def __init__(self, state: _FakeMlflowState) -> None:
        self._state = state

    def search_model_versions(self, filter_string: str) -> list[_VersionRecord]:
        name = filter_string.split("=")[-1].strip("'")
        return list(self._state.model_versions.get(name, []))

    def get_latest_versions(
        self, name: str, stages: list[str] | None = None
    ) -> list[_VersionRecord]:
        versions = self._state.model_versions.get(name, [])
        if not stages:
            return list(versions)
        return [record for record in versions if record.current_stage in stages]

    def transition_model_version_stage(
        self, name: str, version: str, stage: str
    ) -> None:
        self._state.update_stage(name, version, stage)


class _FakeMlflowException(RuntimeError):
    """Exception mirroring mlflow.exceptions.MlflowException."""


def _build_fake_mlflow() -> tuple[ModuleType, _FakeMlflowState]:
    module = ModuleType("mlflow")
    state = _FakeMlflowState()

    models_module = ModuleType("mlflow.models")

    def infer_signature(features: Any, predictions: Any) -> dict[str, Any]:
        column_count = len(getattr(features, "columns", []))
        return {"fields": column_count, "predictions": list(predictions)}

    setattr(models_module, "infer_signature", infer_signature)
    setattr(module, "models", models_module)

    sklearn_module = ModuleType("mlflow.sklearn")

    def log_model(**kwargs: Any) -> None:
        state.logged_models.append(dict(kwargs))

    def load_model(uri: str) -> dict[str, str]:
        state.loaded_models.append(uri)
        return {"loaded": uri}

    setattr(sklearn_module, "log_model", log_model)
    setattr(sklearn_module, "load_model", load_model)
    setattr(module, "sklearn", sklearn_module)

    def start_run(run_name: str | None = None) -> _RunContext:
        return _RunContext(state, run_name)

    setattr(module, "start_run", start_run)

    def set_tracking_uri(uri: str) -> None:
        state.tracking_uri = uri

    def set_registry_uri(uri: str) -> None:
        state.registry_uri = uri

    setattr(module, "set_tracking_uri", set_tracking_uri)

    setattr(module, "set_registry_uri", set_registry_uri)
    setattr(module, "get_experiment_by_name", state.get_experiment)

    def create_experiment(
        name: str, *, artifact_location: str | None = None
    ) -> SimpleNamespace:
        return state.create_experiment(name, artifact_location=artifact_location)

    setattr(module, "create_experiment", create_experiment)
    setattr(module, "set_experiment", state.set_active_experiment)

    setattr(module, "log_params", state.update_params)
    setattr(module, "log_metrics", state.update_metrics)
    setattr(module, "set_tag", state.set_tag)

    def log_artifact(path: str, artifact_path: str | None = None) -> None:
        run_id = state.active_run_id
        if run_id is None:
            raise RuntimeError("Artifact logging requires an active run")
        destination = artifact_path or "root"
        state.record_artifact(run_id, path, destination)

    def log_artifacts(path: str, artifact_path: str | None = None) -> None:
        log_artifact(path, artifact_path)

    setattr(module, "log_artifact", log_artifact)
    setattr(module, "log_artifacts", log_artifacts)

    def get_run(run_id: str) -> SimpleNamespace:
        record = state.runs[run_id]
        return SimpleNamespace(
            data=SimpleNamespace(
                params=record.params,
                metrics=record.metrics,
                tags=record.tags,
            )
        )

    setattr(module, "get_run", get_run)

    exceptions_module = ModuleType("mlflow.exceptions")
    setattr(exceptions_module, "MlflowException", _FakeMlflowException)
    setattr(module, "exceptions", exceptions_module)

    def mlflow_client_factory() -> _FakeMlflowClient:
        return _FakeMlflowClient(state)

    setattr(module, "MlflowClient", mlflow_client_factory)

    return module, state


def test_init_mlflow_creates_experiment() -> None:
    module, state = _build_fake_mlflow()
    config = MLflowConfig(
        tracking_uri="sqlite:///tmp.db",
        experiment_name="stub_experiment",
        registry_uri="sqlite:///registry.db",
        artifact_location="/tmp/artifacts",
    )

    init_mlflow(config, mlflow_module=module)

    experiment = state.get_experiment("stub_experiment")
    expect(experiment is not None, "Experiment should be created")
    expect(state.tracking_uri == "sqlite:///tmp.db", "Tracking URI should be recorded")
    expect(
        state.registry_uri == "sqlite:///registry.db", "Registry URI should be recorded"
    )
    expect(
        state.active_experiment == "stub_experiment", "Experiment should be activated"
    )


def test_init_mlflow_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    module, state = _build_fake_mlflow()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///env.db")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "env_experiment")
    monkeypatch.delenv("MLFLOW_REGISTRY_URI", raising=False)
    monkeypatch.setenv(
        "MLFLOW_ARTIFACT_LOCATION", os.fspath(Path("/tmp/env-artifacts"))
    )

    init_mlflow(mlflow_module=module)

    experiment = state.get_experiment("env_experiment")
    expect(experiment is not None, "Environment-driven experiment should be created")
    expect(
        state.tracking_uri == "sqlite:///env.db",
        "Tracking URI should use environment value",
    )
    expect(state.registry_uri is None, "Registry URI remains unset when not provided")
    expect(
        state.active_experiment == "env_experiment",
        "Environment experiment should activate",
    )


def test_log_training_run_records_payload(tmp_path: Path) -> None:
    module, state = _build_fake_mlflow()
    init_mlflow(MLflowConfig(experiment_name="demo"), mlflow_module=module)

    class DummyModel:
        def predict(self, frame: pd.DataFrame) -> list[float]:
            return [float(value) for value in frame.index]

    feature_frame = pd.DataFrame({"value": [1, 2, 3]})
    artifact_file = tmp_path / "metrics.json"
    artifact_file.write_text("{}")
    artifact_dir = tmp_path / "charts"
    artifact_dir.mkdir()

    run_id = log_training_run(
        model=DummyModel(),
        params={"max_depth": 3},
        metrics={"auc": 0.91},
        metadata={"owners": ("ml", "qa"), "release_candidate": True},
        artifacts={"file": artifact_file, "dir": artifact_dir},
        model_name="demo_model",
        input_example=feature_frame,
        mlflow_module=module,
    )

    expect(run_id in state.runs, "Run should be tracked")
    record = state.runs[run_id]
    expect(record.params["max_depth"] == "3", "Parameters should be stringified")
    expect(record.metrics["auc"] == 0.91, "Metrics should be stored")
    expect("owners" in record.tags, "Metadata should be stored as tags")
    expect(
        "file" in record.artifacts and "dir" in record.artifacts,
        "Artifacts should be logged",
    )
    expect(bool(state.logged_models), "Model logging should capture payloads")


def test_log_training_run_formats_metadata_and_skips_missing_artifacts(
    tmp_path: Path,
) -> None:
    module, state = _build_fake_mlflow()
    init_mlflow(MLflowConfig(experiment_name="metadata"), mlflow_module=module)

    class DummyModel:
        def predict(self, frame: pd.DataFrame) -> list[float]:
            return [float(value) for value in frame.index]

    feature_frame = pd.DataFrame({"value": [0, 1]})
    missing_artifact = tmp_path / "missing"
    metadata_path = tmp_path / "metadata.txt"
    metadata_path.write_text("details")

    run_id = log_training_run(
        model=DummyModel(),
        params={"depth": 4},
        metrics={"accuracy": 0.9},
        metadata={
            "stage": ModelStage.STAGING,
            "scheduled_at": datetime(2024, 1, 1, 12, 30, 15),
            "owners": ["ml", "qa"],
            "location": metadata_path,
            "raw": {"k": "v"},
        },
        artifacts={"missing": missing_artifact},
        model_name="meta_model",
        input_example=feature_frame,
        mlflow_module=module,
    )

    record = state.runs[run_id]
    expect(
        record.tags["stage"] == ModelStage.STAGING.value,
        "Enums should record their value",
    )
    expect(
        record.tags["scheduled_at"].startswith("2024-01-01T12:30:15"),
        "Datetime tags should be ISO formatted",
    )
    expect(record.tags["owners"] == "ml, qa", "Iterable metadata should join values")
    expect(
        record.tags["location"] == str(metadata_path), "Path metadata coerces to string"
    )
    expect(
        record.tags["raw"].startswith("{'k': 'v'"), "Fallback repr used for mappings"
    )
    expect("missing" not in record.artifacts, "Missing artifacts are ignored")


def test_promote_model_archives_existing() -> None:
    module, state = _build_fake_mlflow()
    state.register_version(
        "demo", version=1, stage=ModelStage.PRODUCTION.value, run_id="run-1"
    )
    state.register_version(
        "demo", version=2, stage=ModelStage.STAGING.value, run_id="run-2"
    )

    promote_model(
        model_name="demo",
        version="latest",
        stage=ModelStage.PRODUCTION,
        archive_existing=True,
        mlflow_module=module,
    )

    prod_versions = [
        v
        for v in state.model_versions["demo"]
        if v.current_stage == ModelStage.PRODUCTION.value
    ]
    archived_versions = [
        v
        for v in state.model_versions["demo"]
        if v.current_stage == ModelStage.ARCHIVED.value
    ]
    expect(
        len(prod_versions) == 1 and prod_versions[0].version == "2",
        "Latest version promoted",
    )
    expect(
        any(v.version == "1" for v in archived_versions), "Previous production archived"
    )


def test_promote_model_without_existing_versions_raises() -> None:
    module, _ = _build_fake_mlflow()

    with pytest.raises(ValueError) as exc:
        promote_model(
            model_name="demo",
            version="latest",
            stage=ModelStage.PRODUCTION,
            mlflow_module=module,
        )

    expect(
        "No versions found" in str(exc.value), "Error should mention missing versions"
    )


def test_promote_model_skips_archiving_when_disabled() -> None:
    module, state = _build_fake_mlflow()
    state.register_version(
        "demo", version=1, stage=ModelStage.STAGING.value, run_id="run-1"
    )
    state.register_version(
        "demo", version=2, stage=ModelStage.STAGING.value, run_id="run-2"
    )

    promote_model(
        model_name="demo",
        version=2,
        stage=ModelStage.STAGING,
        archive_existing=False,
        mlflow_module=module,
    )

    staging_versions = [
        v
        for v in state.model_versions["demo"]
        if v.current_stage == ModelStage.STAGING.value
    ]
    expect(
        len(staging_versions) == 2,
        "Existing staging versions remain when archiving disabled",
    )


def test_model_loading_and_metadata() -> None:
    module, state = _build_fake_mlflow()
    state.register_version(
        "demo", version=1, stage=ModelStage.STAGING.value, run_id="run-10"
    )
    state.register_version(
        "demo", version=3, stage=ModelStage.PRODUCTION.value, run_id="run-11"
    )

    result = load_production_model("demo", mlflow_module=module)
    expect(
        result["loaded"].endswith("/Production"),
        "Model URI should target production stage",
    )
    expect(state.loaded_models[-1].endswith("/Production"), "Load should record URI")

    metadata = get_model_metadata(
        "demo", stage=ModelStage.PRODUCTION, mlflow_module=module
    )
    expect(len(metadata) == 1, "Stage filter should restrict to production")
    expect(metadata[0]["version"] == "3", "Metadata should reflect active version")

    all_metadata = get_model_metadata("demo", mlflow_module=module)
    expect(
        len(all_metadata) == 2, "Metadata without stage should include every version"
    )
