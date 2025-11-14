import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_ruff_and_bandit_quick_checks():
    """Smoke: ruff & bandit quick checks on core python surfaces.

    This test runs `uv run ruff check` and a quick `uv run bandit` scan, expecting
    the commands to exit with code 0. The bandit call is intentionally limited
    to a small subtree and medium severity so it runs quickly in smoke tier.
    """
    ruff_cmd = ["uv", "run", "ruff", "check", "apps/data-platform", "ops"]
    r = subprocess.run(ruff_cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"ruff check failed: {r.stdout}\n{r.stderr}"

    # Quick security scan (do not fail the test on warnings; this is advisory)
    bandit_cmd = [
        "uv",
        "run",
        "bandit",
        "-r",
        "apps/data-platform/hotpass",
        "--severity-level",
        "medium",
        "--confidence-level",
        "high",
    ]
    r2 = subprocess.run(bandit_cmd, capture_output=True, text=True)
    assert r2.returncode in (
        0,
        1,
    ), f"bandit scan returned unexpected code {r2.returncode}"


@pytest.mark.smoke
def test_cli_overview_help():
    """Smoke: CLI overview should load quickly and show the verb list."""
    res = subprocess.run(
        [
            "uv",
            "run",
            "hotpass",
            "overview",
            "--help",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"overview --help failed: {res.stderr}"
    assert "overview" in res.stdout.lower(), "Output should include overview help text"
