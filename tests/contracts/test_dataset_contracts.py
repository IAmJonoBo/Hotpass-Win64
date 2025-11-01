"""Tests for dataset contract round-tripping and artefact generation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hotpass import contracts

from tests.helpers.pytest_marks import parametrize


def _find_repo_root() -> Path:
    """Find repository root by looking for pyproject.toml marker."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not find repository root (no pyproject.toml found)")


REPO_ROOT = _find_repo_root()
SCHEMAS_DIR = REPO_ROOT / "schemas"
DOC_PATH = REPO_ROOT / "docs" / "reference" / "schemas.md"


@parametrize(
    "contract",
    contracts.DATASET_CONTRACTS,
    ids=lambda contract: contract.name,
)
def test_contract_roundtrip(contract: contracts.DatasetContract) -> None:
    """Verify each contract supports model/dataframe round-tripping and schema parity."""

    models = contract.example_models()
    assert models, f"expected example data for {contract.name}"

    dataframe = contract.dataframe_from_models(models)
    validated = contract.dataframe_schema.validate(dataframe)
    roundtripped = contract.models_from_dataframe(validated)

    expected_rows = [model.model_dump(by_alias=True) for model in models]
    actual_rows = [model.model_dump(by_alias=True) for model in roundtripped]
    assert actual_rows == expected_rows

    schema_path = SCHEMAS_DIR / (contract.schema_filename or f"{contract.name}.schema.json")
    expected_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert contract.to_frictionless() == expected_schema


def _extract_last_updated(path: Path) -> date:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("last_updated:"):
            _, value = line.split(":", 1)
            return date.fromisoformat(value.strip())
    raise AssertionError("Documentation missing last_updated front matter")


def test_reference_document_matches_renderer() -> None:
    """Ensure the stored documentation matches the renderer output."""

    last_updated = _extract_last_updated(DOC_PATH)
    rendered = contracts.render_reference_markdown(
        contracts.DATASET_CONTRACTS, last_updated=last_updated
    )
    assert rendered == DOC_PATH.read_text(encoding="utf-8")


def test_regeneration_scripts_are_stable(tmp_path: Path) -> None:
    """Regeneration helpers should reproduce the committed artefacts."""

    schema_dir = tmp_path / "schemas"
    doc_path = tmp_path / "schemas.md"

    generated_schemas = contracts.regenerate_json_schemas(
        schema_dir=schema_dir, contracts=contracts.DATASET_CONTRACTS
    )
    assert generated_schemas, "no schemas were generated"

    for generated in generated_schemas:
        expected = json.loads((SCHEMAS_DIR / generated.name).read_text(encoding="utf-8"))
        actual = json.loads(generated.read_text(encoding="utf-8"))
        assert actual == expected

    last_updated = _extract_last_updated(DOC_PATH)
    generated_doc = contracts.regenerate_reference_doc(
        doc_path=doc_path,
        contracts=contracts.DATASET_CONTRACTS,
        last_updated=last_updated,
    )
    assert generated_doc.read_text(encoding="utf-8") == DOC_PATH.read_text(encoding="utf-8")
