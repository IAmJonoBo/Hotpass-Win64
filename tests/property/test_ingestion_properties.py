from __future__ import annotations

import math
import string
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hotpass.normalization import normalize_province, slugify
from hotpass.pipeline import ingestion as ingestion_module
from hotpass.pipeline.config import PipelineConfig
from hotpass.pipeline.ingestion import ingest_sources

from tests.helpers.hypothesis import HealthCheck, SearchStrategy, given, settings, st


def expect(condition: bool, message: str) -> None:
    """Shared assertion helper that mirrors project testing guidance."""

    if not condition:
        pytest.fail(message)


_BASE_COLUMNS = [
    "organization_name",
    "source_dataset",
    "source_record_id",
]

_OPTIONAL_COLUMNS = [
    "province",
    "area",
    "address",
    "category",
    "organization_type",
    "status",
    "website",
    "planes",
    "description",
    "notes",
    "last_interaction_date",
    "priority",
    "contact_names",
    "contact_roles",
    "contact_emails",
    "contact_phones",
]


def _unicode_strings() -> SearchStrategy[str]:
    """Generate messy unicode while filtering control-only payloads."""

    return st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),
            whitelist_categories=(
                "Ll",
                "Lu",
                "Lt",
                "Lo",
                "Nd",
                "Nl",
                "No",
                "Pc",
                "Pd",
                "Pe",
                "Pf",
                "Pi",
                "Po",
                "Ps",
                "Sm",
                "So",
                "Zs",
            ),
        ),
        min_size=1,
        max_size=30,
    )


def _row_strategy() -> SearchStrategy[dict[str, object]]:
    email_local = st.text(string.ascii_lowercase + string.digits, min_size=1, max_size=12)
    phone_digits = st.text(string.digits, min_size=9, max_size=12)
    list_strategy = st.lists(_unicode_strings(), min_size=1, max_size=3)
    return st.fixed_dictionaries(
        {
            "organization_name": _unicode_strings(),
            "source_dataset": st.sampled_from(
                ["Contact Database", "Reachout Database", "SACAA Cleaned"]
            ),
            "source_record_id": st.text(
                string.ascii_letters + string.digits, min_size=1, max_size=12
            ),
            "province": st.one_of(st.none(), _unicode_strings()),
            "area": st.one_of(st.none(), _unicode_strings()),
            "address": st.one_of(st.none(), _unicode_strings()),
            "category": st.one_of(st.none(), _unicode_strings()),
            "organization_type": st.one_of(st.none(), _unicode_strings()),
            "status": st.one_of(st.none(), _unicode_strings()),
            "website": st.one_of(
                st.none(),
                st.sampled_from(
                    [
                        "https://example.com",
                        "https://hotpass.example",
                        "http://ünicode.test",
                    ]
                ),
            ),
            "planes": st.one_of(st.none(), st.sampled_from(["0", "1", "12"])),
            "description": st.one_of(st.none(), _unicode_strings()),
            "notes": st.one_of(st.none(), _unicode_strings()),
            "last_interaction_date": st.one_of(
                st.none(),
                st.datetimes(
                    min_value=pd.Timestamp(2010, 1, 1),
                    max_value=pd.Timestamp(2040, 12, 31),
                ),
                st.dates(
                    min_value=pd.Timestamp(2010, 1, 1).date(),
                    max_value=pd.Timestamp(2040, 12, 31).date(),
                ),
                _unicode_strings(),
            ),
            "priority": st.one_of(st.none(), st.sampled_from(["High", "Medium", "Low"])),
            "contact_names": list_strategy,
            "contact_roles": list_strategy,
            "contact_emails": st.lists(
                email_local.map(lambda local: f"{local}@example.com"),
                min_size=1,
                max_size=3,
            ),
            "contact_phones": st.lists(
                phone_digits.map(lambda digits: f"+27{digits}"),
                min_size=1,
                max_size=3,
            ),
        }
    )


def _apply_duplicates(frame: pd.DataFrame, pairs: Iterable[tuple[str, str]]) -> pd.DataFrame:
    if not pairs:
        return frame
    columns = list(frame.columns)
    name_to_index = {name: idx for idx, name in enumerate(columns)}
    for extra_name, target_name in pairs:
        extra_idx = name_to_index.get(extra_name)
        target_idx = name_to_index.get(target_name)
        if extra_idx is None or target_idx is None:
            continue
        if columns[extra_idx] in _BASE_COLUMNS:
            # Never duplicate the required columns that pipeline logic depends on.
            continue
        columns[extra_idx] = columns[target_idx]
        name_to_index[columns[extra_idx]] = extra_idx
    frame = frame.copy()
    frame.columns = columns
    return frame


@given(data=st.data())
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_ingest_sources_handles_messy_frames(
    data: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row_count = data.draw(st.integers(min_value=1, max_value=5))
    rows = data.draw(st.lists(_row_strategy(), min_size=row_count, max_size=row_count))

    drop_candidates = data.draw(
        st.lists(
            st.sampled_from(_OPTIONAL_COLUMNS),
            unique=True,
            max_size=len(_OPTIONAL_COLUMNS),
        )
    )

    extra_columns = data.draw(
        st.lists(
            st.text(string.ascii_lowercase, min_size=3, max_size=10).filter(
                lambda name: name not in _BASE_COLUMNS and name not in _OPTIONAL_COLUMNS
            ),
            unique=True,
            max_size=3,
        )
    )

    duplicate_pairs: list[tuple[str, str]] = []
    if extra_columns:
        duplicate_pairs = data.draw(
            st.lists(
                st.tuples(
                    st.sampled_from(extra_columns),
                    st.sampled_from(_OPTIONAL_COLUMNS),
                ),
                unique=True,
                max_size=len(extra_columns),
            )
        )

    frame = pd.DataFrame(rows)
    frame = frame.drop(columns=drop_candidates, errors="ignore")

    for column_name in extra_columns:
        frame[column_name] = [f"{column_name}_{index}" for index in range(len(frame))]

    frame = _apply_duplicates(frame, duplicate_pairs)
    frame.attrs["load_seconds"] = data.draw(
        st.floats(min_value=0.0, max_value=10.0, allow_nan=False)
    )

    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig(
        input_dir=input_dir,
        output_path=output_dir / "refined.parquet",
    )

    def _fake_load_sources(
        _input_dir: Path, _country_code: str, _options: object
    ) -> dict[str, pd.DataFrame]:
        return {"Contact Database": frame.copy(deep=True)}

    monkeypatch.setattr(ingestion_module, "load_sources", _fake_load_sources)

    combined_one, timings_one, redactions_one = ingest_sources(config)
    combined_two, timings_two, redactions_two = ingest_sources(config)

    expect(redactions_one == [], "ingestion should not emit redaction events")
    expect(redactions_two == [], "repeated ingestion should not emit redaction events")
    expect(
        combined_one.equals(combined_two),
        "ingest_sources should be idempotent for stable inputs",
    )
    expect(timings_one == timings_two, "timings should remain stable across runs")
    expect(len(combined_one) == len(frame), "row count should align with input frames")
    expect(
        len(combined_one.columns) == len(set(combined_one.columns)),
        "column headers must be deduplicated",
    )

    for original, slug in zip(
        frame["organization_name"], combined_one["organization_slug"], strict=True
    ):
        expect(slug == slugify(original), "slugified organization name should match helper")
        expect(slug is None or slug.isascii(), "slug outputs should remain ASCII-safe")

    if "province" in frame.columns:
        province_source = frame["province"]
        if isinstance(province_source, pd.DataFrame):
            province_source = province_source.iloc[:, 0]
        for original, normalized in zip(province_source, combined_one["province"], strict=True):
            expect(
                normalized == normalize_province(original),
                "province normalization must align with helper",
            )
    else:
        expect(
            "province" in combined_one.columns,
            "missing provinces should be reintroduced as empty column",
        )

    expect(
        math.isclose(sum(timings_one.values()), sum(timings_two.values())),
        "timing sums should remain stable",
    )
