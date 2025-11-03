"""Utility helpers for CLI commands."""

from __future__ import annotations

import shlex
import subprocess  # nosec B404 - subprocess is required for CLI command execution
from collections.abc import Iterable, Sequence


class CommandExecutionError(RuntimeError):
    """Raised when a subprocess exits with a non-zero status."""


def format_command(command: Sequence[str]) -> str:
    """Return a shell-compatible string for display."""

    return " ".join(shlex.quote(part) for part in command)


def run_command(
    command: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command with consistent defaults."""

    proc = subprocess.run(  # nosec B603 - command arguments are explicit; shell disabled
        list(command),
        check=False,
        capture_output=capture_output,
        text=text,
        env=env,
    )
    if check and proc.returncode != 0:
        raise CommandExecutionError(
            f"Command failed with exit code {proc.returncode}: {format_command(command)}\n"
            f"{proc.stderr if proc.stderr else ''}"
        )
    return proc


def ensure_sequence(values: Iterable[str] | None) -> list[str]:
    """Normalise an iterable of strings into a list."""

    if values is None:
        return []
    if isinstance(values, list):
        return values
    return list(values)
