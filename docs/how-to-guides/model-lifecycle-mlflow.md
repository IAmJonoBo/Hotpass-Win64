# Model Lifecycle and Promotion with MLflow

This guide explains how to train, track, evaluate, and promote lead scoring models using MLflow's tracking server and model registry.

## Overview

Hotpass uses MLflow to manage the machine learning lifecycle for lead scoring models:

- **Tracking Server**: Records training runs, parameters, metrics, and artifacts
- **Model Registry**: Manages model versions and deployment stages
- **Stage Gates**: Controls promotion from development → staging → production

## Prerequisites

Install the ML scoring dependencies:

```bash
uv sync --extra ml_scoring
```

## Configuration

MLflow can be configured via environment variables or programmatically:

### Environment Variables

```bash
# SQLite backend (default for local development)
export MLFLOW_TRACKING_URI="sqlite:///mlflow.db"
export MLFLOW_EXPERIMENT_NAME="lead_scoring"

# Remote tracking server (production)
export MLFLOW_TRACKING_URI="http://mlflow-server:5000"
export MLFLOW_REGISTRY_URI="http://mlflow-server:5000"
```

### Programmatic Configuration

```python
from hotpass.ml import MLflowConfig, init_mlflow

config = MLflowConfig(
    tracking_uri="sqlite:///mlflow.db",
    experiment_name="lead_scoring",
)
init_mlflow(config)
```

## Training and Logging Models

### Basic Training with MLflow

The `train_lead_scoring_model` function automatically logs to MLflow when enabled:

```python
from hotpass.transform.scoring import train_lead_scoring_model
import pandas as pd

# Prepare training data
dataset = pd.DataFrame({
    "completeness": [0.9, 0.4, 0.75, 0.3],
    "email_confidence": [0.8, 0.1, 0.6, 0.2],
    "phone_confidence": [0.7, 0.0, 0.4, 0.2],
    "source_priority": [1.0, 0.2, 0.6, 0.1],
    "intent_signal_score": [0.9, 0.3, 0.5, 0.2],
    "won": [1, 0, 1, 0],  # Target variable
})

# Train model with MLflow tracking
result = train_lead_scoring_model(
    dataset,
    target_column="won",
    enable_mlflow=True,
    mlflow_model_name="lead_scoring_model",
)

print(f"ROC AUC: {result.metrics['roc_auc']:.3f}")
print(f"Precision: {result.metrics['precision']:.3f}")
print(f"Recall: {result.metrics['recall']:.3f}")
```

### Manual Logging

For custom training workflows, use the `log_training_run` function:

```python
from hotpass.ml import init_mlflow, log_training_run
from sklearn.linear_model import LogisticRegression
import pandas as pd

# Initialize MLflow
init_mlflow()

# Train your model
X_train = pd.DataFrame({"feature1": [0.1, 0.2], "feature2": [0.5, 0.6]})
y_train = pd.Series([0, 1])
model = LogisticRegression()
model.fit(X_train, y_train)

# Log to MLflow
run_id = log_training_run(
    model=model,
    params={"max_iter": 1000, "solver": "lbfgs"},
    metrics={"accuracy": 0.95, "precision": 0.92},
    metadata={"dataset": "contacts_2025", "features": ["feature1", "feature2"]},
    model_name="custom_lead_scorer",
    input_example=X_train.head(5),
)

print(f"Logged run: {run_id}")
```

## Model Registry and Promotion

### Stage Definitions

The model registry uses four stages:

- **None**: Newly registered models (default)
- **Staging**: Models being tested before production
- **Production**: Active models serving predictions
- **Archived**: Retired or superseded models

### Promoting Models to Staging

After training and validation, promote a model to staging:

```python
from hotpass.ml import promote_model, ModelStage

# Promote version 3 to staging
promote_model(
    model_name="lead_scoring_model",
    version=3,
    stage=ModelStage.STAGING,
    archive_existing=False,
)
```

### Promoting Models to Production

Once validated in staging, promote to production:

```python
from hotpass.ml import promote_model, ModelStage

# Promote version 3 to production, archiving any existing production models
promote_model(
    model_name="lead_scoring_model",
    version=3,
    stage=ModelStage.PRODUCTION,
    archive_existing=True,  # Archive previous production model
)
```

### Promoting Latest Version

Use `"latest"` to promote the most recent model version:

```python
promote_model(
    model_name="lead_scoring_model",
    version="latest",
    stage=ModelStage.PRODUCTION,
    archive_existing=True,
)
```

## Loading Models for Inference

### Load Production Model

```python
from hotpass.ml import load_production_model
import pandas as pd

# Load the current production model
model = load_production_model("lead_scoring_model")

# Make predictions
features = pd.DataFrame({
    "completeness": [0.85],
    "email_confidence": [0.75],
    "phone_confidence": [0.65],
    "source_priority": [0.9],
    "intent_signal_score": [0.7],
})

probabilities = model.predict_proba(features)[:, 1]
print(f"Lead score: {probabilities[0]:.3f}")
```

### Load Specific Version

```python
import mlflow

model = mlflow.sklearn.load_model("models:/lead_scoring_model/3")
```

## Inspecting Model Metadata

### List All Model Versions

```python
from hotpass.ml import get_model_metadata

metadata = get_model_metadata("lead_scoring_model")
for version_info in metadata:
    print(f"Version {version_info['version']}: {version_info['stage']}")
```

### Filter by Stage

```python
from hotpass.ml import get_model_metadata, ModelStage

# Get only production models
production_models = get_model_metadata(
    "lead_scoring_model",
    stage=ModelStage.PRODUCTION
)

for model in production_models:
    print(f"Production version: {model['version']}")
    print(f"Run ID: {model['run_id']}")
```

## Promotion Workflow Example

Complete workflow from training to production:

```python
from hotpass.ml import init_mlflow, promote_model, ModelStage, get_model_metadata
from hotpass.transform.scoring import train_lead_scoring_model
import pandas as pd

# 1. Initialize MLflow
init_mlflow()

# 2. Train model
dataset = pd.read_parquet("training_data.parquet")
result = train_lead_scoring_model(
    dataset,
    target_column="won",
    enable_mlflow=True,
    metric_thresholds={"roc_auc": 0.7, "precision": 0.6},
)

# 3. Get the model version that was just registered
metadata = get_model_metadata("lead_scoring_model")
latest_version = max(int(m['version']) for m in metadata)

# 4. Promote to staging for validation
promote_model(
    model_name="lead_scoring_model",
    version=latest_version,
    stage=ModelStage.STAGING,
)

print(f"Model version {latest_version} promoted to Staging")
print("Validate model performance before promoting to Production")

# 5. After validation, promote to production
# promote_model(
#     model_name="lead_scoring_model",
#     version=latest_version,
#     stage=ModelStage.PRODUCTION,
#     archive_existing=True,
# )
```

## MLflow UI

View tracking runs and model registry through the MLflow UI:

```bash
# Start MLflow UI (local development)
mlflow ui --backend-store-uri sqlite:///mlflow.db

# Access at http://localhost:5000
```

## Best Practices

### Training

- Always set meaningful `run_name` values for traceability
- Log comprehensive metadata (dataset version, feature names, training date)
- Include input examples for automatic signature inference
- Set metric thresholds to prevent deploying underperforming models

### Promotion

- Never promote directly to production without staging validation
- Archive existing production models to maintain rollback capability
- Document promotion decisions in run tags or comments
- Test staged models with production-like data before final promotion

### Monitoring

- Regularly review model performance metrics in production
- Set up alerts for metric degradation
- Maintain audit trail of all promotions and demotions
- Track model lineage from training data to deployment

## Troubleshooting

### Missing MLflow Module

If you see `ImportError: mlflow`, install the ml_scoring extra:

```bash
uv sync --extra ml_scoring
```

### Database Locked Errors

SQLite databases can experience locks under concurrent access. For production, use a proper database backend:

```bash
export MLFLOW_TRACKING_URI="postgresql://user:<password>@host:5432/mlflow"
```

### Model Not Found

Ensure you're using the correct model name and that the model has been registered:

```python
from hotpass.ml import get_model_metadata

# List all registered models
import mlflow
client = mlflow.MlflowClient()
for rm in client.search_registered_models():
    print(f"Model: {rm.name}")
```

## Integration with Pipeline

To integrate MLflow tracking with the full pipeline, set environment variables before running:

```bash
export MLFLOW_TRACKING_URI="sqlite:///mlflow.db"
export MLFLOW_EXPERIMENT_NAME="hotpass_pipeline"

uv run hotpass refine \
  --input-dir ./data \
  --output-path ./dist/refined.xlsx \
  --profile generic \
  --archive
```

## See Also

- [Configure Pipeline](configure-pipeline.md) - Pipeline configuration options
- [Orchestrate and Observe](orchestrate-and-observe.md) - Prefect orchestration
- [Architecture: MLflow Lifecycle Strategy](../adr/0006-mlflow-lifecycle-strategy.md) - ADR documenting design decisions
