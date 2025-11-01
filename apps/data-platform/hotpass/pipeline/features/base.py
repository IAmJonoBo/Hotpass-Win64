"""Base contracts for pipeline features."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from typing import Protocol

from ...observability import PipelineMetrics
from ..base import PipelineConfig, PipelineResult
from .config import EnhancedPipelineConfig

TraceFactory = Callable[[str], AbstractContextManager[object]]


@dataclass(slots=True)
class FeatureContext:
    """Execution context shared with feature strategies."""

    base_config: PipelineConfig
    enhanced_config: EnhancedPipelineConfig
    trace_factory: TraceFactory = field(default_factory=lambda: (lambda _name: nullcontext()))
    metrics: PipelineMetrics | None = None


class PipelineFeatureStrategy(Protocol):
    """Contract for optional feature hooks executed after the base pipeline."""

    name: str

    def is_enabled(self, context: FeatureContext) -> bool:
        """Return ``True`` when the feature should be applied."""

    def apply(self, result: PipelineResult, context: FeatureContext) -> PipelineResult:
        """Apply the feature to the pipeline result and return the updated value."""


def default_trace_factory(enabled: bool) -> TraceFactory:
    """Return a trace factory that emits spans only when observability is enabled."""

    if not enabled:
        return lambda _name: nullcontext()

    from ...observability import trace_operation  # Local import to avoid cycles

    def factory(operation: str) -> AbstractContextManager[object]:
        return trace_operation(operation)

    return factory


def ensure_feature_sequence(
    features: Sequence[PipelineFeatureStrategy] | None,
) -> tuple[PipelineFeatureStrategy, ...]:
    """Normalise optional feature sequences."""

    if not features:
        return ()
    return tuple(features)
