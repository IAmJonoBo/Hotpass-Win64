"""Refresh Data Docs, lineage snapshots, and research manifests in a single pass."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- Great Expectations Data Docs ---
def run_data_contract_checks() -> None:
    """
    Generate Data Docs by reusing the ops/validation/refresh_data_docs helper.

    The helper loads sample workbooks from data/ and writes HTML outputs to
    dist/data-docs/. We treat failures as non-fatal so docs refresh remains
    best-effort on environments without optional dependencies.
    """

    try:
        from ops.validation.refresh_data_docs import main as refresh_data_docs_main
    except Exception as exc:  # noqa: BLE001 - optional dependency
        print(f"Great Expectations refresh skipped: unable to import helper ({exc}).")
        return

    try:
        exit_code = refresh_data_docs_main()
    except Exception as exc:  # noqa: BLE001 - keep doc refresh best-effort
        print(f"Great Expectations refresh skipped: {exc}")
        return

    if exit_code != 0:
        print(f"Great Expectations refresh completed with exit code {exit_code}.")
    else:
        print("Great Expectations refresh completed successfully.")


# --- Marquez lineage export (PNG + JSON) ---
def marquez_lineage_snapshot() -> None:
    marquez_url = os.environ.get("MARQUEZ_URL", "")
    api_key = os.environ.get("MARQUEZ_API_KEY", "")
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    output_dir = Path("docs/lineage/")
    output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_datasets(limit: int = 50) -> list[dict[str, Any]]:
        if not marquez_url:
            return []
        response = requests.get(
            f"{marquez_url}/api/v1/namespaces/default/datasets?limit={limit}",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        datasets = payload.get("datasets", [])
        if not isinstance(datasets, list):
            return []
        return datasets

    def write_json(name: str, data: Any) -> None:
        (output_dir / f"{name}.json").write_text(json.dumps(data, indent=2))

    try:
        datasets = fetch_datasets()
        if datasets:
            write_json("datasets", datasets)
    except Exception as exc:  # noqa: BLE001 - keep pipeline non-fatal
        print(f"Marquez export skipped: {exc}")

    (output_dir / "LAST_REFRESH.txt").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


# --- Research manifests cache directory (metadata only) ---
def ensure_research_manifests() -> None:
    Path("docs/research/").mkdir(parents=True, exist_ok=True)


def main() -> None:
    run_data_contract_checks()
    marquez_lineage_snapshot()
    ensure_research_manifests()
    print("Docs refresh complete.")


if __name__ == "__main__":
    main()
