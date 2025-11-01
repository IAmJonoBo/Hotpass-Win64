"""Configuration validation, migration, and autofix tooling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import IndustryProfile, get_default_profile
from .config_schema import HotpassConfig


@dataclass(slots=True)
class DiagnosticResult:
    """Result of a configuration diagnostic check."""

    check_name: str
    passed: bool
    message: str
    fix_suggestion: str | None = None
    severity: str = "info"

    def __repr__(self) -> str:  # pragma: no cover - convenience for debugging
        return (
            "DiagnosticResult("  # noqa: UP031 - multi-line readability
            f"check_name={self.check_name!r}, "
            f"passed={self.passed!r}, "
            f"severity={self.severity!r}, "
            f"message={self.message!r}"
            ")"
        )


class ConfigDoctor:
    """Diagnose, migrate, and autofix canonical configuration payloads."""

    def __init__(self, config: HotpassConfig | None = None):
        self.config: HotpassConfig = config or HotpassConfig()
        self.diagnostics: list[DiagnosticResult] = []

    def diagnose(self) -> list[DiagnosticResult]:
        """Run diagnostic checks across governance and pipeline settings."""

        self.diagnostics = []
        self._check_governance()
        self._check_pipeline_contract()
        return self.diagnostics

    def _check_governance(self) -> None:
        governance = self.config.governance
        if not governance.intent:
            self.diagnostics.append(
                DiagnosticResult(
                    "governance.intent",
                    False,
                    "No governance intent declared.",
                    "Populate governance.intent with the business objective for this run.",
                    "error",
                )
            )
        if not governance.data_owner.strip():
            self.diagnostics.append(
                DiagnosticResult(
                    "governance.data_owner",
                    False,
                    "Data owner is not specified.",
                    "Assign a data owner responsible for refinement outcomes.",
                    "error",
                )
            )
        else:
            self.diagnostics.append(
                DiagnosticResult(
                    "governance.data_owner",
                    True,
                    f"Data owner registered as '{governance.data_owner}'.",
                )
            )

    def _check_pipeline_contract(self) -> None:
        contract = self.config.data_contract
        self.diagnostics.append(
            DiagnosticResult(
                "data_contract.expectation_suite",
                bool(contract.expectation_suite),
                f"Expectation suite set to '{contract.expectation_suite}'.",
                ("Specify an expectation suite name." if not contract.expectation_suite else None),
                "error" if not contract.expectation_suite else "info",
            )
        )

    def get_summary(self) -> dict[str, Any]:
        """Return a roll-up summary of the most recent diagnostic run."""

        if not self.diagnostics:
            self.diagnose()
        total = len(self.diagnostics)
        passed = len([result for result in self.diagnostics if result.passed])
        failed = total - passed
        health = 0 if total == 0 else int((passed / total) * 100)
        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "health_score": health,
        }

    def autofix(self) -> bool:
        """Apply safe autofixes for missing governance metadata."""

        changes = False
        governance = self.config.governance
        if not governance.data_owner.strip():
            updated_governance = governance.model_copy(update={"data_owner": "Data Governance"})
            self.config = self.config.model_copy(update={"governance": updated_governance})
            changes = True
        if changes:
            self.diagnose()
        return changes

    def upgrade_payload(
        self, payload: Mapping[str, Any]
    ) -> tuple[HotpassConfig, list[DiagnosticResult]]:
        """Upgrade a legacy configuration payload to the canonical schema."""

        base = HotpassConfig()
        notices: list[DiagnosticResult] = []

        updates: dict[str, Any] = {}
        pipeline_updates: dict[str, Any] = {}

        if "input_dir" in payload:
            pipeline_updates["input_dir"] = Path(payload["input_dir"])
            notices.append(
                DiagnosticResult(
                    "legacy.input_dir",
                    True,
                    "Migrated deprecated 'input_dir' field to pipeline configuration.",
                )
            )
        if "output_path" in payload:
            pipeline_updates["output_path"] = Path(payload["output_path"])
        if "expectation_suite" in payload:
            pipeline_updates["expectation_suite"] = payload["expectation_suite"]
        if "country_code" in payload:
            pipeline_updates["country_code"] = payload["country_code"]
        if pipeline_updates:
            updates["pipeline"] = pipeline_updates

        if "features" in payload:
            updates["features"] = payload["features"]
            notices.append(
                DiagnosticResult(
                    "legacy.features",
                    True,
                    "Migrated legacy feature flags to canonical FeatureSwitches.",
                )
            )

        if "governance" in payload:
            updates["governance"] = payload["governance"]

        profile_payload = payload.get("profile")
        if profile_payload:
            try:
                profile = IndustryProfile.from_dict(profile_payload)
            except ValueError:
                profile = get_default_profile("generic")
                notices.append(
                    DiagnosticResult(
                        "legacy.profile",
                        False,
                        "Failed to parse legacy profile; defaulted to 'generic'.",
                        "Review profile payload for validity.",
                        "warning",
                    )
                )
            else:
                updates["profile"] = profile.to_dict()
                notices.append(
                    DiagnosticResult(
                        "legacy.profile",
                        True,
                        "Migrated legacy profile payload to canonical schema.",
                        severity="info",
                    )
                )

        if updates:
            config = base.merge(updates)
        else:
            config = base

        self.config = config
        return config, notices


__all__ = ["ConfigDoctor", "DiagnosticResult"]
