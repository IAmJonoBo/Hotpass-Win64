"""Tests for MLflow tracking and model registry integration."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from tests.helpers.fixtures import fixture

# Helper to check if MLflow is available
pytest.importorskip("mlflow", reason="MLflow required for tracking tests")

from hotpass.ml.tracking import (
    MLflowConfig,
    ModelStage,
    get_model_metadata,
    init_mlflow,
    load_production_model,
    log_training_run,
    promote_model,
)
from hotpass.transform.scoring import train_lead_scoring_model


def expect(condition: bool, message: str) -> None:
    """Assert-free test helper following project conventions."""
    if not condition:
        raise AssertionError(message)


def _build_training_frame() -> pd.DataFrame:
    """Build a sample dataset for training tests."""
    return pd.DataFrame(
        {
            "completeness": [0.9, 0.4, 0.75, 0.3, 0.85, 0.6, 0.7, 0.5],
            "email_confidence": [0.8, 0.1, 0.6, 0.2, 0.75, 0.5, 0.55, 0.3],
            "phone_confidence": [0.7, 0.0, 0.4, 0.2, 0.65, 0.3, 0.45, 0.25],
            "source_priority": [1.0, 0.2, 0.6, 0.1, 0.9, 0.4, 0.5, 0.3],
            "intent_signal_score": [0.9, 0.3, 0.5, 0.2, 0.8, 0.4, 0.6, 0.35],
            "won": [1, 0, 1, 0, 1, 0, 1, 0],
        }
    )


@fixture
def temp_mlflow_db(tmp_path: Path) -> str:
    """Create a temporary MLflow tracking database."""
    db_path = tmp_path / "mlflow.db"
    tracking_uri = f"sqlite:///{db_path}"
    return tracking_uri


@fixture
def mlflow_config(temp_mlflow_db: str) -> MLflowConfig:
    """Create MLflow configuration with temporary database."""
    return MLflowConfig(
        tracking_uri=temp_mlflow_db,
        experiment_name="test_lead_scoring",
    )


def test_mlflow_config_from_env():
    """Test loading MLflow configuration from environment variables."""
    with patch.dict(
        os.environ,
        {
            "MLFLOW_TRACKING_URI": "sqlite:///test.db",
            "MLFLOW_EXPERIMENT_NAME": "custom_experiment",
            "MLFLOW_REGISTRY_URI": "sqlite:///registry.db",
        },
    ):
        config = MLflowConfig.from_env()
        expect(
            config.tracking_uri == "sqlite:///test.db",
            "Tracking URI should be loaded from environment",
        )
        expect(
            config.experiment_name == "custom_experiment",
            "Experiment name should be loaded from environment",
        )
        expect(
            config.registry_uri == "sqlite:///registry.db",
            "Registry URI should be loaded from environment",
        )


def test_init_mlflow_creates_experiment(mlflow_config: MLflowConfig):
    """Test that init_mlflow creates the experiment if it doesn't exist."""
    import mlflow

    init_mlflow(mlflow_config)

    experiment = mlflow.get_experiment_by_name(mlflow_config.experiment_name)
    expect(experiment is not None, "Experiment should be created")
    expect(
        experiment.name == mlflow_config.experiment_name,
        "Experiment name should match configuration",
    )


def test_log_training_run_records_metrics(mlflow_config: MLflowConfig, tmp_path: Path):
    """Test that log_training_run logs parameters, metrics, and model."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    # Train a simple model
    X_train = pd.DataFrame({"feature1": [0.1, 0.2, 0.3, 0.4], "feature2": [0.5, 0.6, 0.7, 0.8]})
    y_train = pd.Series([0, 0, 1, 1])

    model = LogisticRegression(max_iter=100, random_state=42)
    model.fit(X_train, y_train)

    params = {"max_iter": 100, "random_state": 42}
    metrics = {"accuracy": 0.85, "precision": 0.80}
    metadata = {"test_key": "test_value", "trained_at": "2025-10-28"}

    run_id = log_training_run(
        model=model,
        params=params,
        metrics=metrics,
        metadata=metadata,
        model_name="test_model",
        input_example=X_train.head(2),
    )

    expect(run_id is not None, "Run ID should be returned")
    expect(len(run_id) > 0, "Run ID should not be empty")

    # Verify run details
    run = mlflow.get_run(run_id)
    expect(run.data.params["max_iter"] == "100", "Parameters should be logged")
    expect(run.data.metrics["accuracy"] == 0.85, "Metrics should be logged")
    expect("test_key" in run.data.tags, "Metadata should be logged as tags")


def test_log_training_run_with_artifacts(mlflow_config: MLflowConfig, tmp_path: Path):
    """Test that log_training_run logs artifacts correctly."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    # Create a test artifact
    artifact_path = tmp_path / "test_artifact.txt"
    artifact_path.write_text("Test artifact content")

    X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
    y_train = pd.Series([0, 1])

    model = LogisticRegression(max_iter=100)
    model.fit(X_train, y_train)

    run_id = log_training_run(
        model=model,
        params={"test_param": "value"},
        metrics={"test_metric": 0.9},
        metadata={},
        artifacts={"test_artifact": artifact_path},
        model_name="test_model_with_artifacts",
    )

    expect(run_id is not None, "Run ID should be returned")

    # Verify run was logged successfully
    run = mlflow.get_run(run_id)
    expect(run.data.params["test_param"] == "value", "Parameters should be logged")
    expect(run.data.metrics["test_metric"] == 0.9, "Metrics should be logged")


def test_train_lead_scoring_model_with_mlflow(mlflow_config: MLflowConfig, tmp_path: Path):
    """Test that train_lead_scoring_model logs to MLflow when enabled."""
    import os

    import mlflow

    # Set environment variables for the tracking configuration
    os.environ["MLFLOW_TRACKING_URI"] = mlflow_config.tracking_uri
    os.environ["MLFLOW_EXPERIMENT_NAME"] = mlflow_config.experiment_name

    init_mlflow(mlflow_config)

    dataset = _build_training_frame()
    result = train_lead_scoring_model(
        dataset,
        target_column="won",
        enable_mlflow=True,
        mlflow_model_name="test_lead_scoring",
    )

    expect(result.model is not None, "Model should be trained")
    expect("roc_auc" in result.metrics, "Metrics should include roc_auc")
    expect(result.metrics["roc_auc"] >= 0.0, "ROC AUC should be non-negative")

    # Verify that a run was logged
    experiment = mlflow.get_experiment_by_name(mlflow_config.experiment_name)
    runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])
    expect(len(runs) > 0, "At least one run should be logged")

    # Check that model was registered
    client = mlflow.MlflowClient()
    versions = client.search_model_versions("name='test_lead_scoring'")
    expect(len(versions) > 0, "Model should be registered")

    # Clean up environment
    os.environ.pop("MLFLOW_TRACKING_URI", None)
    os.environ.pop("MLFLOW_EXPERIMENT_NAME", None)


def test_train_lead_scoring_model_without_mlflow(tmp_path: Path):
    """Test that train_lead_scoring_model works when MLflow is disabled."""
    dataset = _build_training_frame()
    result = train_lead_scoring_model(
        dataset,
        target_column="won",
        enable_mlflow=False,
    )

    expect(result.model is not None, "Model should be trained without MLflow")
    expect("roc_auc" in result.metrics, "Metrics should be available")


def test_promote_model(mlflow_config: MLflowConfig):
    """Test model promotion to different stages."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    # Train and register a model
    X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
    y_train = pd.Series([0, 1])
    model = LogisticRegression(max_iter=100)
    model.fit(X_train, y_train)

    model_name = "promotion_test_model"
    log_training_run(
        model=model,
        params={},
        metrics={"test_metric": 0.9},
        metadata={},
        model_name=model_name,
    )

    # Get the version that was just registered
    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    expect(len(versions) > 0, "Model should be registered")
    version = versions[0].version

    # Promote to staging
    promote_model(
        model_name=model_name,
        version=version,
        stage=ModelStage.STAGING,
        archive_existing=False,
    )

    # Verify promotion
    model_version = client.get_model_version(model_name, version)
    expect(
        model_version.current_stage == "Staging",
        "Model should be in Staging stage",
    )


def test_promote_model_archives_existing(mlflow_config: MLflowConfig):
    """Test that promote_model archives existing models in the target stage."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
    y_train = pd.Series([0, 1])

    model_name = "archive_test_model"

    # Register and promote first model
    model1 = LogisticRegression(max_iter=100)
    model1.fit(X_train, y_train)
    log_training_run(
        model=model1,
        params={},
        metrics={"version": 1},
        metadata={},
        model_name=model_name,
    )

    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    version1 = versions[0].version

    promote_model(
        model_name=model_name,
        version=version1,
        stage=ModelStage.PRODUCTION,
    )

    # Register and promote second model
    model2 = LogisticRegression(max_iter=100)
    model2.fit(X_train, y_train)
    log_training_run(
        model=model2,
        params={},
        metrics={"version": 2},
        metadata={},
        model_name=model_name,
    )

    versions = client.search_model_versions(f"name='{model_name}'")
    version2 = max(int(v.version) for v in versions)

    promote_model(
        model_name=model_name,
        version=version2,
        stage=ModelStage.PRODUCTION,
        archive_existing=True,
    )

    # Verify first model is archived
    model_version1 = client.get_model_version(model_name, version1)
    expect(
        model_version1.current_stage == "Archived",
        "Previous production model should be archived",
    )

    # Verify second model is in production
    model_version2 = client.get_model_version(model_name, str(version2))
    expect(
        model_version2.current_stage == "Production",
        "New model should be in Production",
    )


def test_load_production_model(mlflow_config: MLflowConfig):
    """Test loading a model from production stage."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
    y_train = pd.Series([0, 1])
    model = LogisticRegression(max_iter=100)
    model.fit(X_train, y_train)

    model_name = "load_production_test"
    log_training_run(
        model=model,
        params={},
        metrics={},
        metadata={},
        model_name=model_name,
    )

    # Promote to production
    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    version = versions[0].version
    promote_model(
        model_name=model_name,
        version=version,
        stage=ModelStage.PRODUCTION,
    )

    # Load production model
    loaded_model = load_production_model(model_name)
    expect(loaded_model is not None, "Production model should be loaded")

    # Verify it makes predictions
    predictions = loaded_model.predict(X_train)
    expect(len(predictions) == len(X_train), "Model should make predictions")


def test_get_model_metadata(mlflow_config: MLflowConfig):
    """Test retrieving model metadata from registry."""
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
    y_train = pd.Series([0, 1])
    model = LogisticRegression(max_iter=100)
    model.fit(X_train, y_train)

    model_name = "metadata_test_model"
    log_training_run(
        model=model,
        params={},
        metrics={},
        metadata={},
        model_name=model_name,
    )

    # Get all metadata
    metadata_list = get_model_metadata(model_name)
    expect(len(metadata_list) > 0, "Should retrieve model metadata")
    expect("version" in metadata_list[0], "Metadata should include version")
    expect("stage" in metadata_list[0], "Metadata should include stage")
    expect("run_id" in metadata_list[0], "Metadata should include run_id")


def test_get_model_metadata_filtered_by_stage(mlflow_config: MLflowConfig):
    """Test retrieving model metadata filtered by stage."""
    import mlflow
    from sklearn.linear_model import LogisticRegression

    init_mlflow(mlflow_config)

    X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
    y_train = pd.Series([0, 1])
    model = LogisticRegression(max_iter=100)
    model.fit(X_train, y_train)

    model_name = "stage_filter_test_model"
    log_training_run(
        model=model,
        params={},
        metrics={},
        metadata={},
        model_name=model_name,
    )

    # Promote to staging
    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    version = versions[0].version
    promote_model(
        model_name=model_name,
        version=version,
        stage=ModelStage.STAGING,
    )

    # Get staging metadata
    staging_metadata = get_model_metadata(model_name, stage=ModelStage.STAGING)
    expect(len(staging_metadata) > 0, "Should retrieve staging model metadata")
    expect(
        staging_metadata[0]["stage"] == "Staging",
        "Retrieved model should be in Staging",
    )


def test_mlflow_integration_with_in_memory_sqlite(tmp_path: Path):
    """Test MLflow works with in-memory SQLite for testing."""
    import mlflow

    # Use in-memory SQLite database
    config = MLflowConfig(
        tracking_uri="sqlite:///",
        experiment_name="in_memory_test",
    )

    init_mlflow(config)

    experiment = mlflow.get_experiment_by_name(config.experiment_name)
    expect(experiment is not None, "Experiment should be created in-memory")
