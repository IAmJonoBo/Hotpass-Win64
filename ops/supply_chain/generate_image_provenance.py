"""Generate a provenance statement for locally built container images."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def inspect_image(image: str) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not payload:
        raise RuntimeError(f"No metadata returned for image {image}")
    return payload[0]


def normalise_digest(digest: str) -> str:
    return digest.split(":", 1)[1] if ":" in digest else digest


def build_statement(image: str) -> dict[str, Any]:
    metadata = inspect_image(image)
    digest = normalise_digest(metadata.get("Id", ""))
    repo_digests = metadata.get("RepoDigests") or []
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": image,
                "digest": {"sha256": digest},
                "annotations": {"repoDigests": repo_digests},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildType": "https://github.com/IAmJonoBo/Hotpass/.github/workflows/quality-gates.yml@v1",
            "builder": {"id": "https://github.com/IAmJonoBo/Hotpass/actions"},
            "buildConfig": {
                "image": image,
                "repoDigests": repo_digests,
            },
            "metadata": {
                "buildStartedOn": datetime.now(UTC).isoformat(),
                "buildFinishedOn": datetime.now(UTC).isoformat(),
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Fully qualified image reference")
    parser.add_argument("--output", type=Path, default=Path("dist/provenance"))
    parser.add_argument("--filename", default="provenance.json")
    args = parser.parse_args()

    statement = build_statement(args.image)
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / args.filename
    destination.write_text(json.dumps(statement, indent=2), encoding="utf-8")
    print(f"Provenance statement written to {destination}")


if __name__ == "__main__":
    main()
