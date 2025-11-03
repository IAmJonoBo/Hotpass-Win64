"""MLflow tracking and model registry integration for lead scoring models."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pandas as pd

LOGGER = logging.getLogger(__name__)


class ModelStage(str, Enum):
    """Valid stages for model promotion in the registry."""

    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


@dataclass
class MLflowConfig:
    """Configuration for MLflow tracking and registry."""

    tracking_uri: str = "sqlite:///mlflow.db"
    experiment_name: str = "lead_scoring"
    registry_uri: str | None = None
    artifact_location: str | None = None

    @classmethod
    def from_env(cls) -> MLflowConfig:
        """Load configuration from environment variables."""
        return cls(
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"),
            experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "lead_scoring"),
            registry_uri=os.getenv("MLFLOW_REGISTRY_URI"),
            artifact_location=os.getenv("MLFLOW_ARTIFACT_LOCATION"),
        )


def _load_mlflow(module: ModuleType | None) -> Any:
    """Import the mlflow module or return the provided override."""

    if module is not None:
        return module
    try:
        import mlflow
    except ImportError as exc:  # pragma: no cover - exercised via tests with stub
        msg = (
            "mlflow is required for model tracking. Install the 'ml_scoring' extra "
            "(pip install hotpass[ml_scoring])."
        )
        raise RuntimeError(msg) from exc
    return mlflow


def init_mlflow(
    config: MLflowConfig | None = None,
    *,
    mlflow_module: ModuleType | None = None,
) -> None:
    """Initialize MLflow tracking with the specified configuration."""

    mlflow = _load_mlflow(mlflow_module)

    if config is None:
        config = MLflowConfig.from_env()

    mlflow.set_tracking_uri(config.tracking_uri)
    if config.registry_uri:
        mlflow.set_registry_uri(config.registry_uri)

    # Create experiment if it doesn't exist
    experiment = mlflow.get_experiment_by_name(config.experiment_name)
    if experiment is None:
        kwargs = {}
        if config.artifact_location:
            kwargs["artifact_location"] = config.artifact_location
        mlflow.create_experiment(config.experiment_name, **kwargs)

    mlflow.set_experiment(config.experiment_name)


def _normalise_tag_value(value: Any) -> str | None:
    """Coerce metadata values into mlflow tag-friendly strings."""

    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str | int | float | bool):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return ", ".join(str(item) for item in sorted(value))
    if isinstance(value, Sequence) and not isinstance(value, (str | bytes | bytearray)):
        return ", ".join(str(item) for item in value)
    return repr(value)


def _iter_artifact_entries(
    artifacts: Mapping[str, Path] | None,
) -> Iterable[tuple[str, Path]]:
    """Yield artifact entries that exist on disk."""

    if not artifacts:
        return []
    existing: list[tuple[str, Path]] = []
    for name, path in artifacts.items():
        candidate = Path(path)
        if candidate.exists():
            existing.append((name, candidate))
    return existing


def log_training_run(
    *,
    model: Any,
    params: Mapping[str, Any],
    metrics: Mapping[str, float],
    metadata: Mapping[str, Any],
    artifacts: Mapping[str, Path] | None = None,
    model_name: str = "lead_scoring_model",
    signature: Any = None,
    input_example: pd.DataFrame | None = None,
    run_name: str | None = None,
    mlflow_module: ModuleType | None = None,
) -> str:
    """
    Log a training run with MLflow, including model, params, metrics, and artifacts.

    Returns the run ID of the logged run.
    """
    mlflow = _load_mlflow(mlflow_module)
    infer_signature = cast(Any, mlflow.models.infer_signature)

    if run_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"{model_name}_{timestamp}"

    run_context = cast(AbstractContextManager[Any], mlflow.start_run(run_name=run_name))

    with run_context as run:
        # Log parameters
        mlflow.log_params(params)

        # Log metrics
        mlflow.log_metrics(metrics)

        # Log metadata as tags
        for key, value in metadata.items():
            tag_value = _normalise_tag_value(value)
            if tag_value is not None:
                mlflow.set_tag(key, tag_value)

        # Infer signature if not provided
        if signature is None and input_example is not None:
            try:
                predictions = model.predict(input_example)
                signature = infer_signature(input_example, predictions)
            except Exception as exc:  # pragma: no cover - inference is best-effort
                LOGGER.debug(
                    "Signature inference failed; continuing without signature",
                    exc_info=exc,
                )

        # Log the model
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=model_name,
            signature=signature,
            input_example=input_example,
        )

        # Log additional artifacts
        for name, path in _iter_artifact_entries(artifacts):
            if path.is_file():
                mlflow.log_artifact(str(path), artifact_path=name)
            else:
                mlflow.log_artifacts(str(path), artifact_path=name)

        run_id = cast(str, getattr(run.info, "run_id", str(run.info)))
        return run_id


def promote_model(
    *,
    model_name: str,
    version: int | str,
    stage: ModelStage,
    archive_existing: bool = True,
    mlflow_module: ModuleType | None = None,
) -> None:
    """
    Promote a model version to a specific stage in the registry.

    Args:
        model_name: Name of the registered model
        version: Version number or "latest" to promote
        stage: Target stage for promotion
        archive_existing: Whether to archive existing models in the target stage
    """
    mlflow = _load_mlflow(mlflow_module)
    client = mlflow.MlflowClient()
    MlflowException = getattr(mlflow, "exceptions", None)
    if MlflowException is None or not hasattr(MlflowException, "MlflowException"):
        MlflowException = RuntimeError
    else:  # pragma: no branch - simple attribute lookup
        MlflowException = MlflowException.MlflowException

    # Resolve version if "latest"
    if isinstance(version, str) and version.lower() == "latest":
        versions = client.search_model_versions(f"name='{model_name}'")
        if not versions:
            msg = f"No versions found for model '{model_name}'"
            raise ValueError(msg)
        version = max(int(v.version) for v in versions)

    version_str = str(version)

    # Archive existing models in the target stage if requested
    if archive_existing and stage not in (ModelStage.NONE, ModelStage.ARCHIVED):
        try:
            existing = client.get_latest_versions(model_name, stages=[stage.value])
            for existing_version in existing:
                client.transition_model_version_stage(
                    name=model_name,
                    version=existing_version.version,
                    stage=ModelStage.ARCHIVED.value,
                )
        except MlflowException:
            # No existing versions in this stage
            pass

    # Transition the specified version to the target stage
    client.transition_model_version_stage(
        name=model_name,
        version=version_str,
        stage=stage.value,
    )


def load_production_model(
    model_name: str = "lead_scoring_model",
    *,
    mlflow_module: ModuleType | None = None,
) -> Any:
    """
    Load the production model from the registry.

    Returns:
        The loaded model ready for inference.
    """
    mlflow = _load_mlflow(mlflow_module)
    model_uri = f"models:/{model_name}/Production"
    return mlflow.sklearn.load_model(model_uri)


def get_model_metadata(
    model_name: str,
    stage: ModelStage | None = None,
    *,
    mlflow_module: ModuleType | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve metadata for model versions in the registry.

    Args:
        model_name: Name of the registered model
        stage: Optional stage filter (e.g., Production, Staging)

    Returns:
        List of model version metadata dictionaries
    """
    mlflow = _load_mlflow(mlflow_module)
    client = mlflow.MlflowClient()

    if stage:
        versions = client.get_latest_versions(model_name, stages=[stage.value])
    else:
        versions = client.search_model_versions(f"name='{model_name}'")

    return [
        {
            "version": v.version,
            "stage": v.current_stage,
            "run_id": v.run_id,
            "creation_timestamp": v.creation_timestamp,
            "last_updated_timestamp": v.last_updated_timestamp,
        }
        for v in versions
    ]


__all__ = [
    "MLflowConfig",
    "ModelStage",
    "init_mlflow",
    "log_training_run",
    "promote_model",
    "load_production_model",
    "get_model_metadata",
]
