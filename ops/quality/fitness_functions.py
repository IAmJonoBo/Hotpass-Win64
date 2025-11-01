"""Evaluate automated fitness functions for Hotpass."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "apps" / "data-platform" / "hotpass"


class FitnessFailure(Exception):
    """Raised when a fitness function fails."""


def check_module_length(module: str, max_lines: int) -> None:
    path = SRC_ROOT / module
    try:
        line_count = sum(1 for _ in path.open("r", encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise FitnessFailure(f"module {module} missing; expected at {path}") from exc
    if line_count > max_lines:
        raise FitnessFailure(f"{module} exceeds {max_lines} lines ({line_count})")


def check_import(module: str, module_path: str, symbol: str) -> None:
    path = SRC_ROOT / module
    tree = ast.parse(path.read_text(encoding="utf-8"))
    candidates = {module_path, module_path.lstrip(".")}
    if not any(
        isinstance(node, ast.ImportFrom)
        and node.module in candidates
        and any(alias.name == symbol for alias in node.names)
        for node in ast.walk(tree)
    ):
        raise FitnessFailure(f"{module} missing instrumentation import {symbol} from {module_path}")


def check_public_api(module: str, symbols: list[str]) -> None:
    path = SRC_ROOT / module
    tree = ast.parse(path.read_text(encoding="utf-8"))
    exported: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = node.value
                if isinstance(value, ast.List | ast.Tuple):
                    for element in value.elts:
                        if isinstance(element, ast.Constant) and isinstance(element.value, str):
                            exported.add(element.value)
    missing = [symbol for symbol in symbols if symbol not in exported]
    if missing:
        raise FitnessFailure(f"{module} missing public exports: {missing}")


def _module_length_check(module: str, max_lines: int) -> Callable[[], None]:
    def _check() -> None:
        check_module_length(module, max_lines)

    return _check


def check_profile_completeness(profile_name: str) -> None:
    """Check that a profile has all 4 required blocks."""
    import yaml

    profile_path = (
        PROJECT_ROOT / "apps" / "data-platform" / "hotpass" / "profiles" / f"{profile_name}.yaml"
    )
    if not profile_path.exists():
        raise FitnessFailure(f"Profile {profile_name} not found at {profile_path}")

    try:
        with open(profile_path) as f:
            profile = yaml.safe_load(f)
    except Exception as e:
        raise FitnessFailure(f"Failed to load profile {profile_name}: {e}") from e

    required_blocks = ["ingest", "refine", "enrich", "compliance"]
    missing = [block for block in required_blocks if block not in profile]

    if missing:
        raise FitnessFailure(f"Profile {profile_name} missing blocks: {missing}")


def main() -> None:
    module_thresholds = {
        "pipeline/base.py": 500,
        "pipeline/aggregation.py": 750,
        "pipeline/ingestion.py": 200,
        "pipeline/validation.py": 200,
        "pipeline/export.py": 200,
        "pipeline/enrichment.py": 150,
        "pipeline_enhanced.py": 200,
    }

    checks: list[Callable[[], None]] = [
        *(_module_length_check(module, limit) for module, limit in module_thresholds.items()),
        lambda: check_import(
            "observability.py",
            ".telemetry.registry",
            "build_default_registry",
        ),
        lambda: check_public_api("__init__.py", ["run_pipeline", "PipelineConfig"]),
        # Profile completeness checks (Sprint 3)
        lambda: check_profile_completeness("aviation"),
        lambda: check_profile_completeness("generic"),
        lambda: check_profile_completeness("test"),
    ]

    failures: list[str] = []
    for check in checks:
        try:
            check()
        except FitnessFailure as exc:  # pragma: no cover - exit path
            failures.append(str(exc))

    if failures:
        for failure in failures:
            print(f"❌ {failure}")
        raise SystemExit(1)

    print("✅ Fitness functions satisfied")


if __name__ == "__main__":
    main()
