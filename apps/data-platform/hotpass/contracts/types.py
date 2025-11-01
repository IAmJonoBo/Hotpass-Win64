"""Typed dataset contract representations for Hotpass data assets."""

from __future__ import annotations

import json
import keyword
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pandera as pa
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.fields import FieldInfo

__all__ = [
    "FieldContract",
    "DatasetContract",
    "ContractRowModel",
]


_CONTRACT_SCHEMA = "https://frictionlessdata.io/schemas/table-schema.json"

_PYTHON_TYPE_BY_FRICTIONLESS: dict[str, type[Any]] = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
}

_PANDERA_TYPE_BY_FRICTIONLESS: dict[str, pa.extensions.DataType] = {
    "string": pa.String,
    "number": pa.Float,
    "integer": pa.Int,
    "boolean": pa.Bool,
}


def _to_python_identifier(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", value).strip("_").lower()
    if not cleaned:
        cleaned = "value"
    if cleaned[0].isdigit():
        cleaned = f"field_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def _to_pascal_case(value: str) -> str:
    parts = re.split(r"[^0-9a-zA-Z]+", value)
    return "".join(part.capitalize() for part in parts if part)


class ContractRowModel(BaseModel):
    """Base class for dynamically generated contract row models."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)


@dataclass(frozen=True, slots=True)
class FieldContract:
    """A single column definition within a dataset contract."""

    name: str
    field_type: str
    required: bool = False
    description: str | None = None
    example: Any | None = None
    python_name: str | None = None

    def resolved_python_name(self) -> str:
        if self.python_name:
            return self.python_name
        return _to_python_identifier(self.name)

    def to_frictionless(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "type": self.field_type}
        if self.required:
            payload["constraints"] = {"required": True}
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True, slots=True)
class DatasetContract:
    """Dataset contract metadata and helpers for schema/tooling generation."""

    name: str
    title: str
    description: str
    primary_key: tuple[str, ...]
    fields: tuple[FieldContract, ...]
    examples: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    schema_filename: str | None = None
    _row_model: type[ContractRowModel] | None = field(init=False, default=None, repr=False)
    _dataframe_schema: pa.DataFrameSchema | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.schema_filename:
            object.__setattr__(self, "schema_filename", f"{self.name}.schema.json")

    @property
    def row_model(self) -> type[ContractRowModel]:
        """Return a cached Pydantic model for a single dataset row."""

        cached = cast(type[ContractRowModel] | None, object.__getattribute__(self, "_row_model"))
        if cached is not None:
            return cached

        field_definitions: dict[str, tuple[Any, FieldInfo]] = {}
        seen_names: set[str] = set()

        for field_contract in self.fields:
            python_name = field_contract.resolved_python_name()
            while python_name in seen_names:
                python_name = f"{python_name}_"
            seen_names.add(python_name)

            python_type = _PYTHON_TYPE_BY_FRICTIONLESS.get(field_contract.field_type, str)
            default: Any = ... if field_contract.required else None
            annotation: Any = python_type
            if not field_contract.required:
                annotation = cast(Any, python_type | type(None))

            examples = [field_contract.example] if field_contract.example is not None else None

            field_info = Field(
                default,
                alias=field_contract.name,
                description=field_contract.description,
                examples=examples,
            )
            field_definitions[python_name] = (annotation, field_info)

        model = cast(
            type[ContractRowModel],
            create_model(
                f"{_to_pascal_case(self.name)}Row",
                __base__=ContractRowModel,
                **cast(dict[str, Any], field_definitions),
            ),
        )
        object.__setattr__(self, "_row_model", model)
        return model

    @property
    def dataframe_schema(self) -> pa.DataFrameSchema:
        """Return a cached Pandera schema for validating dataframes."""

        cached = object.__getattribute__(self, "_dataframe_schema")
        if cached is not None:
            return cached

        columns: dict[str, pa.Column] = {}
        for field_contract in self.fields:
            dtype = _PANDERA_TYPE_BY_FRICTIONLESS.get(field_contract.field_type)
            if dtype is None:
                dtype = pa.Object
            columns[field_contract.name] = pa.Column(
                dtype,
                required=field_contract.required,
                nullable=not field_contract.required,
                description=field_contract.description,
            )

        schema = pa.DataFrameSchema(columns, coerce=True)
        object.__setattr__(self, "_dataframe_schema", schema)
        return schema

    def to_frictionless(self) -> dict[str, Any]:
        """Serialise the contract to a Frictionless Table Schema mapping."""

        return {
            "$schema": _CONTRACT_SCHEMA,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "primaryKey": list(self.primary_key),
            "fields": [field.to_frictionless() for field in self.fields],
        }

    def example_models(self) -> list[ContractRowModel]:
        """Create row models from configured examples."""

        row_model = self.row_model
        examples: list[ContractRowModel] = []
        for payload in self.examples:
            examples.append(row_model.model_validate(payload))
        return examples

    def dataframe_from_models(
        self, models: Iterable[BaseModel], *, include_optional: bool = True
    ) -> pd.DataFrame:
        """Convert a sequence of row models into a pandas DataFrame."""

        rows: list[dict[str, Any]] = []
        for model in models:
            by_alias = model.model_dump(by_alias=True)
            if not include_optional:
                by_alias = {
                    key: value
                    for key, value in by_alias.items()
                    if value is not None or key in self.primary_key
                }
            rows.append(by_alias)

        if not rows:
            rows = [{field.name: None for field in self.fields}]

        dataframe = pd.DataFrame(rows)
        dataframe = dataframe[[field.name for field in self.fields]]
        return dataframe

    def models_from_dataframe(self, dataframe: pd.DataFrame) -> list[ContractRowModel]:
        """Validate a dataframe and convert rows into contract models."""

        validated = self.dataframe_schema.validate(dataframe.copy())
        row_model = self.row_model
        result: list[ContractRowModel] = []
        for _, row in validated.iterrows():
            payload = {field.name: row.get(field.name) for field in self.fields}
            result.append(row_model.model_validate(payload))
        return result

    def to_dataframe(self) -> pd.DataFrame:
        """Convenience helper returning a dataframe built from example rows."""

        models = self.example_models()
        return self.dataframe_from_models(models)

    def dump_json_schema(self, directory: Path) -> Path:
        """Write the frictionless schema to disk and return the file path."""

        target = directory / (self.schema_filename or f"{self.name}.schema.json")
        payload = json.dumps(self.to_frictionless(), indent=2)
        target.write_text(f"{payload}\n", encoding="utf-8")
        return target

    def to_markdown_table(self) -> str:
        """Render the contract columns as a Markdown table."""

        # Handle empty fields case
        if not self.fields:
            return (
                "| Column | Type | Required | Description |\n"
                "| ------ | ---- | -------- | ----------- |"
            )

        # Calculate column widths for proper alignment
        col_widths = {
            "column": max(len(f"`{f.name}`") for f in self.fields),
            "type": max(len(f.field_type.title()) for f in self.fields),
            "required": len("Required"),
            "description": max(len(f.description or "") for f in self.fields),
        }

        # Ensure minimum widths match the header text
        col_widths["column"] = max(col_widths["column"], len("Column"))
        col_widths["type"] = max(col_widths["type"], len("Type"))
        col_widths["description"] = max(col_widths["description"], len("Description"))

        # Build header
        lines = [
            f"| {'Column'.ljust(col_widths['column'])} | "
            f"{'Type'.ljust(col_widths['type'])} | "
            f"{'Required'.ljust(col_widths['required'])} | "
            f"{'Description'.ljust(col_widths['description'])} |",
            f"| {'-' * col_widths['column']} | "
            f"{'-' * col_widths['type']} | "
            f"{'-' * col_widths['required']} | "
            f"{'-' * col_widths['description']} |",
        ]

        # Build data rows
        for field_contract in self.fields:
            column_name = f"`{field_contract.name}`"
            field_type = field_contract.field_type.title()
            required = "Yes" if field_contract.required else "No"
            description = field_contract.description or ""

            lines.append(
                f"| {column_name.ljust(col_widths['column'])} | "
                f"{field_type.ljust(col_widths['type'])} | "
                f"{required.ljust(col_widths['required'])} | "
                f"{description.ljust(col_widths['description'])} |"
            )

        return "\n".join(lines)

    def example_block(self, index: int = 0) -> str:
        """Return a JSON code block representing an example row."""

        examples = list(self.examples)
        if not examples:
            payload = cast(dict[str, Any], {field.name: None for field in self.fields})
        else:
            payload = dict(examples[min(index, len(examples) - 1)])
        return json.dumps(payload, indent=2, ensure_ascii=False)


def render_reference_markdown(contracts: Sequence[DatasetContract], *, last_updated: date) -> str:
    """Generate the reference documentation page for all dataset contracts."""

    lines: list[str] = [
        "---",
        "title: Dataset schemas",
        "summary: Canonical dataset contracts for Hotpass source and refined tables.",
        f"last_updated: {last_updated.isoformat()}",
        "---",
        "",
        "# Dataset schemas",
        "",
        "```{note}",
        "This page is generated from the dataset contract registry. Run",
        "`python -m hotpass.contracts.generator` to refresh the artefacts.",
        "```",
        "",
    ]

    for contract in contracts:
        lines.extend(
            [
                f"## {contract.title}",
                "",
                contract.description,
                "",
                f"**Primary key:** `{', '.join(contract.primary_key)}`",
                "",
                contract.to_markdown_table(),
                "",
                "### Example",
                "",
                "```json",
                contract.example_block(),
                "```",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"
