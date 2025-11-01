"""Machine learning components for lead scoring and model lifecycle management."""

from __future__ import annotations

__all__ = [
    "MLflowConfig",
    "init_mlflow",
    "log_training_run",
    "promote_model",
    "ModelStage",
]

try:
    from hotpass.ml.tracking import (
        MLflowConfig,
        ModelStage,
        init_mlflow,
        log_training_run,
        promote_model,
    )
except ImportError:  # pragma: no cover
    # MLflow is optional; gracefully handle missing dependency
    pass
