from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SimulationRun:
    name: str
    tool: str
    description: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class SimulationRunLoader:
    """Load simulated MCP responses stored under data/pyside-ui."""

    def __init__(self, data_dir: Path | None = None) -> None:
        default_data_dir = Path(__file__).resolve().parents[2] / "data" / "pyside-ui"
        self.data_dir = data_dir or default_data_dir

    def available(self) -> list[str]:
        return sorted(path.stem for path in self.data_dir.glob("*.json"))

    def load(self, name: str) -> SimulationRun:
        path = self.data_dir / f"{name}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SimulationRun(
            name=name,
            tool=str(payload.get("tool", "")),
            description=str(payload.get("description", "")),
            arguments=self._as_dict(payload.get("arguments", {})),
            result=self._as_dict(payload.get("result", {})),
        )

    def _as_dict(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}
