"""Lead scoring helpers used to prioritise enriched contacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from hotpass.enrichment.validators import logistic_scale

DEFAULT_WEIGHTS: Mapping[str, float] = {
    "completeness": 0.3,
    "email_confidence": 0.25,
    "phone_confidence": 0.15,
    "source_priority": 0.2,
    "intent": 0.1,
}


@dataclass(slots=True)
class LeadScore:
    """Lead score enriched with contributing components."""

    value: float
    components: Mapping[str, float]


class LeadScorer:
    """Combine quality signals into a normalised lead score."""

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        if not self.weights:
            raise ValueError("weights must contain at least one entry")

    def _normalise(self, components: Mapping[str, float]) -> float:
        weighted = 0.0
        total_weight = 0.0
        for key, raw_value in components.items():
            weight = self.weights.get(key, 0.0)
            if weight <= 0:
                continue
            total_weight += weight
            weighted += weight * max(0.0, min(1.0, raw_value))
        if total_weight == 0:
            return 0.0
        return weighted / total_weight

    def score(
        self,
        *,
        completeness: float,
        email_confidence: float,
        phone_confidence: float,
        source_priority: float,
        intent_score: float = 0.0,
    ) -> LeadScore:
        components = {
            "completeness": completeness,
            "email_confidence": email_confidence,
            "phone_confidence": phone_confidence,
            "source_priority": source_priority,
            "intent": intent_score,
        }
        normalised = self._normalise(components)
        scaled = logistic_scale(normalised)
        return LeadScore(value=scaled, components=components)


@dataclass(slots=True)
class LeadScoringModel:
    """Persistable estimator for prospect prioritisation."""

    estimator: Any
    feature_names: tuple[str, ...]
    trained_at: datetime

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        missing = [name for name in self.feature_names if name not in frame.columns]
        if missing:
            missing_str = ", ".join(missing)
            msg = f"Missing feature columns for lead scoring: {missing_str}"
            raise ValueError(msg)
        values = frame[list(self.feature_names)].fillna(0.0)
        probabilities = self.estimator.predict_proba(values)[:, 1]
        series = pd.Series(probabilities, index=values.index, dtype="float64")
        return series.clip(0.0, 1.0)


@dataclass(slots=True)
class LeadScoringTrainingResult:
    """Container for a trained model alongside evaluation artefacts."""

    model: LeadScoringModel
    metrics: dict[str, float]
    metadata: dict[str, Any]


DEFAULT_METRICS_PATH = Path("dist/metrics/lead_scoring.json")


def train_lead_scoring_model(
    dataset: pd.DataFrame,
    *,
    target_column: str,
    feature_columns: Sequence[str] | None = None,
    random_state: int = 7,
    validation_size: float = 0.2,
    metric_thresholds: Mapping[str, float] | None = None,
    metrics_path: Path | None = None,
    enable_mlflow: bool = True,
    mlflow_model_name: str = "lead_scoring_model",
) -> LeadScoringTrainingResult:
    """
    Train a logistic regression model and evaluate it on a validation split.

    Optionally logs the training run to MLflow if enable_mlflow=True and MLflow is available.
    """

    try:  # pragma: no cover - dependency import guarded at runtime
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import precision_score, recall_score, roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:  # pragma: no cover - informative error
        msg = (
            "scikit-learn is required to train lead scoring models. Install the"
            " 'ml_scoring' extra (pip install hotpass[ml_scoring])."
        )
        raise RuntimeError(msg) from exc

    if target_column not in dataset.columns:
        msg = f"Target column '{target_column}' not present in dataset"
        raise ValueError(msg)

    default_features = (
        "completeness",
        "email_confidence",
        "phone_confidence",
        "source_priority",
        "intent_signal_score",
    )
    candidate_features = tuple(feature_columns) if feature_columns else default_features
    usable = [name for name in candidate_features if name in dataset.columns]
    if not usable:
        msg = "No usable feature columns available for lead scoring"
        raise ValueError(msg)

    if validation_size <= 0 or validation_size >= 1:
        msg = "validation_size must be between 0 and 1"
        raise ValueError(msg)

    training_frame = dataset[list(usable) + [target_column]].dropna()
    if training_frame.empty:
        msg = "Training dataset is empty after dropping null values"
        raise ValueError(msg)
    if len(training_frame) < 2:
        msg = "At least two samples are required to train a model"
        raise ValueError(msg)

    X = training_frame[list(usable)].astype("float64")
    y = training_frame[target_column].astype("int64")

    stratify = y if y.nunique() > 1 else None
    X_train, X_valid, y_train, y_valid = train_test_split(
        X,
        y,
        test_size=validation_size,
        random_state=random_state,
        stratify=stratify,
    )

    estimator = LogisticRegression(max_iter=1000, solver="lbfgs", random_state=random_state)
    estimator.fit(X_train, y_train)

    validation_probabilities = estimator.predict_proba(X_valid)[:, 1]
    try:
        roc_auc = float(roc_auc_score(y_valid, validation_probabilities))
    except ValueError:
        roc_auc = 0.0
    predictions = (validation_probabilities >= 0.5).astype(int)
    precision = float(precision_score(y_valid, predictions, zero_division=0))
    recall = float(recall_score(y_valid, predictions, zero_division=0))

    metrics = {
        "roc_auc": roc_auc,
        "precision": precision,
        "recall": recall,
    }

    trained_at = datetime.now(tz=UTC)
    metadata: dict[str, Any] = {
        "target_column": target_column,
        "feature_names": tuple(usable),
        "random_state": random_state,
        "trained_at": trained_at.isoformat(),
        "dataset_rows": int(len(training_frame)),
        "train_rows": int(len(X_train)),
        "validation_rows": int(len(X_valid)),
        "validation_size": validation_size,
    }

    destination = metrics_path or DEFAULT_METRICS_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    serializable_metadata = dict(metadata)
    serializable_metadata["feature_names"] = list(metadata["feature_names"])
    payload = {"metrics": metrics, "metadata": serializable_metadata}
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if metric_thresholds:
        failures = {
            name: threshold
            for name, threshold in metric_thresholds.items()
            if metrics.get(name, 0.0) < threshold
        }
        if failures:
            details = ", ".join(
                f"{metric}={metrics.get(metric, 0.0):.3f} < {threshold:.3f}"
                for metric, threshold in failures.items()
            )
            msg = f"Validation metrics below required thresholds: {details}"
            raise RuntimeError(msg)

    model = LeadScoringModel(
        estimator=estimator,
        feature_names=tuple(usable),
        trained_at=trained_at,
    )

    # Log to MLflow if enabled and available
    if enable_mlflow:
        try:
            from hotpass.ml.tracking import init_mlflow, log_training_run

            init_mlflow()

            # Prepare parameters for logging
            params = {
                "target_column": target_column,
                "random_state": random_state,
                "validation_size": validation_size,
                "max_iter": 1000,
                "solver": "lbfgs",
            }

            # Prepare artifacts
            artifacts = {}
            if destination.exists():
                artifacts["metrics"] = destination

            # Create input example from validation set
            input_example = X_valid.head(5) if len(X_valid) >= 5 else X_valid

            log_training_run(
                model=estimator,
                params=params,
                metrics=metrics,
                metadata=metadata,
                artifacts=artifacts,
                model_name=mlflow_model_name,
                input_example=input_example,
            )
        except (ImportError, RuntimeError):
            # MLflow not available or initialization failed - continue without tracking
            pass

    return LeadScoringTrainingResult(model=model, metrics=metrics, metadata=metadata)


def score_prospects(model: LeadScoringModel, frame: pd.DataFrame) -> pd.DataFrame:
    """Attach lead score predictions using the supplied model."""

    scores = model.predict(frame)
    calibrated = scores.apply(logistic_scale)
    result = frame.copy()
    result["lead_score"] = calibrated
    return result


def build_daily_list(
    *,
    refined_df: pd.DataFrame,
    intent_digest: pd.DataFrame | None,
    model: LeadScoringModel | None = None,
    top_n: int = 50,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Generate a ranked prospect list combining refined data and intent signals."""

    if refined_df.empty:
        return pd.DataFrame(
            columns=[
                "organization_name",
                "organization_slug",
                "lead_score",
                "intent_signal_score",
                "intent_signal_count",
                "intent_last_observed_at",
                "intent_top_insights",
            ]
        )

    working = refined_df.copy()
    if model is not None:
        feature_frame = working.set_index("organization_slug", drop=False)
        feature_subset = feature_frame[list(model.feature_names)]
        prediction_series = model.predict(feature_subset)
        ordered_predictions = prediction_series.reindex(
            feature_frame["organization_slug"],
        ).fillna(0.0)
        working["lead_score"] = ordered_predictions.to_numpy()
    else:
        base_score = working.get("contact_primary_lead_score")
        if base_score is None:
            base_score = pd.Series(0.0, index=working.index)
        working["lead_score"] = base_score.fillna(0.0).apply(logistic_scale)

    digest = intent_digest if intent_digest is not None else pd.DataFrame()
    if not digest.empty:
        digest_subset = digest[
            [
                "target_slug",
                "intent_signal_score",
                "intent_signal_count",
                "intent_last_observed_at",
                "intent_top_insights",
            ]
        ].copy()
        digest_subset.rename(columns={"target_slug": "organization_slug"}, inplace=True)
        working = working.merge(digest_subset, on="organization_slug", how="left")
    else:
        working["intent_signal_score"] = working.get("intent_signal_score", 0.0)
        working["intent_signal_count"] = working.get("intent_signal_count", 0)
        working["intent_last_observed_at"] = working.get("intent_last_observed_at")
        working["intent_top_insights"] = working.get("intent_top_insights")

    columns = [
        "organization_name",
        "organization_slug",
        "lead_score",
        "intent_signal_score",
        "intent_signal_count",
        "intent_last_observed_at",
        "intent_top_insights",
    ]
    available = [column for column in columns if column in working.columns]
    ranked = (
        working[available]
        .sort_values("lead_score", ascending=False)
        .drop_duplicates(subset="organization_slug", keep="first")
        .head(top_n)
        .reset_index(drop=True)
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = output_path.suffix.lower()
        if suffix == ".parquet":
            ranked.to_parquet(output_path, index=False)
        elif suffix in {".csv", ".tsv"}:
            sep = "\t" if suffix == ".tsv" else ","
            ranked.to_csv(output_path, index=False, sep=sep)
        else:
            ranked.to_json(output_path, orient="records", indent=2)

    return ranked


__all__ = [
    "LeadScore",
    "LeadScorer",
    "LeadScoringModel",
    "build_daily_list",
    "score_prospects",
    "train_lead_scoring_model",
]
