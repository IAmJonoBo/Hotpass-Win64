"""Implementation of the `hotpass dashboard` subcommand."""

from __future__ import annotations

import argparse
import importlib
import ipaddress
import re
from collections.abc import Iterable
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from ..builder import CLICommand, SharedParsers
from ..configuration import CLIProfile
from ..progress import DEFAULT_SENSITIVE_FIELD_TOKENS, StructuredLogger
from ..shared import normalise_sensitive_fields

_SAFE_HOST_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def build(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    shared: SharedParsers,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "dashboard",
        help="Launch the Hotpass Streamlit monitoring dashboard",
        description="Start the Streamlit dashboard bound to a specific host and port.",
        parents=[shared.base],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--port", type=int, default=8501, help="Port for Streamlit dashboard")
    parser.add_argument("--host", default="localhost", help="Host for dashboard server")
    return parser


def register() -> CLICommand:
    return CLICommand(
        name="dashboard",
        help="Launch the Hotpass dashboard",
        builder=build,
        handler=_command_handler,
    )


def _command_handler(namespace: argparse.Namespace, profile: CLIProfile | None) -> int:
    log_format_value: str | None = getattr(namespace, "log_format", None)
    if log_format_value is None and profile is not None:
        log_format_value = profile.log_format
    log_format = (log_format_value or "rich").lower()
    if log_format not in {"json", "rich"}:
        msg = f"Unsupported log format: {log_format}"
        raise ValueError(msg)

    raw_sensitive = getattr(namespace, "sensitive_fields", None)
    if raw_sensitive is None and profile is not None:
        raw_sensitive = profile.options.get("sensitive_fields")
    sensitive_iter: Iterable[str] | None = None
    if isinstance(raw_sensitive, str):
        sensitive_iter = [raw_sensitive]
    elif isinstance(raw_sensitive, Iterable):
        sensitive_iter = [str(value) for value in raw_sensitive if value is not None]
    elif raw_sensitive is not None:
        sensitive_iter = [str(raw_sensitive)]
    sensitive_fields = normalise_sensitive_fields(sensitive_iter, DEFAULT_SENSITIVE_FIELD_TOKENS)
    logger = StructuredLogger(log_format, sensitive_fields)
    console = logger.console if log_format == "rich" else None

    if not 0 < namespace.port < 65536:
        logger.log_error("Invalid port. Provide an integer between 1 and 65535.")
        return 1

    host = _normalise_dashboard_host(namespace.host)
    if host is None:
        logger.log_error("Invalid host. Use localhost or a valid IP/DNS label.")
        return 1

    runner, error_message = _load_streamlit_runner()
    if runner is None:
        logger.log_error(error_message or "Streamlit CLI could not be loaded")
        return 1

    dashboard_path = _resolve_dashboard_path()
    if dashboard_path is None:  # pragma: no cover - defensive guard
        logger.log_error("Hotpass dashboard module could not be located")
        return 1

    command = [
        str(dashboard_path),
        "--server.port",
        str(namespace.port),
        "--server.address",
        host,
    ]

    if console:
        console.print("[bold cyan]Launching Hotpass dashboard...[/bold cyan]")
        console.print(f"[dim]Command:[/dim] {' '.join(command)}")

    try:
        runner(command)
    except SystemExit as exc:
        code = exc.code or 0
        if code != 0:
            logger.log_error("Dashboard exited with non-zero status.")
        return int(code)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.log_error(f"Dashboard failed to start: {exc}")
        return 1

    logger.log_event(
        "dashboard.started",
        {"host": host, "port": namespace.port, "entrypoint": str(dashboard_path)},
    )
    return 0


def _normalise_dashboard_host(host: str) -> str | None:
    candidate = host.strip()
    if not candidate:
        return None
    if candidate == "localhost":
        return "localhost"
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        if _SAFE_HOST_PATTERN.fullmatch(candidate):
            return candidate
        return None
    else:
        return candidate


def _load_streamlit_runner() -> tuple[Any | None, str | None]:
    try:
        streamlit_cli = importlib.import_module("streamlit.web.cli")
    except ModuleNotFoundError:
        return None, "Streamlit not found. Install with: uv sync --extra dashboards"
    except Exception as exc:  # pragma: no cover - defensive guard
        return None, f"Unable to load Streamlit CLI: {exc}"

    runner = getattr(streamlit_cli, "main_run", None)
    if runner is None:
        return None, "Streamlit CLI entrypoint missing. Upgrade Streamlit to ≥1.25."
    return runner, None


def _resolve_dashboard_path() -> Path | None:
    spec = find_spec("hotpass.dashboard")
    if spec and spec.origin:
        return Path(spec.origin)
    candidate = Path(__file__).resolve().parents[2] / "dashboard.py"
    return candidate if candidate.exists() else None


__all__ = ["register", "build"]
