"""Wrapper around mutmut with curated settings for CI."""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys

TARGETS = [
    "apps/data-platform/hotpass/quality.py",
    "apps/data-platform/hotpass/pipeline_enhanced.py",
]


def main() -> None:
    env = {**os.environ, "MUTATE": ",".join(TARGETS)}
    env.setdefault(
        "PYTEST_ADDOPTS",
        "-k 'quality or pipeline_enhanced or contracts' --maxfail=1",
    )

    python_cmd = sys.executable

    subprocess.run([python_cmd, "-m", "coverage", "erase"], check=True, env=env)  # nosec B603
    subprocess.run([python_cmd, "-m", "pytest"], check=True, env=env)  # nosec B603

    command = ["mutmut", "run"]
    subprocess.run(command, check=True, env=env)  # nosec B603

    subprocess.run([python_cmd, "-m", "coverage", "erase"], check=True, env=env)  # nosec B603


if __name__ == "__main__":
    main()
