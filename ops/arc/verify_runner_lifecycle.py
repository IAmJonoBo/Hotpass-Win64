"""Utilities that assert GitHub ARC runner scale sets recycle pods cleanly."""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess  # nosec B404 - required for kubectl CLI interaction
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast

import requests


@dataclass(frozen=True)
class AwsIdentitySummary:
    account: str
    arn: str
    user_id: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {
            "account": self.account,
            "arn": self.arn,
            "user_id": self.user_id,
            "source": self.source,
        }


class _StsClient(Protocol):
    def get_caller_identity(
        self,
    ) -> Mapping[str, Any]:  # pragma: no cover - protocol definition
        """Return the AWS identity metadata."""


class _Boto3Session(Protocol):
    def client(
        self, service_name: str, region_name: str | None = None
    ) -> _StsClient:  # pragma: no cover - protocol definition
        """Construct a boto3 client."""


class _Boto3SessionModule(Protocol):
    def Session(self, **kwargs: Any) -> _Boto3Session:  # pragma: no cover - protocol definition
        """Return a boto3 session instance."""


class _Boto3Module(Protocol):
    session: _Boto3SessionModule  # pragma: no cover - protocol attribute


class AwsIdentityVerifier:
    """Resolve the AWS identity attached to the current credentials."""

    def __init__(
        self,
        *,
        region: str | None = None,
        profile: str | None = None,
        boto3_loader: Callable[[], ModuleType | _Boto3Module] | None = None,
        run_command: CommandRunner | None = None,
    ) -> None:
        self.region = region
        self.profile = profile
        self._load_boto3 = boto3_loader or self._import_boto3
        self._run_command = run_command or self._default_run_command

    @staticmethod
    def _import_boto3() -> ModuleType:
        return importlib.import_module("boto3")

    @staticmethod
    def _default_run_command(args: list[str]) -> str:
        result = subprocess.run(args, capture_output=True, check=True, text=True)  # nosec B603
        return result.stdout.strip()

    def verify(self) -> AwsIdentitySummary:
        boto3_module: ModuleType | _Boto3Module | None
        try:
            boto3_module = self._load_boto3()
        except ModuleNotFoundError:
            boto3_module = None
        except ImportError:
            boto3_module = None
        if boto3_module is not None:
            try:
                session_kwargs: dict[str, Any] = {}
                if self.profile:
                    session_kwargs["profile_name"] = self.profile
                session_factory = getattr(boto3_module, "session", None)
                session_ctor = getattr(session_factory, "Session", None)
                if not callable(session_ctor):
                    raise AttributeError("boto3 session factory missing")
                session = cast(_Boto3Session, session_ctor(**session_kwargs))
                client = session.client("sts", region_name=self.region)
                response = client.get_caller_identity()
                return AwsIdentitySummary(
                    account=str(response.get("Account", "")),
                    arn=str(response.get("Arn", "")),
                    user_id=str(response.get("UserId", "")),
                    source="boto3",
                )
            except Exception:
                boto3_module = None
        command = ["aws"]
        if self.profile:
            command.extend(["--profile", self.profile])
        command.extend(["sts", "get-caller-identity", "--output", "json"])
        if self.region:
            command.extend(["--region", self.region])
        try:
            raw_output = self._run_command(command)
        except FileNotFoundError as exc:  # pragma: no cover - covered via tests
            raise RuntimeError("AWS CLI executable 'aws' was not found on PATH") from exc
        except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive guard
            stderr = exc.stderr.strip() if exc.stderr else ""
            message = f"AWS CLI failed with exit code {exc.returncode}"
            if stderr:
                message = f"{message}: {stderr}"
            raise RuntimeError(message) from exc
        output = raw_output.strip()
        if not output:
            raise RuntimeError("AWS CLI returned empty output while resolving identity")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError("AWS CLI output is not valid JSON") from exc
        return AwsIdentitySummary(
            account=str(payload.get("Account", "")),
            arn=str(payload.get("Arn", "")),
            user_id=str(payload.get("UserId", "")),
            source="aws-cli",
        )


class CommandRunner(Protocol):
    def __call__(self, args: list[str]) -> str:  # pragma: no cover - protocol
        """Execute ``args`` and return the command's stdout."""


@dataclass(frozen=True)
class RunnerStatus:
    name: str
    busy: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> RunnerStatus:
        return cls(name=payload.get("name", "unknown"), busy=bool(payload.get("busy", False)))


class RunnerLifecycleVerifier:
    """Checks a RunnerScaleSet for leftover pods or busy runners."""

    def __init__(
        self,
        *,
        owner: str,
        repository: str,
        scale_set: str,
        namespace: str,
        session: requests.Session | None = None,
        run_command: CommandRunner | None = None,
        now: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        timeout_seconds: float = 600.0,
        poll_interval: float = 10.0,
    ) -> None:
        self.owner = owner
        self.repository = repository
        self.scale_set = scale_set
        self.namespace = namespace
        self.session = session or requests.Session()
        self._run_command = run_command or self._default_run_command
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval

    @staticmethod
    def _default_run_command(args: list[str]) -> str:
        result = subprocess.run(args, capture_output=True, check=True, text=True)  # nosec B603
        return result.stdout.strip()

    def _list_runner_pods(self) -> list[str]:
        command = [
            "kubectl",
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            f"actions.github.com/scale-set-name={self.scale_set}",
            "--no-headers",
        ]
        output = self._run_command(command)
        return [line for line in output.splitlines() if line.strip()]

    def _fetch_runner_status(self) -> list[RunnerStatus]:
        url = f"https://api.github.com/repos/{self.owner}/{self.repository}/actions/runners"
        response = self.session.get(
            url,
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        runners = payload.get("runners", [])
        return [RunnerStatus.from_payload(item) for item in runners]

    def verify(self) -> None:
        deadline = self._now() + self.timeout_seconds
        while self._now() < deadline:
            pods = self._list_runner_pods()
            runners = self._fetch_runner_status()
            busy = [runner for runner in runners if runner.busy]
            if not pods and not busy:
                return
            self._sleep(self.poll_interval)
        raise RuntimeError(
            "Timed out waiting for ARC runner scale set to become idle",
        )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate ARC runner scale set lifecycle",
    )
    parser.add_argument(
        "--owner",
        required=True,
        help="GitHub organisation or user that owns the repository",
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="Repository containing the workflows that use the runners",
    )
    parser.add_argument(
        "--scale-set",
        required=True,
        help="RunnerScaleSet name configured in the cluster",
    )
    parser.add_argument(
        "--namespace",
        default="arc-runners",
        help="Kubernetes namespace hosting the runner pods",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Seconds to wait for the runner to drain",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Seconds between status checks",
    )
    parser.add_argument(
        "--output",
        choices={"text", "json"},
        default="text",
        help="Render mode for verification results",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help=("Optional JSON file describing pods and runner statuses for offline verification"),
    )
    parser.add_argument(
        "--verify-oidc",
        action="store_true",
        help="Also confirm the AWS identity resolved via OIDC",
    )
    parser.add_argument(
        "--aws-region",
        help="Optional AWS region override when verifying the identity",
    )
    parser.add_argument(
        "--aws-profile",
        help="Optional AWS profile name to use for identity verification",
    )
    return parser.parse_args(argv)


def _emit_result(
    success: bool,
    mode: str,
    *,
    identity: AwsIdentitySummary | None = None,
) -> None:
    if mode == "json":
        payload: dict[str, Any] = {"success": success}
        if identity is not None:
            payload["identity"] = identity.as_dict()
        print(json.dumps(payload))
    else:
        state = "healthy" if success else "unhealthy"
        print(f"Runner scale set is {state}")
        if identity is not None:
            print(
                "OIDC identity: "
                f"{identity.arn} (account {identity.account}, source {identity.source})",
            )


@dataclass(frozen=True)
class _LifecycleSnapshot:
    pods: list[str]
    runners: list[dict[str, Any]]


class _SnapshotFeeder:
    def __init__(self, snapshots: list[_LifecycleSnapshot]) -> None:
        self._snapshots = snapshots
        self._index = 0

    def pods_output(self) -> str:
        if self._index >= len(self._snapshots):
            raise RuntimeError("Snapshot scenario exhausted while listing pods")
        return "\n".join(self._snapshots[self._index].pods)

    def runner_payload(self) -> dict[str, Any]:
        if self._index >= len(self._snapshots):
            raise RuntimeError("Snapshot scenario exhausted while fetching runners")
        payload = {
            "total_count": len(self._snapshots[self._index].runners),
            "runners": self._snapshots[self._index].runners,
        }
        self._index += 1
        return payload


class _SnapshotResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:  # pragma: no cover - mirrors requests API
        return None


class _SnapshotSession:
    def __init__(self, feeder: _SnapshotFeeder) -> None:
        self._feeder = feeder

    def get(  # noqa: D401 - request signature follows requests.Session.get
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _SnapshotResponse:
        return _SnapshotResponse(self._feeder.runner_payload())


def _load_snapshots(path: Path) -> list[_LifecycleSnapshot]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if isinstance(raw, dict):
        snapshots = raw.get("iterations")
    else:
        snapshots = raw
    if not isinstance(snapshots, list):
        msg = 'Snapshot file must contain a list or {"iterations": [...]}'
        raise ValueError(msg)
    parsed: list[_LifecycleSnapshot] = []
    for index, item in enumerate(snapshots):
        if not isinstance(item, dict):
            raise ValueError(f"Snapshot at index {index} is not an object")
        pods_raw = item.get("pods", [])
        runners_raw = item.get("runners", [])
        if not isinstance(pods_raw, list) or not isinstance(runners_raw, list):
            raise ValueError(
                "Snapshot entries must include 'pods' and 'runners' lists",
            )
        pods = [str(pod) for pod in pods_raw]
        runners: list[dict[str, Any]] = []
        for runner in runners_raw:
            if not isinstance(runner, dict):
                raise ValueError(
                    f"Runner entry at snapshot {index} must be an object",
                )
            name = str(runner.get("name", "unknown"))
            busy = bool(runner.get("busy", False))
            runners.append({"name": name, "busy": busy})
        parsed.append(_LifecycleSnapshot(pods=pods, runners=runners))
    if not parsed:
        raise ValueError("Snapshot file must include at least one iteration")
    return parsed


def _build_snapshot_verifier(
    args: argparse.Namespace,
    snapshots: list[_LifecycleSnapshot],
) -> RunnerLifecycleVerifier:
    feeder = _SnapshotFeeder(snapshots)

    def _run_command(_: list[str]) -> str:
        return feeder.pods_output()

    session = cast(requests.Session, _SnapshotSession(feeder))

    return RunnerLifecycleVerifier(
        owner=args.owner,
        repository=args.repository,
        scale_set=args.scale_set,
        namespace=args.namespace,
        session=session,
        run_command=cast(CommandRunner, _run_command),
        now=time.monotonic,
        sleep=lambda _: None,
        timeout_seconds=args.timeout,
        poll_interval=args.poll_interval,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.snapshot is not None:
        snapshots = _load_snapshots(args.snapshot)
        verifier = _build_snapshot_verifier(args, snapshots)
    else:
        verifier = RunnerLifecycleVerifier(
            owner=args.owner,
            repository=args.repository,
            scale_set=args.scale_set,
            namespace=args.namespace,
            timeout_seconds=args.timeout,
            poll_interval=args.poll_interval,
        )
    identity_summary: AwsIdentitySummary | None = None
    try:
        verifier.verify()
    except Exception as exc:  # noqa: BLE001 - surfaced to the CLI
        _emit_result(False, args.output)
        print(str(exc), file=sys.stderr)
        return 1
    region = args.aws_region or None
    profile = args.aws_profile or None
    if args.verify_oidc:
        identity_verifier = AwsIdentityVerifier(
            region=region,
            profile=profile,
        )
        try:
            identity_summary = identity_verifier.verify()
        except Exception as exc:  # noqa: BLE001 - surfaced to the CLI
            _emit_result(False, args.output)
            print(f"OIDC verification failed: {exc}", file=sys.stderr)
            return 1
    _emit_result(True, args.output, identity=identity_summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
