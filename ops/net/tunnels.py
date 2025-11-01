"""Helpers for managing Hotpass tunnel state."""

from __future__ import annotations

import os
import signal
import socket
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from hotpass.cli.state import load_state, remove_state, write_state

STATE_FILE = "net.json"


@dataclass(slots=True)
class TunnelSession:
    """Representation of a stored tunnel session."""

    label: str
    via: str
    command: list[str]
    pid: int | None
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the session for persistence."""

        return {
            "label": self.label,
            "via": self.via,
            "command": list(self.command),
            "pid": self.pid,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TunnelSession:
        """Hydrate a session from JSON payloads stored on disk."""

        return cls(
            label=str(payload.get("label", "")),
            via=str(payload.get("via", "")),
            command=list(payload.get("command", [])),
            pid=payload.get("pid"),
            created_at=str(payload.get("created_at", "")),
            metadata=dict(payload.get("metadata", {})),
        )


def load_sessions() -> list[TunnelSession]:
    """Return all persisted tunnel sessions."""

    data = load_state(STATE_FILE, default={"sessions": []}) or {"sessions": []}
    sessions: list[TunnelSession] = []
    for entry in data.get("sessions", []):
        try:
            sessions.append(TunnelSession.from_dict(entry))
        except Exception:  # pragma: no cover - defensive guard
            continue
    return sessions


def save_sessions(sessions: Iterable[TunnelSession]) -> None:
    """Persist tunnel sessions back to disk."""

    payload = {"sessions": [session.to_dict() for session in sessions]}
    write_state(STATE_FILE, payload)


def clear_sessions() -> None:
    """Remove the tunnel state file entirely."""

    remove_state(STATE_FILE)


def latest_session() -> TunnelSession | None:
    """Return the most recently recorded tunnel session, if any."""

    sessions = load_sessions()
    return sessions[-1] if sessions else None


def is_port_available(port: int) -> bool:
    """Return True if the requested port can be bound locally."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def find_available_port(start: int, *, limit: int = 20) -> int | None:
    """Locate the next available port from a starting value."""

    port = start
    for _ in range(limit):
        if is_port_available(port):
            return port
        port += 1
    return None


def format_ports(metadata: dict[str, Any]) -> str:
    """Render tunnel metadata into a human-readable summary."""

    details: list[str] = []
    prefect = metadata.get("prefect", {})
    if prefect.get("local_port"):
        details.append(f"Prefect:{prefect['local_port']}")
    marquez = metadata.get("marquez", {})
    if marquez.get("local_port"):
        details.append(f"Marquez:{marquez['local_port']}")
    return ", ".join(details) if details else "-"


def is_process_alive(pid: int) -> bool:
    """Check if a PID is still running."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_pid(pid: int) -> None:
    """Terminate a process, preferring process group signals when possible."""

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:  # pragma: no cover - fall back to individual kill
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:  # pragma: no cover - best effort
            return
