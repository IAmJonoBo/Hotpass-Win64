"""Sanity checks for the Marquez docker-compose stack."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml


def expect(condition: bool, message: str) -> None:
    """Raise a descriptive failure when the condition is false."""

    if not condition:
        pytest.fail(message)


def _load_compose() -> dict[str, Any]:
    compose_path = Path(__file__).resolve().parents[2] / "infra" / "marquez" / "docker-compose.yaml"
    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    expect(isinstance(payload, dict), "Compose file should parse into a mapping.")
    return cast(dict[str, Any], payload)


def test_marquez_compose_exposes_expected_services() -> None:
    """The compose stack should define the Marquez API/UI and backing database."""

    payload = _load_compose()
    services = payload.get("services", {})

    expect("marquez" in services, "Compose stack should include the Marquez service.")
    expect(
        "marquez-db" in services,
        "Compose stack should include the PostgreSQL backing store.",
    )

    marquez = services.get("marquez", {})
    depends_on = marquez.get("depends_on") or {}
    if isinstance(depends_on, dict):
        dependency_keys = set(depends_on)
    else:
        dependency_keys = set(depends_on)
    expect(
        "marquez-db" in dependency_keys,
        "Marquez service should depend on the database health check.",
    )
    marquez_ports = {str(port) for port in marquez.get("ports", [])}
    expect(
        any(port.endswith(":5000") for port in marquez_ports),
        "Marquez service should expose the API port.",
    )

    expect(
        "marquez-web" in services,
        "Compose stack should include the Marquez UI service.",
    )
    marquez_ui = services.get("marquez-web", {})
    ui_depends_on = marquez_ui.get("depends_on") or {}
    if isinstance(ui_depends_on, dict):
        ui_dependency_keys = set(ui_depends_on)
    else:
        ui_dependency_keys = set(ui_depends_on)
    expect(
        "marquez" in ui_dependency_keys,
        "Marquez UI should depend on the API service.",
    )
    marquez_ui_ports = {str(port) for port in marquez_ui.get("ports", [])}
    expect(
        any(port.endswith(":3000") for port in marquez_ui_ports),
        "Marquez UI service should expose the UI port.",
    )

    db_service = services.get("marquez-db", {})
    db_env = db_service.get("environment", {})
    expect(
        db_env.get("POSTGRES_DB") == "marquez",
        "Database name should be set for Marquez.",
    )
    expect(
        db_env.get("POSTGRES_USER") == "marquez",
        "Database user should match the Marquez defaults.",
    )
    expect(
        db_env.get("POSTGRES_PASSWORD") == "marquez",
        "Database password should match the stack defaults.",
    )


def test_marquez_compose_declares_persistent_volume() -> None:
    """The stack should declare a persistent volume for PostgreSQL state."""

    payload = _load_compose()
    volumes = payload.get("volumes", {})

    expect(
        "marquez_db" in volumes,
        "Persistent volume for Marquez database should be declared.",
    )
    volume_def = volumes.get("marquez_db", {})
    expect(
        isinstance(volume_def, dict),
        "Volume definition should be a mapping for compatibility with Compose.",
    )
