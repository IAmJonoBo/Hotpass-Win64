"""Render dependency and vulnerability summaries for release automation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SEVERITY_ORDER = ["critical", "high", "medium", "low", "unknown"]


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def summarise_pip_audit(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": 0, "by_severity": {key: 0 for key in SEVERITY_ORDER}}
    if not payload:
        return summary
    if isinstance(payload, dict) and "dependencies" in payload:
        # pip-audit >=2.7 schema
        vulnerabilities = payload.get("vulnerabilities", [])
    else:
        vulnerabilities = payload
    if not isinstance(vulnerabilities, list):
        return summary
    for finding in vulnerabilities:
        severity = str(finding.get("severity", "unknown")).lower()
        summary["total"] += 1
        if severity not in summary["by_severity"]:
            summary["by_severity"]["unknown"] += 1
        else:
            summary["by_severity"][severity] += 1
    return summary


def summarise_npm_audit(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": 0, "by_severity": {key: 0 for key in SEVERITY_ORDER}}
    if not payload or not isinstance(payload, dict):
        return summary
    metadata = payload.get("metadata") or {}
    vulnerabilities = metadata.get("vulnerabilities") or {}
    total = metadata.get("total", 0)
    summary["total"] = int(total) if isinstance(total, int) else int(vulnerabilities.get("total", 0) or 0)
    for severity in SEVERITY_ORDER:
        count = vulnerabilities.get(severity, 0)
        if isinstance(count, int):
            summary["by_severity"][severity] = count
    return summary


def render_summary(pip_summary: dict[str, Any], npm_summary: dict[str, Any]) -> str:
    lines = ["## Security Reports", "", "### Python (pip-audit)"]
    if pip_summary["total"] == 0:
        lines.append("- No known vulnerabilities detected.")
    else:
        lines.append(f"- {pip_summary['total']} vulnerabilities detected")
        lines.extend(
            f"  - {severity.title()}: {pip_summary['by_severity'][severity]}"
            for severity in SEVERITY_ORDER
            if pip_summary['by_severity'][severity] > 0
        )
    lines.append("")
    lines.append("### Web UI (npm audit)")
    if npm_summary["total"] == 0:
        lines.append("- No known vulnerabilities detected.")
    else:
        lines.append(f"- {npm_summary['total']} vulnerabilities detected")
        lines.extend(
            f"  - {severity.title()}: {npm_summary['by_severity'][severity]}"
            for severity in SEVERITY_ORDER
            if npm_summary['by_severity'][severity] > 0
        )
    lines.append("")
    lines.append("Raw reports are published alongside this release for downstream triage.")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render release security summary text.")
    parser.add_argument("--pip-audit", type=Path, required=True, help="Path to pip-audit JSON output")
    parser.add_argument("--npm-audit", type=Path, required=True, help="Path to npm audit JSON output")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the Markdown summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    pip_payload = load_json(args.pip_audit)
    npm_payload = load_json(args.npm_audit)
    summary = render_summary(summarise_pip_audit(pip_payload), summarise_npm_audit(npm_payload))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
