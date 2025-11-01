from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from hotpass import cli
from hotpass.cli.builder import CommandHandler


def _invoke(argv: list[str]) -> int:
    parser = cli.build_parser()
    args = parser.parse_args(argv)
    handler = cast(CommandHandler | None, getattr(args, "handler", None))
    assert handler is not None, "Handler must be bound on parsed namespace"
    # None profile since these commands do not rely on CLI profiles
    return handler(args, None)


def test_net_up_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_STATE_DIR", str(tmp_path / ".hotpass"))
    exit_code = _invoke(
        [
            "net",
            "up",
            "--host",
            "bastion.example.com",
            "--dry-run",
        ],
    )
    assert exit_code == 0


def test_aws_check_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_STATE_DIR", str(tmp_path / ".hotpass"))
    exit_code = _invoke(
        [
            "aws",
            "--profile",
            "staging",
            "--dry-run",
        ],
    )
    assert exit_code == 0


def test_ctx_init_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_STATE_DIR", str(tmp_path / ".hotpass"))
    exit_code = _invoke(
        [
            "ctx",
            "init",
            "--prefect-profile",
            "hotpass-dev",
            "--prefect-url",
            "http://127.0.0.1:9999/api",
            "--no-kube",
            "--dry-run",
        ],
    )
    assert exit_code == 0


def test_env_write_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_STATE_DIR", str(tmp_path / ".hotpass"))
    exit_code = _invoke(
        [
            "env",
            "--target",
            "demo",
            "--prefect-url",
            "http://127.0.0.1:1111/api",
            "--openlineage-url",
            "http://127.0.0.1:2222/api/v1",
            "--allow-network",
            "--dry-run",
        ],
    )
    assert exit_code == 0


def test_arc_verify_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_STATE_DIR", str(tmp_path / ".hotpass"))
    exit_code = _invoke(
        [
            "arc",
            "--owner",
            "example",
            "--repository",
            "repo",
            "--scale-set",
            "runner-set",
            "--dry-run",
        ],
    )
    assert exit_code == 0


def test_distro_docs_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOTPASS_STATE_DIR", str(tmp_path / ".hotpass"))
    exit_code = _invoke(
        [
            "distro",
            "docs",
            "--output",
            str(tmp_path / "docs"),
            "--dry-run",
        ],
    )
    assert exit_code == 0
