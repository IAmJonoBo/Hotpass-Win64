"""Hotpass data refinement pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.append(str(_PACKAGE_ROOT))

from . import _warning_filters as _warning_filters  # noqa: F401
from . import benchmarks
from .artifacts import create_refined_archive
from .column_mapping import ColumnMapper, infer_column_types, profile_dataframe
from .config import IndustryProfile, get_default_profile, load_industry_profile
from .config_doctor import ConfigDoctor, DiagnosticResult
from .contacts import Contact, OrganizationContacts, consolidate_contacts_from_rows
from .error_handling import ErrorHandler, ErrorReport, ErrorSeverity
from .formatting import OutputFormat, apply_excel_formatting, export_to_multiple_formats
from .pipeline import (
    PIIRedactionConfig,
    PipelineConfig,
    PipelineExecutionConfig,
    PipelineOrchestrator,
    PipelineResult,
    QualityReport,
    default_feature_bundle,
    run_pipeline,
)
from .pipeline_enhanced import EnhancedPipelineConfig, run_enhanced_pipeline

del _warning_filters

__all__ = [
    "benchmarks",
    "create_refined_archive",
    "PipelineConfig",
    "PipelineExecutionConfig",
    "PipelineResult",
    "QualityReport",
    "run_pipeline",
    "PipelineOrchestrator",
    "default_feature_bundle",
    "PIIRedactionConfig",
    "EnhancedPipelineConfig",
    "run_enhanced_pipeline",
    "ColumnMapper",
    "infer_column_types",
    "profile_dataframe",
    "IndustryProfile",
    "get_default_profile",
    "load_industry_profile",
    "ConfigDoctor",
    "DiagnosticResult",
    "Contact",
    "OrganizationContacts",
    "consolidate_contacts_from_rows",
    "ErrorHandler",
    "ErrorReport",
    "ErrorSeverity",
    "OutputFormat",
    "apply_excel_formatting",
    "export_to_multiple_formats",
]
