# ADR 0006: MLflow Lifecycle Strategy

## Status

Accepted

## Context

Hotpass includes lead scoring models to prioritise prospects based on quality signals, enrichment data, and intent. As these models evolve, we need a systematic approach to:

1. Track experiments and training runs with parameters, metrics, and artifacts
2. Version models and manage their deployment lifecycle
3. Promote models through stage gates (development → staging → production)
4. Enable rollback to previous versions when issues are detected
5. Maintain an audit trail of all model changes and promotions

The scoring module (`apps/data-platform/hotpass/transform/scoring.py`) contains training logic but lacks any tracking, versioning, or deployment management capabilities.

## Decision

We adopt **MLflow** as the unified platform for ML lifecycle management with the following architecture:

### Components

1. **Tracking Server**: Records all training runs, parameters, metrics, and artifacts
   - Default backend: SQLite (`sqlite:///mlflow.db`) for development
   - Production backend: PostgreSQL or cloud storage (S3, Azure Blob)
   - Configurable via `MLFLOW_TRACKING_URI` environment variable

2. **Model Registry**: Central repository for versioned models
   - Manages model versions with metadata and lineage
   - Enforces stage-based promotion workflow
   - Supports model aliases for stable references

3. **Stage Gates**: Four deployment stages with explicit promotion
   - **None**: Newly registered models (default)
   - **Staging**: Models undergoing validation
   - **Production**: Active models serving predictions
   - **Archived**: Retired or superseded models

### Integration Points

#### Training Integration

The `train_lead_scoring_model` function automatically logs to MLflow when `enable_mlflow=True`:

```python
result = train_lead_scoring_model(
    dataset,
    target_column="won",
    enable_mlflow=True,
    mlflow_model_name="lead_scoring_model",
)
```

Logged artifacts include:

- Trained sklearn model
- Training parameters (random_state, validation_size, solver config)
- Validation metrics (ROC AUC, precision, recall)
- Metadata (feature names, dataset size, training timestamp)
- Metrics JSON file

#### Promotion Workflow

Models follow a strict promotion path:

1. **Training** → Model registered with version number, stage=None
2. **Validation** → Promote to Staging for testing with production-like data
3. **Deployment** → Promote to Production, archiving previous production model
4. **Retirement** → Archive when superseded or deprecated

Promotion is explicit and programmatic:

```python
promote_model(
    model_name="lead_scoring_model",
    version=3,
    stage=ModelStage.PRODUCTION,
    archive_existing=True,
)
```

#### Inference Integration

Production models are loaded by stage reference, not version number:

```python
model = load_production_model("lead_scoring_model")
predictions = model.predict(features)
```

This allows seamless updates: promoting a new version to Production automatically redirects all inference calls.

### Configuration Strategy

MLflow configuration is hierarchical:

1. **Environment variables** (highest precedence):
   - `MLFLOW_TRACKING_URI`
   - `MLFLOW_EXPERIMENT_NAME`
   - `MLFLOW_REGISTRY_URI`
   - `MLFLOW_ARTIFACT_LOCATION`

2. **Programmatic config** via `MLflowConfig`:

   ```python
   config = MLflowConfig(
       tracking_uri="sqlite:///mlflow.db",
       experiment_name="lead_scoring",
   )
   init_mlflow(config)
   ```

3. **Defaults**:
   - Tracking URI: `sqlite:///mlflow.db`
   - Experiment name: `lead_scoring`

### Graceful Degradation

MLflow is optional:

- Training succeeds even if MLflow is unavailable
- `enable_mlflow=False` bypasses tracking entirely
- Import errors are caught and logged, not fatal
- Tests mock MLflow when it's not installed

This preserves existing workflows while enabling progressive adoption.

## Consequences

### Positive

- **Reproducibility**: Every training run is recorded with full parameters and code version
- **Traceability**: Complete audit trail from training data to production deployment
- **Rollback**: Previous model versions remain available for instant rollback
- **Collaboration**: Team members can review all experiments in a shared registry
- **Automation**: Promotion workflow can be automated via CI/CD pipelines
- **Observability**: Metrics and artifacts are centrally stored and queryable
- **Flexibility**: SQLite for local dev, production DB for scale

### Negative

- **Dependency**: Adds MLflow (and its transitive deps) to the ml_scoring extra
- **Complexity**: Developers must learn MLflow concepts and APIs
- **State Management**: Registry state (DB, artifacts) must be backed up and versioned
- **Migration Risk**: Changing backends requires data migration planning

### Mitigation

- **Training**: Comprehensive how-to guide (`docs/how-to-guides/model-lifecycle-mlflow.md`)
- **Testing**: Full test coverage (86%) with in-memory SQLite for CI/CD
- **Gradual Adoption**: MLflow is opt-in via `enable_mlflow` flag
- **Backup**: Document backup and restore procedures for tracking DB
- **Monitoring**: Alert on registry errors or tracking failures

## Alternatives Considered

### 1. DVC (Data Version Control)

**Pros**:

- Git-like interface familiar to developers
- Strong data versioning capabilities
- Already adopted for dataset versioning

**Cons**:

- No built-in experiment tracking or metrics logging
- Limited model registry features
- Requires separate tool for serving models

**Decision**: DVC is retained for **data** versioning; MLflow handles **model** lifecycle.

### 2. Weights & Biases (W&B)

**Pros**:

- Excellent visualisation and collaboration features
- Native integrations with popular ML frameworks
- Hosted service reduces operational burden

**Cons**:

- Cloud dependency (data leaves premises)
- Licensing costs for team use
- Less control over artifact storage

**Decision**: Rejected due to data sovereignty and cost concerns.

### 3. Custom Registry (Database + S3)

**Pros**:

- Full control over storage and schema
- No external dependencies
- Tailored to specific needs

**Cons**:

- High development and maintenance cost
- Reinventing standard tooling
- Lack of UI and visualisation tools

**Decision**: Not worth the engineering investment.

### 4. Manual Git Tagging

**Pros**:

- Zero additional dependencies
- Simple and auditable

**Cons**:

- No structured metadata or metrics
- No experiment comparison
- Difficult to query or automate

**Decision**: Insufficient for production ML workflows.

## Implementation Notes

### Module Structure

```
apps/data-platform/hotpass/ml/
├── __init__.py          # Public API exports
└── tracking.py          # MLflow integration
```

### Key Functions

- `init_mlflow(config)`: Initialise tracking server and experiment
- `log_training_run(...)`: Log model with params, metrics, artifacts
- `promote_model(...)`: Transition model version to target stage
- `load_production_model(name)`: Load active production model
- `get_model_metadata(name, stage)`: Query registry for model versions

### Environment Setup

Development:

```bash
export MLFLOW_TRACKING_URI="sqlite:///mlflow.db"
uv run mlflow ui
```

Production (example):

```bash
export MLFLOW_TRACKING_URI="postgresql://<user>:<password>@db:5432/mlflow"
export MLFLOW_ARTIFACT_LOCATION="s3://hotpass-mlflow-artifacts/"
```

### Testing Strategy

- **Unit tests**: Mock MLflow client for fast, isolated tests
- **Integration tests**: Use in-memory SQLite (`sqlite:///`) for full workflow validation
- **Coverage target**: 85% minimum (achieved 86%)

### Monitoring and Alerts

Track these metrics in production:

- Model registration rate (new versions per day)
- Promotion frequency (staging → production)
- Inference latency per model version
- Prediction distribution drift
- Registry errors or unavailable models

## Roadmap Integration

This ADR satisfies **Phase 4, Task T4.1** of the Hotpass roadmap:

> If model training exists or is planned, run MLflow Tracking with a DB backend; log code, params, metrics, and artefacts. Create a Model Registry with stage gates ("Staging" → "Production"); document promotion policy.

Acceptance criteria met:

- [x] MLflow Tracking operational with SQLite backend
- [x] Model Registry with stage gates implemented
- [x] Promotion workflow documented in how-to guide
- [x] ADR committed describing the lifecycle policy
- [x] Tests validate tracking and promotion with in-memory DB

## References

- [MLflow Documentation](https://www.mlflow.org/docs/latest/index.html)
- [Model Registry Concepts](https://www.mlflow.org/docs/latest/model-registry.html)
- [How-to: Model Lifecycle and Promotion](../how-to-guides/model-lifecycle-mlflow.md)
- [Roadmap Phase 4](../roadmap.md#phase-4--ml-lifecycle-conditional)

## Revision History

- **2025-10-28**: Initial version (accepted)
