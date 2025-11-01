"""Tests for DVC-based data versioning."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hotpass.versioning import (DatasetVersion, DVCManager,
                                record_version_metadata)

pytestmark = pytest.mark.bandwidth("smoke")


def expect(condition: bool, message: str) -> None:
    """Assert-free validation helper."""
    if not condition:
        raise AssertionError(message)


class TestDatasetVersion:
    """Tests for DatasetVersion class."""

    def test_semver_property(self) -> None:
        """Test semantic version string generation."""
        version = DatasetVersion(
            major=1, minor=2, patch=3, timestamp="2025-01-01T00:00:00Z"
        )
        expect(
            version.semver == "1.2.3",
            f"Expected semver '1.2.3', got '{version.semver}'",
        )

    def test_bump_major(self) -> None:
        """Test major version bump resets minor and patch."""
        version = DatasetVersion(
            major=1, minor=2, patch=3, timestamp="2025-01-01T00:00:00Z"
        )
        new_version = version.bump("major")

        expect(new_version.major == 2, f"Expected major=2, got {new_version.major}")
        expect(new_version.minor == 0, f"Expected minor=0, got {new_version.minor}")
        expect(new_version.patch == 0, f"Expected patch=0, got {new_version.patch}")

    def test_bump_minor(self) -> None:
        """Test minor version bump resets patch."""
        version = DatasetVersion(
            major=1, minor=2, patch=3, timestamp="2025-01-01T00:00:00Z"
        )
        new_version = version.bump("minor")

        expect(new_version.major == 1, f"Expected major=1, got {new_version.major}")
        expect(new_version.minor == 3, f"Expected minor=3, got {new_version.minor}")
        expect(new_version.patch == 0, f"Expected patch=0, got {new_version.patch}")

    def test_bump_patch(self) -> None:
        """Test patch version bump."""
        version = DatasetVersion(
            major=1, minor=2, patch=3, timestamp="2025-01-01T00:00:00Z"
        )
        new_version = version.bump("patch")

        expect(new_version.major == 1, f"Expected major=1, got {new_version.major}")
        expect(new_version.minor == 2, f"Expected minor=2, got {new_version.minor}")
        expect(new_version.patch == 4, f"Expected patch=4, got {new_version.patch}")

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization round-trip."""
        version = DatasetVersion(
            major=1,
            minor=2,
            patch=3,
            timestamp="2025-01-01T00:00:00Z",
            checksum="abc123",
            description="Test version",
        )

        version_dict = version.to_dict()
        restored = DatasetVersion.from_dict(version_dict)

        expect(
            restored.major == version.major,
            f"Expected major={version.major}, got {restored.major}",
        )
        expect(
            restored.minor == version.minor,
            f"Expected minor={version.minor}, got {restored.minor}",
        )
        expect(
            restored.patch == version.patch,
            f"Expected patch={version.patch}, got {restored.patch}",
        )
        expect(
            restored.checksum == version.checksum,
            f"Expected checksum={version.checksum}, got {restored.checksum}",
        )
        expect(
            restored.description == version.description,
            f"Expected description={version.description}, got {restored.description}",
        )


class TestDVCManager:
    """Tests for DVCManager class."""

    def test_is_initialized_when_dvc_dir_exists(self, tmp_path: Path) -> None:
        """Test DVC initialization detection."""
        dvc_dir = tmp_path / ".dvc"
        dvc_dir.mkdir()
        (dvc_dir / "config").touch()

        manager = DVCManager(tmp_path)
        expect(
            manager.is_initialized(),
            "Expected is_initialized to return True when .dvc/config exists",
        )

    def test_is_not_initialized_when_dvc_dir_missing(self, tmp_path: Path) -> None:
        """Test DVC initialization detection when not initialized."""
        manager = DVCManager(tmp_path)
        expect(
            not manager.is_initialized(),
            "Expected is_initialized to return False when .dvc dir missing",
        )

    @patch("hotpass.versioning.subprocess.run")
    def test_initialize_creates_dvc_structure(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test DVC initialization."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        manager = DVCManager(tmp_path)
        result = manager.initialize()

        expect(result, "Expected initialize to return True")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        expect(
            call_args[0][0] == ["dvc", "init"],
            f"Expected dvc init command, got {call_args[0][0]}",
        )

    @patch("hotpass.versioning.subprocess.run")
    def test_initialize_handles_dvc_not_installed(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test DVC initialization when DVC is not installed."""
        mock_run.side_effect = FileNotFoundError("dvc not found")

        manager = DVCManager(tmp_path)
        result = manager.initialize()

        expect(not result, "Expected initialize to return False when DVC not found")

    @patch("hotpass.versioning.subprocess.run")
    def test_add_path_tracks_file(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test adding a path to DVC tracking."""
        dvc_dir = tmp_path / ".dvc"
        dvc_dir.mkdir()
        (dvc_dir / "config").touch()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        manager = DVCManager(tmp_path)
        test_file = tmp_path / "data.xlsx"
        test_file.touch()

        result = manager.add_path(test_file)

        expect(result, "Expected add_path to return True")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        expect(
            "dvc" in call_args[0][0] and "add" in call_args[0][0],
            f"Expected dvc add command, got {call_args[0][0]}",
        )

    def test_get_version_returns_default_when_no_file(self, tmp_path: Path) -> None:
        """Test getting version when no version file exists."""
        manager = DVCManager(tmp_path)
        version = manager.get_version()

        expect(version.major == 0, f"Expected major=0, got {version.major}")
        expect(version.minor == 1, f"Expected minor=1, got {version.minor}")
        expect(version.patch == 0, f"Expected patch=0, got {version.patch}")

    def test_set_and_get_version_round_trip(self, tmp_path: Path) -> None:
        """Test setting and getting version."""
        manager = DVCManager(tmp_path)

        version = DatasetVersion(
            major=1,
            minor=2,
            patch=3,
            timestamp="2025-01-01T00:00:00Z",
            checksum="abc123",
            description="Test version",
        )

        result = manager.set_version(version, "test_dataset")
        expect(result, "Expected set_version to return True")

        retrieved = manager.get_version("test_dataset")
        expect(
            retrieved.semver == version.semver,
            f"Expected semver {version.semver}, got {retrieved.semver}",
        )
        expect(
            retrieved.checksum == version.checksum,
            f"Expected checksum {version.checksum}, got {retrieved.checksum}",
        )

    def test_set_version_creates_directory(self, tmp_path: Path) -> None:
        """Test that set_version creates .dvc directory if needed."""
        manager = DVCManager(tmp_path)

        version = DatasetVersion(
            major=1, minor=0, patch=0, timestamp="2025-01-01T00:00:00Z"
        )

        result = manager.set_version(version)
        expect(result, "Expected set_version to return True")
        expect(manager.version_file.exists(), "Expected version file to be created")

    def test_get_version_handles_corrupt_json(self, tmp_path: Path) -> None:
        """Test that get_version handles corrupted version file."""
        manager = DVCManager(tmp_path)
        manager.version_file.parent.mkdir(parents=True, exist_ok=True)

        with open(manager.version_file, "w") as f:
            f.write("invalid json {")

        version = manager.get_version()
        expect(
            version.major == 0, f"Expected major=0 on corrupt file, got {version.major}"
        )
        expect(
            version.minor == 1, f"Expected minor=1 on corrupt file, got {version.minor}"
        )

    @patch("hotpass.versioning.subprocess.run")
    def test_tag_version_creates_git_tag(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test creating a git tag for a version."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        manager = DVCManager(tmp_path)
        version = DatasetVersion(
            major=1, minor=2, patch=3, timestamp="2025-01-01T00:00:00Z"
        )

        result = manager.tag_version(version, "test_dataset")
        expect(result, "Expected tag_version to return True")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        expect(
            "git" in call_args[0][0] and "tag" in call_args[0][0],
            f"Expected git tag command, got {call_args[0][0]}",
        )
        expect(
            "test_dataset-v1.2.3" in call_args[0][0],
            f"Expected tag name in command, got {call_args[0][0]}",
        )

    @patch("hotpass.versioning.subprocess.run")
    def test_push_metadata_requires_initialization(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test that push_metadata checks for DVC initialization."""
        manager = DVCManager(tmp_path)
        result = manager.push_metadata()

        expect(
            not result, "Expected push_metadata to return False when not initialized"
        )
        mock_run.assert_not_called()

    @patch("hotpass.versioning.subprocess.run")
    def test_push_metadata_calls_dvc_push(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test pushing DVC metadata."""
        dvc_dir = tmp_path / ".dvc"
        dvc_dir.mkdir()
        (dvc_dir / "config").touch()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        manager = DVCManager(tmp_path)
        result = manager.push_metadata()

        expect(result, "Expected push_metadata to return True")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        expect(
            call_args[0][0] == ["dvc", "push"],
            f"Expected dvc push command, got {call_args[0][0]}",
        )

    def test_status_returns_not_initialized(self, tmp_path: Path) -> None:
        """Test status when DVC is not initialized."""
        manager = DVCManager(tmp_path)
        status = manager.status()

        expect(not status["initialized"], "Expected initialized=False in status")
        expect("tracked_files" in status, "Expected tracked_files in status")

    @patch("hotpass.versioning.subprocess.run")
    def test_status_returns_initialized(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test status when DVC is initialized."""
        dvc_dir = tmp_path / ".dvc"
        dvc_dir.mkdir()
        (dvc_dir / "config").touch()

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="clean")

        manager = DVCManager(tmp_path)
        status = manager.status()

        expect(status["initialized"], "Expected initialized=True in status")
        expect("status_output" in status, "Expected status_output in status")


class TestRecordVersionMetadata:
    """Tests for record_version_metadata function."""

    def test_records_metadata_file(self, tmp_path: Path) -> None:
        """Test recording version metadata to file."""
        output_path = tmp_path / "refined_data.xlsx"
        output_path.touch()

        version = DatasetVersion(
            major=1,
            minor=2,
            patch=3,
            timestamp="2025-01-01T00:00:00Z",
            checksum="abc123",
        )

        metadata_path = record_version_metadata(output_path, version)

        expect(metadata_path.exists(), "Expected metadata file to be created")
        expect(
            metadata_path.name == "refined_data.version.json",
            f"Expected refined_data.version.json, got {metadata_path.name}",
        )

        with open(metadata_path) as f:
            data = json.load(f)

        expect(data["major"] == 1, f"Expected major=1 in metadata, got {data['major']}")
        expect(data["minor"] == 2, f"Expected minor=2 in metadata, got {data['minor']}")
        expect(data["patch"] == 3, f"Expected patch=3 in metadata, got {data['patch']}")
        expect(
            data["checksum"] == "abc123",
            f"Expected checksum=abc123 in metadata, got {data['checksum']}",
        )

    def test_records_additional_metadata(self, tmp_path: Path) -> None:
        """Test recording version with additional metadata."""
        output_path = tmp_path / "data.xlsx"
        output_path.touch()

        version = DatasetVersion(
            major=1, minor=0, patch=0, timestamp="2025-01-01T00:00:00Z"
        )

        additional = {"pipeline": "enhanced", "records": 1000}
        metadata_path = record_version_metadata(output_path, version, additional)

        with open(metadata_path) as f:
            data = json.load(f)

        expect("metadata" in data, "Expected metadata field in output")
        expect(
            data["metadata"]["pipeline"] == "enhanced",
            f"Expected pipeline=enhanced, got {data['metadata'].get('pipeline')}",
        )
        expect(
            data["metadata"]["records"] == 1000,
            f"Expected records=1000, got {data['metadata'].get('records')}",
        )
