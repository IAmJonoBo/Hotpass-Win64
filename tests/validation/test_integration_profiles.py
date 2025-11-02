from __future__ import annotations

import json
from pathlib import Path

from ops.validation import check_integration_profiles
from ops.validation import docker_smoke


def test_arc_manifests_are_valid() -> None:
    arc_root = Path("infra/arc")
    errors = check_integration_profiles.validate_arc_manifests(arc_root)
    assert errors == [], f"ARC manifest validation errors: {errors}"


def test_llm_config_is_valid() -> None:
    config = Path("apps/web-ui/public/config/llm-providers.yaml")
    errors = check_integration_profiles.validate_llm_config(config)
    assert errors == [], f"LLM config validation errors: {errors}"


def test_docker_smoke_main_success(monkeypatch, capsys) -> None:
    def _fake_check(name: str, url: str) -> docker_smoke.CheckResult:
        return docker_smoke.CheckResult(name=name, url=url, passed=True)

    monkeypatch.setattr(docker_smoke, "run_check", _fake_check)
    exit_code = docker_smoke.main(
        [
            "--base-url",
            "http://localhost:3001",
            "--prefect-url",
            "http://localhost:4200",
            "--marquez-url",
            "http://localhost:5001",
            "--llm-url",
            "http://localhost:11434",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_passed"]
    assert {check["name"] for check in payload["checks"]} == {
        "web-ui",
        "prefect-health",
        "marquez-health",
        "llm-tags",
    }
