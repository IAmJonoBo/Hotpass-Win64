"""Data versioning utilities using DVC for Hotpass datasets."""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404 - subprocess is required for DVC orchestration
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command with standard CLI defaults."""

    return subprocess.run(  # nosec - explicit command list, shell disabled
        command,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )

VersionType = Literal["major", "minor", "patch"]


@dataclass
class DatasetVersion:
    """Semantic version metadata for a dataset."""

    major: int
    minor: int
    patch: int
    timestamp: str
    checksum: str | None = None
    description: str | None = None

    @property
    def semver(self) -> str:
        """Return semantic version string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, bump_type: VersionType) -> DatasetVersion:
        """Create a new version by bumping the specified component."""
        if bump_type == "major":
            return DatasetVersion(
                major=self.major + 1,
                minor=0,
                patch=0,
                timestamp=datetime.now(UTC).isoformat(),
                checksum=self.checksum,
            )
        elif bump_type == "minor":
            return DatasetVersion(
                major=self.major,
                minor=self.minor + 1,
                patch=0,
                timestamp=datetime.now(UTC).isoformat(),
                checksum=self.checksum,
            )
        else:  # patch
            return DatasetVersion(
                major=self.major,
                minor=self.minor,
                patch=self.patch + 1,
                timestamp=datetime.now(UTC).isoformat(),
                checksum=self.checksum,
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetVersion:
        """Create DatasetVersion from dictionary."""
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class DVCManager:
    """Manager for DVC operations and dataset versioning."""

    def __init__(self, repo_root: Path):
        """Initialize DVC manager.

        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = repo_root
        self.dvc_dir = repo_root / ".dvc"
        self.version_file = repo_root / ".dvc" / "versions.json"

    def is_initialized(self) -> bool:
        """Check if DVC is initialized in the repository."""
        return self.dvc_dir.exists() and (self.dvc_dir / "config").exists()

    def initialize(self) -> bool:
        """Initialize DVC in the repository.

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            if self.is_initialized():
                logger.info("DVC already initialized")
                return True

            result = _run_command(["dvc", "init"], cwd=self.repo_root)

            if result.returncode == 0:
                logger.info("DVC initialized successfully")
                return True
            else:
                logger.warning(f"DVC init failed: {result.stderr}")
                return False

        except FileNotFoundError:
            logger.error("DVC not installed. Install with: pip install 'dvc[s3]'")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize DVC: {e}")
            return False

    def add_path(self, path: Path) -> bool:
        """Add a path to DVC tracking.

        Args:
            path: Path to track with DVC

        Returns:
            True if successful, False otherwise
        """
        if not self.is_initialized():
            logger.error("DVC not initialized. Run initialize() first.")
            return False

        try:
            result = _run_command(["dvc", "add", str(path)], cwd=self.repo_root)

            if result.returncode == 0:
                logger.info(f"Added {path} to DVC tracking")
                return True
            else:
                logger.warning(f"DVC add failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to add path to DVC: {e}")
            return False

    def get_version(self, dataset_name: str = "refined_data") -> DatasetVersion:
        """Get the current version for a dataset.

        Args:
            dataset_name: Name of the dataset

        Returns:
            Current DatasetVersion
        """
        if not self.version_file.exists():
            return DatasetVersion(
                major=0, minor=1, patch=0, timestamp=datetime.now(UTC).isoformat()
            )

        try:
            with open(self.version_file) as f:
                versions = json.load(f)

            if dataset_name in versions:
                return DatasetVersion.from_dict(versions[dataset_name])

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to read version file: {e}")

        return DatasetVersion(major=0, minor=1, patch=0, timestamp=datetime.now(UTC).isoformat())

    def set_version(
        self,
        version: DatasetVersion,
        dataset_name: str = "refined_data",
    ) -> bool:
        """Set the version for a dataset.

        Args:
            version: DatasetVersion to set
            dataset_name: Name of the dataset

        Returns:
            True if successful, False otherwise
        """
        try:
            self.version_file.parent.mkdir(parents=True, exist_ok=True)

            versions = {}
            if self.version_file.exists():
                with open(self.version_file) as f:
                    versions = json.load(f)

            versions[dataset_name] = version.to_dict()

            with open(self.version_file, "w") as f:
                json.dump(versions, f, indent=2)

            logger.info(f"Set version {version.semver} for {dataset_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to set version: {e}")
            return False

    def tag_version(
        self,
        version: DatasetVersion,
        dataset_name: str = "refined_data",
    ) -> bool:
        """Create a DVC and git tag for a dataset version.

        Args:
            version: DatasetVersion to tag
            dataset_name: Name of the dataset

        Returns:
            True if successful, False otherwise
        """
        tag_name = f"{dataset_name}-v{version.semver}"

        try:
            result = _run_command(
                [
                    "git",
                    "tag",
                    "-a",
                    tag_name,
                    "-m",
                    f"Dataset {dataset_name} version {version.semver}",
                ],
                cwd=self.repo_root,
            )

            if result.returncode == 0:
                logger.info(f"Created tag {tag_name}")
                return True
            else:
                logger.warning(f"Failed to create tag: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to tag version: {e}")
            return False

    def push_metadata(self) -> bool:
        """Push DVC metadata to configured remote.

        Returns:
            True if successful, False otherwise
        """
        if not self.is_initialized():
            logger.error("DVC not initialized")
            return False

        try:
            result = _run_command(["dvc", "push"], cwd=self.repo_root)

            if result.returncode == 0:
                logger.info("DVC push successful")
                return True
            else:
                logger.warning(f"DVC push failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to push DVC metadata: {e}")
            return False

    def status(self) -> dict[str, Any]:
        """Get DVC status information.

        Returns:
            Dictionary with status information
        """
        if not self.is_initialized():
            return {"initialized": False, "tracked_files": []}

        try:
            result = _run_command(["dvc", "status"], cwd=self.repo_root)

            return {
                "initialized": True,
                "status_output": result.stdout,
                "has_changes": result.returncode != 0,
            }

        except Exception as e:
            logger.error(f"Failed to get DVC status: {e}")
            return {"initialized": True, "error": str(e)}


def record_version_metadata(
    output_path: Path,
    version: DatasetVersion,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Record version metadata alongside the output file.

    Args:
        output_path: Path to the output file
        version: DatasetVersion to record
        metadata: Optional additional metadata

    Returns:
        Path to the metadata file
    """
    metadata_path = output_path.parent / f"{output_path.stem}.version.json"

    version_data = version.to_dict()
    if metadata:
        version_data["metadata"] = metadata

    with open(metadata_path, "w") as f:
        json.dump(version_data, f, indent=2)

    logger.info(f"Recorded version metadata to {metadata_path}")
    return metadata_path


__all__ = [
    "DatasetVersion",
    "DVCManager",
    "VersionType",
    "record_version_metadata",
]
