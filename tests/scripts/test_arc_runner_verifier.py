"""Tests for the ARC runner lifecycle verification helpers."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import requests

import ops.arc.verify_runner_lifecycle as lifecycle


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@dataclass
class _Response:
    json_payload: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return self.json_payload

    def raise_for_status(self) -> None:  # noqa: D401 - behaviour is mocked
        """Mimic `requests.Response.raise_for_status`."""
        return None


class _Session(requests.Session):
    def __init__(self, payloads: Iterator[dict[str, Any]]) -> None:
        super().__init__()
        self._payloads = payloads
        self.request_count = 0

    def get(  # type: ignore[override]
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | tuple[float, float] | None = None,
    ) -> _Response:
        self.request_count += 1
        try:
            payload = next(self._payloads)
        except StopIteration as exc:  # pragma: no cover - guard for unexpected calls
            raise AssertionError("No more payloads configured for test") from exc
        return _Response(json_payload=payload)


class _Command:
    def __init__(self, results: Iterator[str]) -> None:
        self._results = results
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        self.calls.append(args)
        try:
            return next(self._results)
        except StopIteration as exc:  # pragma: no cover - guard for unexpected calls
            raise AssertionError("No more command results configured for test") from exc


class _Clock:
    def __init__(self, values: Iterator[float]) -> None:
        self._values = values

    def __call__(self) -> float:
        try:
            return next(self._values)
        except StopIteration as exc:  # pragma: no cover - guard for unexpected calls
            raise AssertionError("Clock exhausted during test") from exc


class _Sleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, duration: float) -> None:
        self.calls.append(duration)


class _VerifierFactory:
    def __init__(
        self,
        github_payloads: Iterator[dict[str, Any]],
        command_results: Iterator[str],
        clock_values: Iterator[float],
        poll_interval: float,
        timeout: float,
    ) -> None:
        self.session = _Session(payloads=github_payloads)
        self.command = _Command(results=command_results)
        self.clock = _Clock(values=clock_values)
        self.sleeper = _Sleeper()
        self.verifier = lifecycle.RunnerLifecycleVerifier(
            owner="Hotpass",
            repository="pipeline",
            scale_set="hotpass-arc",
            namespace="arc-runners",
            session=self.session,
            run_command=self.command,
            now=self.clock,
            sleep=self.sleeper,
            timeout_seconds=timeout,
            poll_interval=poll_interval,
        )


def _build_verifier(
    github_payloads: Iterator[dict[str, Any]],
    command_results: Iterator[str],
    clock_values: Iterator[float],
    poll_interval: float = 1.0,
    timeout: float = 5.0,
) -> tuple[lifecycle.RunnerLifecycleVerifier, _Sleeper]:
    factory = _VerifierFactory(
        github_payloads=github_payloads,
        command_results=command_results,
        clock_values=clock_values,
        poll_interval=poll_interval,
        timeout=timeout,
    )
    return factory.verifier, factory.sleeper


def test_verifier_succeeds_when_runners_idle() -> None:
    payloads = iter(
        [
            {"total_count": 1, "runners": [{"busy": True, "name": "hotpass-arc-1"}]},
            {"total_count": 1, "runners": [{"busy": False, "name": "hotpass-arc-1"}]},
        ]
    )
    command_results = iter(["runner-pod", ""])  # kubectl output shows pod until drained
    clock_values = iter([0.0, 1.0, 2.1])

    verifier, sleeper = _build_verifier(payloads, command_results, clock_values)
    verifier.verify()

    expect(len(sleeper.calls) == 1, "Verifier should sleep while waiting for drain")


def test_verifier_raises_when_timeout_expires() -> None:
    payloads = iter([{"total_count": 1, "runners": [{"busy": True, "name": "hotpass-arc-1"}]}] * 4)
    command_results = iter(["runner-pod", "runner-pod"])  # pods never drain
    clock_values = iter([0.0, 1.0, 2.0, 3.1])

    verifier, _ = _build_verifier(
        payloads,
        command_results,
        clock_values,
        poll_interval=0.5,
        timeout=3.0,
    )

    error: Exception | None = None
    try:
        verifier.verify()
    except Exception as exc:  # noqa: BLE001 - capturing for expect pattern
        error = exc

    expect(error is not None, "Verifier should raise when runners remain busy")
    expect("Timed out" in str(error), "Error should mention timeout for diagnostics")


def test_cli_snapshot_mode(tmp_path: Path) -> None:
    snapshot = {
        "iterations": [
            {
                "pods": ["runner-pod"],
                "runners": [{"name": "hotpass-arc-1", "busy": True}],
            },
            {
                "pods": [],
                "runners": [{"name": "hotpass-arc-1", "busy": False}],
            },
        ]
    }
    snapshot_path = tmp_path / "scenario.json"
    snapshot_path.write_text(json.dumps(snapshot))

    result = subprocess.run(
        [
            sys.executable,
            "ops/arc/verify_runner_lifecycle.py",
            "--owner",
            "Hotpass",
            "--repository",
            "pipeline",
            "--scale-set",
            "hotpass-arc",
            "--snapshot",
            str(snapshot_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    expect(result.returncode == 0, "Snapshot mode should exit successfully")
    expect(
        "Runner scale set is healthy" in result.stdout,
        "Snapshot mode should report healthy status",
    )


def test_identity_verifier_prefers_boto3_when_available() -> None:
    captured: dict[str, Any] = {}

    class _StubClient:
        def __init__(self, profile: str | None) -> None:
            self.profile = profile

        def get_caller_identity(self) -> dict[str, str]:
            return {
                "Account": "123456789012",
                "Arn": "arn:aws:sts::123456789012:assumed-role/hotpass-arc/staging",
                "UserId": "ARO123456789:Hotpass",
            }

    class _StubSession:
        def __init__(self, profile_name: str | None = None) -> None:
            captured["profile"] = profile_name

        def client(self, service_name: str, region_name: str | None = None) -> _StubClient:
            expect(service_name == "sts", "Identity verifier should request an STS client")
            captured["region"] = region_name
            return _StubClient(profile=captured.get("profile"))

    def _load_boto3() -> Any:
        return SimpleNamespace(session=SimpleNamespace(Session=_StubSession))

    summary = lifecycle.AwsIdentityVerifier(
        region="eu-west-1",
        profile="staging",
        boto3_loader=_load_boto3,
    ).verify()

    expect(summary.source == "boto3", "Verifier should prefer boto3 when available")
    expect(summary.account == "123456789012", "Account should surface from STS response")
    expect(captured.get("region") == "eu-west-1", "Region should be forwarded to boto3")
    expect(captured.get("profile") == "staging", "Profile should be forwarded to boto3")


def test_identity_verifier_falls_back_to_cli() -> None:
    command = _Command(
        results=iter(
            [
                json.dumps(
                    {
                        "Account": "123456789012",
                        "Arn": "arn:aws:sts::123456789012:assumed-role/hotpass-arc/staging",
                        "UserId": "ARO123456789:Hotpass",
                    }
                )
            ]
        )
    )

    def _missing_boto3() -> ModuleType:
        raise ModuleNotFoundError("boto3")

    summary = lifecycle.AwsIdentityVerifier(
        region="eu-west-1",
        profile="staging",
        boto3_loader=_missing_boto3,
        run_command=command,
    ).verify()

    expect(summary.source == "aws-cli", "Fallback should surface CLI as the source")
    expect(len(command.calls) == 1, "CLI fallback should run exactly once")
    expect(command.calls[0][0] == "aws", "CLI fallback should invoke the aws executable")
    expect("--profile" in command.calls[0], "Profile should be passed to the CLI")
    expect("--region" in command.calls[0], "Region should be passed to the CLI")


def test_identity_verifier_handles_generic_import_error() -> None:
    command = _Command(
        results=iter(
            [
                json.dumps(
                    {
                        "Account": "123456789012",
                        "Arn": "arn:aws:sts::123456789012:assumed-role/hotpass-arc/staging",
                        "UserId": "ARO123456789:Hotpass",
                    }
                )
            ]
        )
    )

    def _broken_boto3() -> ModuleType:
        raise ImportError("boto3 compiled without SSL support")

    summary = lifecycle.AwsIdentityVerifier(
        region="eu-west-1",
        profile="staging",
        boto3_loader=_broken_boto3,
        run_command=command,
    ).verify()

    expect(
        summary.source == "aws-cli",
        "Generic import failures should fall back to the CLI",
    )
    expect(len(command.calls) == 1, "CLI should execute once during fallback")


def test_identity_verifier_raises_when_cli_missing() -> None:
    def _missing_boto3() -> ModuleType:
        raise ModuleNotFoundError("boto3")

    def _missing_cli(_: list[str]) -> str:
        raise FileNotFoundError("aws")

    error: Exception | None = None
    try:
        lifecycle.AwsIdentityVerifier(
            region="eu-west-1",
            profile="staging",
            boto3_loader=_missing_boto3,
            run_command=cast(lifecycle.CommandRunner, _missing_cli),
        ).verify()
    except Exception as exc:  # noqa: BLE001 - captured for expect pattern
        error = exc

    expect(error is not None, "Missing CLI should raise an exception")
    expect(isinstance(error, RuntimeError), "Missing CLI should surface as a runtime error")
    expect(
        "aws cli" in str(error).lower(),
        "Error message should mention AWS CLI availability",
    )


def test_cli_reports_identity_in_json_mode(tmp_path: Path) -> None:
    snapshot = {
        "iterations": [
            {"pods": ["runner-pod"], "runners": [{"name": "arc", "busy": True}]},
            {"pods": [], "runners": [{"name": "arc", "busy": False}]},
        ]
    }
    snapshot_path = tmp_path / "scenario.json"
    snapshot_path.write_text(json.dumps(snapshot))

    captured: dict[str, Any] = {}

    class _StubIdentityVerifier:
        def __init__(self, *, region: str | None, profile: str | None, **_: Any) -> None:
            captured["region"] = region
            captured["profile"] = profile

        def verify(self) -> lifecycle.AwsIdentitySummary:
            return lifecycle.AwsIdentitySummary(
                account="123456789012",
                arn="arn:aws:sts::123456789012:assumed-role/hotpass-arc/staging",
                user_id="ARO123456789:Hotpass",
                source="stub",
            )

    original_identity = lifecycle.AwsIdentityVerifier
    lifecycle.AwsIdentityVerifier = _StubIdentityVerifier  # type: ignore[misc,assignment]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = lifecycle.main(
                [
                    "--owner",
                    "Hotpass",
                    "--repository",
                    "pipeline",
                    "--scale-set",
                    "hotpass-arc",
                    "--namespace",
                    "arc-runners",
                    "--snapshot",
                    str(snapshot_path),
                    "--verify-oidc",
                    "--aws-region",
                    "eu-west-1",
                    "--aws-profile",
                    "staging",
                    "--output",
                    "json",
                ]
            )
    finally:
        lifecycle.AwsIdentityVerifier = original_identity  # type: ignore[misc]

    expect(exit_code == 0, "CLI should exit successfully when verification passes")
    payload = json.loads(stdout.getvalue() or "{}")
    expect(payload.get("success") is True, "JSON payload should indicate success")
    identity = payload.get("identity") or {}
    expect(
        identity.get("source") == "stub",
        "Identity details should be included in output",
    )
    expect(captured.get("region") == "eu-west-1", "Region flag should be forwarded")
    expect(captured.get("profile") == "staging", "Profile flag should be forwarded")
    expect(stderr.getvalue() == "", "No stderr output expected on success")


def test_cli_treats_empty_region_as_none(tmp_path: Path) -> None:
    snapshot = {
        "iterations": [
            {"pods": ["runner-pod"], "runners": [{"name": "arc", "busy": True}]},
            {"pods": [], "runners": [{"name": "arc", "busy": False}]},
        ]
    }
    snapshot_path = tmp_path / "scenario.json"
    snapshot_path.write_text(json.dumps(snapshot))

    captured: dict[str, Any] = {}

    class _StubIdentityVerifier:
        def __init__(self, *, region: str | None, profile: str | None, **_: Any) -> None:
            captured["region"] = region
            captured["profile"] = profile

        def verify(self) -> lifecycle.AwsIdentitySummary:
            return lifecycle.AwsIdentitySummary(
                account="123456789012",
                arn="arn:aws:sts::123456789012:assumed-role/hotpass-arc/staging",
                user_id="ARO123456789:Hotpass",
                source="stub",
            )

    original_identity = lifecycle.AwsIdentityVerifier
    lifecycle.AwsIdentityVerifier = _StubIdentityVerifier  # type: ignore[misc,assignment]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = lifecycle.main(
                [
                    "--owner",
                    "Hotpass",
                    "--repository",
                    "pipeline",
                    "--scale-set",
                    "hotpass-arc",
                    "--namespace",
                    "arc-runners",
                    "--snapshot",
                    str(snapshot_path),
                    "--verify-oidc",
                    "--aws-region",
                    "",
                    "--output",
                    "json",
                ]
            )
    finally:
        lifecycle.AwsIdentityVerifier = original_identity  # type: ignore[misc]

    expect(exit_code == 0, "Empty region values should not cause the CLI to fail")
    expect(captured.get("region") is None, "Empty region should be normalised to None")
    expect(stderr.getvalue() == "", "No stderr output expected on success")


def test_cli_reports_error_when_identity_fails(tmp_path: Path) -> None:
    snapshot: dict[str, Any] = {
        "iterations": [
            {"pods": [], "runners": []},
        ]
    }
    snapshot_path = tmp_path / "scenario.json"
    snapshot_path.write_text(json.dumps(snapshot))

    class _FailingIdentityVerifier:
        def __init__(self, **_: Any) -> None:
            pass

        def verify(self) -> lifecycle.AwsIdentitySummary:
            raise RuntimeError("AWS CLI executable 'aws' was not found on PATH")

    original_identity = lifecycle.AwsIdentityVerifier
    lifecycle.AwsIdentityVerifier = _FailingIdentityVerifier  # type: ignore[misc,assignment]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = lifecycle.main(
                [
                    "--owner",
                    "Hotpass",
                    "--repository",
                    "pipeline",
                    "--scale-set",
                    "hotpass-arc",
                    "--namespace",
                    "arc-runners",
                    "--snapshot",
                    str(snapshot_path),
                    "--verify-oidc",
                    "--output",
                    "text",
                ]
            )
    finally:
        lifecycle.AwsIdentityVerifier = original_identity  # type: ignore[misc]

    expect(exit_code == 1, "CLI should exit with failure when identity verification fails")
    expect(
        "Runner scale set is unhealthy" in stdout.getvalue(),
        "CLI should report unhealthy state on failure",
    )
    expect(
        "OIDC verification failed" in stderr.getvalue(),
        "CLI should emit an explanatory stderr message on failure",
    )
