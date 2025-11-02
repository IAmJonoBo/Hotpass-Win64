"""Validate ARC manifests and LLM configuration for CI integration checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [doc for doc in yaml.safe_load_all(handle) if isinstance(doc, dict)]


def validate_arc_manifests(root: Path) -> list[str]:
    errors: list[str] = []
    runner_path = root / "runner-scale-set.yaml"
    config_path = root / "github-config.yaml"

    if not runner_path.exists():
        errors.append(f"runner-scale-set manifest missing: {runner_path}")
    else:
        for doc in _load_yaml_documents(runner_path):
            kind = doc.get("kind")
            if kind == "RunnerScaleSet":
                spec = doc.get("spec", {})
                template = spec.get("template", {})
                template_spec = template.get("spec", {})
                containers = template_spec.get("containers")
                if not containers:
                    errors.append("RunnerScaleSet missing containers specification")
                else:
                    for container in containers:
                        image = container.get("image")
                        if not image:
                            errors.append("Runner container missing image reference")
                        resources = container.get("resources", {})
                        if not resources:
                            errors.append("Runner container missing resource limits/requests")
                if not template_spec.get("serviceAccountName"):
                    errors.append("RunnerScaleSet missing serviceAccountName")
            if kind == "HorizontalRunnerAutoscaler":
                spec = doc.get("spec", {})
                if spec.get("scaleTargetRef", {}).get("name") != doc.get("metadata", {}).get("name"):
                    errors.append("HorizontalRunnerAutoscaler scaleTargetRef must reference itself")

    if not config_path.exists():
        errors.append(f"GitHubConfig manifest missing: {config_path}")
    else:
        for doc in _load_yaml_documents(config_path):
            if doc.get("kind") == "GitHubConfig":
                spec = doc.get("spec", {})
                if not spec.get("githubConfigUrl"):
                    errors.append("GitHubConfig missing githubConfigUrl")
                if not spec.get("runnerGithubUrl"):
                    errors.append("GitHubConfig missing runnerGithubUrl")
                secret_ref = spec.get("githubAppSecretRef", {})
                if not secret_ref.get("name") or not secret_ref.get("key"):
                    errors.append("GitHubConfig missing githubAppSecretRef name/key")

    return errors


def validate_llm_config(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"LLM config not found: {path}"]

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    llm = payload.get("llm")
    if not isinstance(llm, dict):
        return ["LLM configuration missing 'llm' section"]

    providers = llm.get("providers")
    if not isinstance(providers, list) or not providers:
        errors.append("LLM configuration must define at least one provider")
    else:
        for index, provider in enumerate(providers):
            if not isinstance(provider, dict):
                errors.append(f"Provider #{index} is not a mapping")
                continue
            for field in ("name", "label", "kind"):
                if not provider.get(field):
                    errors.append(f"Provider '{provider.get('name', f'#{index}')}' missing field: {field}")
            if provider.get("kind") == "api" and not provider.get("api_key_env"):
                errors.append(f"API provider '{provider.get('name')}' missing api_key_env")

    strategy = llm.get("strategy")
    if not isinstance(strategy, str):
        errors.append("LLM configuration missing strategy")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arc-root", type=Path, required=True, help="Path to ARC manifest directory")
    parser.add_argument("--llm-config", type=Path, required=True, help="Path to llm-providers.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/ci-badges/integration-profiles.json"),
        help="Path to write JSON summary",
    )
    args = parser.parse_args()

    arc_errors = validate_arc_manifests(args.arc_root)
    llm_errors = validate_llm_config(args.llm_config)

    summary = {
        "arc": {"passed": not arc_errors, "errors": arc_errors},
        "llm": {"passed": not llm_errors, "errors": llm_errors},
    }
    summary["all_passed"] = summary["arc"]["passed"] and summary["llm"]["passed"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
