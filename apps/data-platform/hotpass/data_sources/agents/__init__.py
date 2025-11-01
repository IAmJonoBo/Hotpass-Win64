"""Agent-based acquisition framework for Hotpass."""

from .base import AcquisitionAgent, AgentContext, AgentResult, normalise_records
from .config import (
    AcquisitionPlan,
    AgentDefinition,
    AgentTaskDefinition,
    AgentTaskKind,
    ProviderDefinition,
    TargetDefinition,
)
from .runner import AcquisitionManager, run_plan

__all__ = [
    "AcquisitionAgent",
    "AcquisitionManager",
    "AcquisitionPlan",
    "AgentContext",
    "AgentDefinition",
    "AgentTaskDefinition",
    "AgentTaskKind",
    "AgentResult",
    "ProviderDefinition",
    "TargetDefinition",
    "normalise_records",
    "run_plan",
]
