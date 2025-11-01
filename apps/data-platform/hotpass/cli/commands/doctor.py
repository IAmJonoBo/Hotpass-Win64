from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from hotpass.config import load_industry_profile
from hotpass.config_doctor import ConfigDoctor, DiagnosticResult
from hotpass.config_schema import HotpassConfig

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..shared import load_config

MIN_PYTHON_VERSION = (3, 10)


@dataclass(slots=True)
class DoctorReport:
    """Structured report emitted after running the doctor command."""

    environment: list[DiagnosticResult]
    configuration: list[DiagnosticResult]
    summary: dict[str, int]


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "doctor",
        help="Run configuration and environment diagnostics",
        description=(
            "Inspect your workspace for common configuration issues and missing "
            "directories. The command reuses ConfigDoctor checks and adds "
            "environment validation such as Python version, input/output paths, "
            "and dist directory readiness."
        ),
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--autofix",
        action="store_true",
        help="Apply safe autofixes (governance defaults) before reporting diagnostics",
    )
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="doctor",
        help="Run configuration and environment diagnostics",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    try:
        config = _resolve_config(namespace, profile)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    doctor = ConfigDoctor(config=config)

    if getattr(namespace, "autofix", False):
        if doctor.autofix():
            print("Applied governance autofixes.")

    config_results = doctor.diagnose()
    environment_results = _environment_checks(doctor.config)
    summary = doctor.get_summary()

    report = DoctorReport(
        environment=environment_results,
        configuration=config_results,
        summary={
            "total_checks": summary["total_checks"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "health_score": summary["health_score"],
        },
    )
    _render_report(report)

    failures = [
        result
        for result in (*report.environment, *report.configuration)
        if not result.passed and result.severity == "error"
    ]
    return 0 if not failures else 1


def _resolve_config(namespace: argparse.Namespace, profile: CLIProfile | None) -> HotpassConfig:
    config = HotpassConfig()

    config_paths: list[Path] = []
    if profile is not None:
        config = profile.apply_to_config(config)
        config_paths.extend(profile.resolved_config_files())
        if profile.industry_profile:
            industry = load_industry_profile(profile.industry_profile)
            config = config.merge({"profile": industry.to_dict()})

    cli_config_paths = getattr(namespace, "config_paths", None)
    if cli_config_paths:
        config_paths.extend(Path(path) for path in cli_config_paths)

    for path in config_paths:
        candidate = Path(path)
        if not candidate.exists():
            msg = f"Configuration file not found: {candidate}"
            raise FileNotFoundError(msg)
        payload = load_config(candidate)
        config = config.merge(payload)

    return config


def _environment_checks(config: HotpassConfig) -> list[DiagnosticResult]:
    results: list[DiagnosticResult] = []

    version_ok = sys.version_info >= MIN_PYTHON_VERSION
    version_message = f"Python {sys.version_info.major}.{sys.version_info.minor} detected"
    version_fix = None
    if not version_ok:
        version_fix = f"Upgrade to Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or newer."
    results.append(
        DiagnosticResult(
            "environment.python_version",
            version_ok,
            version_message,
            version_fix,
            "error" if not version_ok else "info",
        )
    )

    input_dir = config.pipeline.input_dir
    if input_dir.exists() and input_dir.is_dir():
        has_files = any(input_dir.iterdir())
        message = (
            f"Input directory ready: {input_dir}"
            if has_files
            else f"Input directory exists but is empty: {input_dir}"
        )
        severity = "warning" if not has_files else "info"
        results.append(
            DiagnosticResult(
                "environment.input_dir",
                True,
                message,
                None,
                severity,
            )
        )
    else:
        results.append(
            DiagnosticResult(
                "environment.input_dir",
                False,
                f"Input directory missing: {input_dir}",
                "Create the input directory or point --input-dir to an existing location.",
                "error",
            )
        )

    output_parent = config.pipeline.output_path.parent
    if output_parent.exists():
        results.append(
            DiagnosticResult(
                "environment.output_parent",
                True,
                f"Output directory available: {output_parent}",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                "environment.output_parent",
                False,
                f"Output directory missing: {output_parent}",
                "Create the directory or update --output-path.",
                "error",
            )
        )

    dist_dir = config.pipeline.dist_dir
    if dist_dir.exists():
        results.append(
            DiagnosticResult(
                "environment.dist_dir",
                True,
                f"Distribution directory ready: {dist_dir}",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                "environment.dist_dir",
                False,
                f"Distribution directory missing: {dist_dir}",
                "Create the directory to capture archives and quality reports.",
                "warning",
            )
        )

    return results


def _render_report(report: DoctorReport) -> None:
    print("Environment diagnostics")
    _render_results(report.environment)
    print()
    print("Configuration diagnostics")
    _render_results(report.configuration)
    print()
    summary = report.summary
    print(
        "Health score: {score}% ({passed}/{total} checks passed)".format(
            score=summary["health_score"],
            passed=summary["passed"],
            total=summary["total_checks"],
        )
    )


def _render_results(results: Iterable[DiagnosticResult]) -> None:
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.check_name}: {result.message}")
        if result.fix_suggestion:
            print(f"        Suggested fix: {result.fix_suggestion}")


__all__ = ["register", "build"]
