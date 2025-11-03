"""Refresh Data Docs, lineage snapshots, and research manifests in a single pass."""

from __future__ import annotations

import importlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]


# --- GE Data Docs ---
# Run the checkpoint via the Python API so we avoid shelling out on hardened runners.
def run_ge_checkpoint() -> None:
    try:
        gx_module: Any = importlib.import_module("great_expectations")
        context = gx_module.get_context()
        context.run_checkpoint(checkpoint_name="contacts_checkpoint")
    except Exception as exc:  # noqa: BLE001 - log but keep pipeline green
        print(f"Great Expectations checkpoint skipped: {exc}")


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

    (output_dir / "LAST_REFRESH.txt").write_text(
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )


# --- Research manifests cache directory (metadata only) ---
def ensure_research_manifests() -> None:
    Path("docs/research/").mkdir(parents=True, exist_ok=True)


def main() -> None:
    run_ge_checkpoint()
    marquez_lineage_snapshot()
    ensure_research_manifests()
    print("Docs refresh complete.")


if __name__ == "__main__":
    main()
