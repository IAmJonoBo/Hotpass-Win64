"""Simple HTTP smoke checks for the docker-compose stack."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass

import requests


@dataclass
class CheckResult:
    name: str
    url: str
    passed: bool
    error: str | None = None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "name": self.name,
            "url": self.url,
            "passed": self.passed,
            "error": self.error,
        }


def run_check(name: str, url: str, timeout: float = 10.0) -> CheckResult:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return CheckResult(name=name, url=url, passed=True)
    except Exception as exc:  # pragma: no cover - exercised via CLI
        return CheckResult(name=name, url=url, passed=False, error=str(exc))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Base URL for the Hotpass web UI")
    parser.add_argument("--prefect-url", required=True, help="Prefect server base URL")
    parser.add_argument("--marquez-url", required=True, help="Marquez server base URL")
    parser.add_argument("--llm-url", help="Optional Ollama/LLM base URL")
    args = parser.parse_args(argv)

    checks = [
        ("web-ui", f"{args.base_url}/"),
        ("prefect-health", f"{args.prefect_url}/api/health"),
        ("marquez-health", f"{args.marquez_url}/healthcheck"),
    ]
    if args.llm_url:
        checks.append(("llm-tags", f"{args.llm_url}/api/tags"))

    results = [run_check(name, url) for name, url in checks]
    summary = {
        "checks": [result.as_dict() for result in results],
        "all_passed": all(result.passed for result in results),
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
