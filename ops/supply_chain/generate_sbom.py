"""Generate CycloneDX SBOM for the Hotpass project."""

from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def generate_sbom(output_dir: Path, filename: str = "hotpass-sbom.json") -> Path:
    """Run cyclonedx-bom to produce an SBOM in JSON format."""

    output_dir.mkdir(parents=True, exist_ok=True)
    sbom_path = output_dir / filename
    command = [
        sys.executable,
        "-m",
        "cyclonedx_py",
        "environment",
        "--of",
        "JSON",
        "-o",
        str(sbom_path),
        "--pyproject",
        str((PROJECT_ROOT / "pyproject.toml").resolve()),
        sys.executable,
    ]
    try:
        subprocess.run(command, check=True)  # nosec B603
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            "cyclonedx_py is not available on the current interpreter."
            " Ensure the 'ci' extra is installed before running the SBOM generator."
        ) from exc
    return sbom_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Generate a CycloneDX SBOM for Hotpass.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/sbom"),
        help="Directory where the SBOM should be written (default: dist/sbom)",
    )
    parser.add_argument(
        "--filename",
        default="hotpass-sbom.json",
        help="Optional filename for the generated SBOM.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for CLI usage."""

    args = parse_args(argv)
    sbom_path = generate_sbom(args.output_dir, args.filename)
    print(f"SBOM written to {sbom_path}")


if __name__ == "__main__":
    main()
