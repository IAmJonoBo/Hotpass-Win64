"""Regression tests for the canonical configuration doctor."""

from __future__ import annotations

from pathlib import Path

from hotpass.compliance import DataClassification
from hotpass.config import get_default_profile
from hotpass.config_doctor import ConfigDoctor, DiagnosticResult
from hotpass.config_schema import GovernanceMetadata, HotpassConfig, PipelineRuntimeConfig


def _make_config(tmp_path: Path) -> HotpassConfig:
    input_dir = tmp_path / "input"
    output_path = tmp_path / "dist" / "refined.xlsx"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    return HotpassConfig(
        pipeline=PipelineRuntimeConfig(
            input_dir=input_dir,
            output_path=output_path,
        ),
        governance=GovernanceMetadata(
            intent=["Baseline refinement"],
            data_owner="Data",  # Satisfy validation
            classification=DataClassification.INTERNAL,
        ),
    )


def test_config_doctor_diagnose_flags_missing_governance(tmp_path: Path) -> None:
    """Missing governance metadata should be reported as errors."""

    config = _make_config(tmp_path)
    config = config.model_copy(
        update={
            "governance": GovernanceMetadata(
                intent=["Baseline refinement"],
                data_owner="",
                classification=DataClassification.INTERNAL,
            )
        }
    )

    doctor = ConfigDoctor(config=config)
    results = doctor.diagnose()

    assert any(r.check_name == "governance.data_owner" and not r.passed for r in results)


def test_config_doctor_autofix_injects_governance_defaults(tmp_path: Path) -> None:
    """Autofix should patch missing governance metadata when possible."""

    config = _make_config(tmp_path).model_copy(
        update={
            "governance": GovernanceMetadata(
                intent=["Baseline refinement"],
                data_owner="",
                classification=DataClassification.INTERNAL,
            ),
        }
    )

    doctor = ConfigDoctor(config=config)
    assert doctor.autofix() is True

    summary = doctor.get_summary()
    assert summary["passed"] >= summary["failed"]
    assert doctor.config.governance.data_owner == "Data Governance"


def test_config_doctor_upgrade_from_legacy_payload(tmp_path: Path) -> None:
    """Legacy payloads should be converted into canonical Hotpass configs."""

    legacy_payload = {
        "input_dir": str(tmp_path),
        "output_path": str(tmp_path / "dist" / "refined.xlsx"),
        "expectation_suite": "default",
        "country_code": "ZA",
        "profile": get_default_profile("aviation").to_dict(),
        "features": {"compliance": True},
        "governance": {
            "intent": ["Process regulated data"],
            "data_owner": "Data Governance",
        },
    }

    doctor = ConfigDoctor()
    config, notices = doctor.upgrade_payload(legacy_payload)

    assert isinstance(config, HotpassConfig)
    assert config.pipeline.expectation_suite == "default"
    assert config.features.compliance is True
    assert any("deprecated" in notice.message for notice in notices)


def test_config_doctor_diagnostic_result_repr() -> None:
    """Ensure diagnostic results remain human readable."""

    result = DiagnosticResult(
        check_name="test",
        passed=False,
        message="example",
        fix_suggestion="fix it",
        severity="warning",
    )

    assert "test" in repr(result)
    assert "warning" in repr(result)
