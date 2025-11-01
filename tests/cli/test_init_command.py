from __future__ import annotations

from pathlib import Path

import pytest
from hotpass import cli


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_init_bootstraps_workspace(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "workspace"
    exit_code = cli.main(["init", "--path", str(target)])
    captured = capsys.readouterr()

    expect(exit_code == 0, "init should exit successfully")
    expect("Hotpass workspace initialised" in captured.out, "success message missing")

    expected_directories = {
        target / "config",
        target / "config" / "profiles",
        target / "data",
        target / "dist",
        target / "prefect",
        target / "prefect" / "deployments",
    }
    for directory in expected_directories:
        expect(directory.exists(), f"missing directory: {directory}")

    config_file = target / "config" / "pipeline.quickstart.toml"
    profile_file = target / "config" / "profiles" / "quickstart.toml"
    prefect_file = target / "prefect" / "deployments" / "quickstart.yaml"
    data_readme = target / "data" / "README.md"

    expect(
        "Bootstrap Hotpass workspace" in config_file.read_text(),
        "config template not written",
    )
    expect("quickstart" in profile_file.read_text(), "profile template not written")
    expect("verify-environment" in prefect_file.read_text(), "prefect template not written")
    expect("drop spreadsheets" in data_readme.read_text(), "data README missing content")


def test_init_requires_force_for_non_empty_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    (target / "placeholder.txt").write_text("existing", encoding="utf-8")

    exit_code = cli.main(["init", "--path", str(target)])
    captured = capsys.readouterr()

    expect(exit_code == 1, "init should fail when directory is not empty")
    expect(
        "not empty" in captured.err or "not empty" in captured.out,
        "failure message missing",
    )
    expect((target / "config").exists() is False, "should not create files on failure")


def test_init_force_overwrites_existing_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "workspace"
    config_file = target / "config" / "pipeline.quickstart.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("placeholder", encoding="utf-8")

    exit_code = cli.main(["init", "--path", str(target), "--force"])
    captured = capsys.readouterr()

    expect(exit_code == 0, "init should succeed with --force")
    expect("Generated artefacts" in captured.out, "expected overwrite summary")
    expect("Bootstrap Hotpass workspace" in config_file.read_text(), "file not overwritten")
