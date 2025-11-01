"""Project-specific Python sitecustomize hooks.

This module registers a shim build backend for ``uv.core.build`` so that
PEP 517 tooling can import the requested backend even when the installed
``uv`` distribution does not yet expose that module. The shim forwards the
build hooks to the ``uv`` executable, matching the behaviour of the legacy
``uv-build`` backend.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from shutil import which
from types import ModuleType
from typing import Any

BACKEND_MODULE = "uv.core.build"


def _warn_config_settings(config_settings: Mapping[Any, Any] | None = None) -> None:
    if config_settings:
        print("Warning: Config settings are not supported", file=sys.stderr)


def _call(args: Sequence[str], config_settings: Mapping[Any, Any] | None = None) -> str:
    _warn_config_settings(config_settings)

    uv_bin = which("uv")
    backend_args: list[str]
    if uv_bin is not None:
        backend_args = ["build-backend"]
    else:
        uv_bin = which("uv-build")
        backend_args = []

    if uv_bin is None:
        raise RuntimeError("uv executable was not properly installed")

    result = subprocess.run(
        [uv_bin, *backend_args, *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        print(
            f"{uv_bin} subprocess did not return a filename on stdout",
            file=sys.stderr,
        )
        sys.exit(1)

    # Forward any additional output to stdout for visibility, keeping the final
    # path return value for the PEP 517 contract.
    for extra in lines[:-1]:
        print(extra)
    return lines[-1].strip()


def build_sdist(sdist_directory: str, config_settings: Mapping[Any, Any] | None = None) -> str:
    return _call(["build-sdist", sdist_directory], config_settings)


def build_wheel(
    wheel_directory: str,
    config_settings: Mapping[Any, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    args = ["build-wheel", wheel_directory]
    if metadata_directory:
        args.append(metadata_directory)
    return _call(args, config_settings)


def build_editable(
    wheel_directory: str,
    config_settings: Mapping[Any, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    args = ["build-editable", wheel_directory]
    if metadata_directory:
        args.append(metadata_directory)
    return _call(args, config_settings)


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: Mapping[Any, Any] | None = None
) -> str:
    return _call(["prepare-metadata-for-build-wheel", metadata_directory], config_settings)


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: Mapping[Any, Any] | None = None
) -> str:
    return _call(["prepare-metadata-for-build-editable", metadata_directory], config_settings)


def get_requires_for_build_sdist(
    config_settings: Mapping[Any, Any] | None = None,
) -> Sequence[str]:
    _warn_config_settings(config_settings)
    return []


def get_requires_for_build_wheel(
    config_settings: Mapping[Any, Any] | None = None,
) -> Sequence[str]:
    _warn_config_settings(config_settings)
    return []


def get_requires_for_build_editable(
    config_settings: Mapping[Any, Any] | None = None,
) -> Sequence[str]:
    _warn_config_settings(config_settings)
    return []


# Register shim modules so ``import uv.core.build`` succeeds before the official
# implementation lands in upstream ``uv``.
backend = ModuleType(BACKEND_MODULE)
backend.build_sdist = build_sdist
backend.build_wheel = build_wheel
backend.build_editable = build_editable
backend.prepare_metadata_for_build_wheel = prepare_metadata_for_build_wheel
backend.prepare_metadata_for_build_editable = prepare_metadata_for_build_editable
backend.get_requires_for_build_sdist = get_requires_for_build_sdist
backend.get_requires_for_build_wheel = get_requires_for_build_wheel
backend.get_requires_for_build_editable = get_requires_for_build_editable
backend.__all__ = [
    "build_sdist",
    "build_wheel",
    "build_editable",
    "prepare_metadata_for_build_wheel",
    "prepare_metadata_for_build_editable",
    "get_requires_for_build_sdist",
    "get_requires_for_build_wheel",
    "get_requires_for_build_editable",
]

core = ModuleType("uv.core")
core.__path__ = []  # Mark as namespace-like so import machinery treats it as a package.
core.build = backend

sys.modules.setdefault("uv.core", core)
sys.modules.setdefault(BACKEND_MODULE, backend)

try:
    import uv as _uv  # noqa: F401
except ModuleNotFoundError:
    _uv = None

if _uv is not None and not hasattr(_uv, "core"):
    _uv.core = core  # type: ignore[attr-defined]
