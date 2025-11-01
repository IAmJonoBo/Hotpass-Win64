"""Property-based tests for pipeline determinism and data coercion."""

from __future__ import annotations

import json
import string
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import hotpass.pipeline.aggregation as aggregation_module
import pandas as pd
import pytest
from hotpass.pipeline.aggregation import YEAR_FIRST_PATTERN, _aggregate_group, _latest_iso_date
from hotpass.pipeline.base import execute_pipeline
from hotpass.pipeline.config import PipelineConfig, PipelineRuntimeHooks

from tests.helpers.hypothesis import HealthCheck, given, settings, st


def expect(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


SSOT_COLUMNS: tuple[str, ...] = cast(tuple[str, ...], aggregation_module.SSOT_COLUMNS)

_NON_DETERMINISTIC_METRICS = {
    "duckdb_sort_seconds",
    "parquet_path",
    "polars_materialize_seconds",
    "polars_sort_speedup",
    "polars_transform_seconds",
    "polars_write_seconds",
}


def _stable_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key not in _NON_DETERMINISTIC_METRICS}


_DATE_VARIANT = st.sampled_from(("iso", "dayfirst", "monthfirst", "timestamp"))


def _coerce_expected_iso(values: list[Any]) -> str | None:
    parsed: list[pd.Timestamp] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, pd.Timestamp):
            candidate = pd.to_datetime(value, utc=True)
        else:
            text = str(value).strip()
            if not text:
                continue
            prefer_dayfirst = not bool(YEAR_FIRST_PATTERN.match(text))
            candidate = pd.to_datetime(
                text,
                errors="coerce",
                dayfirst=prefer_dayfirst,
                utc=True,
            )
            if pd.isna(candidate):
                candidate = pd.to_datetime(
                    text,
                    errors="coerce",
                    dayfirst=not prefer_dayfirst,
                    utc=True,
                )
        if pd.isna(candidate):
            continue
        parsed.append(cast(pd.Timestamp, candidate))
    if not parsed:
        return None
    latest = max(parsed)
    return cast(str, latest.date().isoformat())


@settings(max_examples=15, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.datetimes(
                min_value=datetime(2005, 1, 1),
                max_value=datetime(2040, 12, 31),
                timezones=st.just(UTC),
            ),
            _DATE_VARIANT,
        ),
        min_size=1,
        max_size=4,
    ),
    st.lists(st.one_of(st.none(), st.just(""), st.text(min_size=1, max_size=5)), max_size=3),
)
def test_latest_iso_date_handles_varied_formats(
    entries: list[tuple[datetime, str]], noise: list[Any]
) -> None:
    values: list[Any] = []
    for dt, variant in entries:
        if variant == "iso":
            values.append(dt.date().isoformat())
        elif variant == "dayfirst":
            values.append(dt.strftime("%d/%m/%Y"))
        elif variant == "monthfirst":
            values.append(dt.strftime("%m-%d-%Y"))
        else:
            values.append(pd.Timestamp(dt))
    values.extend(noise)

    result = _latest_iso_date(values)
    expected = _coerce_expected_iso(values)
    expect(result == expected, "ISO coercion should match Pandas reference implementation")


@settings(max_examples=12, deadline=None)
@given(
    st.lists(
        st.fixed_dictionaries(
            {
                "organization_name": st.text(string.ascii_letters + " -'", min_size=1, max_size=25),
                "source_dataset": st.sampled_from(
                    ["Contact Database", "Reachout Database", "SACAA Cleaned", "Agent"],
                ),
                "source_record_id": st.text(string.digits, min_size=1, max_size=6),
                "province": st.one_of(
                    st.none(),
                    st.sampled_from(["Gauteng", "Western Cape", "KwaZulu-Natal"]),
                ),
                "area": st.one_of(st.none(), st.text(string.ascii_letters + " ", max_size=30)),
                "address": st.one_of(st.none(), st.text(string.printable.strip(), max_size=50)),
                "category": st.one_of(st.none(), st.sampled_from(["Flight School", "Aviation"])),
                "organization_type": st.one_of(
                    st.none(), st.sampled_from(["School", "Club", "Association"])
                ),
                "status": st.one_of(st.none(), st.sampled_from(["Active", "Dormant"])),
                "website": st.one_of(
                    st.none(),
                    st.sampled_from(["https://example.com", "https://hotpass.example"]),
                ),
                "planes": st.one_of(st.none(), st.sampled_from(["1", "2", "10"])),
                "description": st.one_of(st.none(), st.text(string.printable.strip(), max_size=40)),
                "notes": st.one_of(st.none(), st.text(string.printable.strip(), max_size=40)),
                "last_interaction_date": st.one_of(
                    st.none(),
                    st.datetimes(min_value=datetime(2010, 1, 1), max_value=datetime(2040, 1, 1)),
                ),
                "priority": st.one_of(st.none(), st.sampled_from(["High", "Medium", "Low"])),
                "contact_names": st.lists(
                    st.text(string.ascii_letters + " -'", min_size=1, max_size=20),
                    min_size=1,
                    max_size=2,
                ),
                "contact_roles": st.lists(
                    st.sampled_from(["Owner", "Manager", "Pilot"]),
                    min_size=1,
                    max_size=2,
                ),
                "contact_emails": st.lists(
                    st.builds(
                        lambda local: f"{local}@example.com",
                        st.text(string.ascii_lowercase, min_size=3, max_size=10),
                    ),
                    min_size=1,
                    max_size=2,
                ),
                "contact_phones": st.lists(
                    st.builds(
                        lambda digits: "+27" + digits,
                        st.text(string.digits, min_size=9, max_size=9),
                    ),
                    min_size=1,
                    max_size=2,
                ),
            }
        ),
        min_size=1,
        max_size=3,
    )
)
def test_aggregate_group_handles_missing_optional_columns(
    rows: list[dict[str, Any]],
) -> None:
    normalised_rows: list[dict[str, Any]] = []
    for row in rows:
        coerced = dict(row)
        if isinstance(coerced.get("last_interaction_date"), datetime):
            coerced["last_interaction_date"] = coerced["last_interaction_date"].date().isoformat()
        normalised_rows.append(coerced)

    result = _aggregate_group(
        slug=None,
        rows=normalised_rows,
        country_code="ZA",
        intent_summaries=None,
    )

    for column in SSOT_COLUMNS:
        expect(column in result, f"expected column '{column}' in aggregation output")
    provenance_raw = result.get("selection_provenance")
    expect(
        isinstance(provenance_raw, str),
        "selection provenance must serialise to JSON text",
    )
    assert isinstance(provenance_raw, str)
    parsed = json.loads(provenance_raw)
    expect(isinstance(parsed, dict), "selection provenance payload must be a JSON object")


class _DeterministicClock:
    def __init__(self) -> None:
        self._perf_ticks = 0
        self._time_ticks = 0

    def perf_counter(self) -> float:
        value = self._perf_ticks * 0.01
        self._perf_ticks += 1
        return value

    def time(self) -> float:
        value = 1_700_000_000 + self._time_ticks
        self._time_ticks += 1
        return float(value)

    def datetime(self) -> datetime:
        return datetime(2025, 1, 1, tzinfo=UTC) + timedelta(seconds=self._time_ticks)


_VALID_ROW = st.fixed_dictionaries(
    {
        "organization_name": st.text(string.ascii_letters + " -'", min_size=1, max_size=25),
        "source_dataset": st.sampled_from(
            ["Contact Database", "Reachout Database", "SACAA Cleaned"]
        ),
        "source_record_id": st.text(string.digits, min_size=1, max_size=6),
        "province": st.sampled_from(["Gauteng", "Western Cape", "KwaZulu-Natal"]),
        "area": st.one_of(st.just(""), st.text(string.ascii_letters + " ", max_size=30)),
        "address": st.text(string.printable.strip(), min_size=1, max_size=40),
        "category": st.sampled_from(["Flight School", "Aviation"]),
        "organization_type": st.sampled_from(["School", "Club", "Association"]),
        "status": st.sampled_from(["Active", "Dormant"]),
        "website": st.sampled_from(["https://example.com", "https://hotpass.example"]),
        "planes": st.sampled_from(["1", "2", "10"]),
        "description": st.text(string.printable.strip(), min_size=1, max_size=40),
        "notes": st.text(string.printable.strip(), min_size=1, max_size=40),
        "last_interaction_date": st.datetimes(
            min_value=datetime(2015, 1, 1), max_value=datetime(2035, 12, 31)
        ),
        "priority": st.sampled_from(["High", "Medium", "Low"]),
        "contact_names": st.lists(
            st.text(string.ascii_letters + " -'", min_size=1, max_size=20),
            min_size=1,
            max_size=2,
        ),
        "contact_roles": st.lists(
            st.sampled_from(["Owner", "Manager", "Pilot"]), min_size=1, max_size=2
        ),
        "contact_emails": st.lists(
            st.builds(
                lambda local: f"{local}@example.com",
                st.text(string.ascii_lowercase, min_size=3, max_size=10),
            ),
            min_size=1,
            max_size=2,
        ),
        "contact_phones": st.lists(
            st.builds(
                lambda digits: "+27" + digits,
                st.text(string.digits, min_size=9, max_size=9),
            ),
            min_size=1,
            max_size=2,
        ),
    }
)


def _build_config(
    frame: pd.DataFrame, output_path: Path, clock: _DeterministicClock
) -> PipelineConfig:
    hooks = PipelineRuntimeHooks(
        time_fn=clock.time,
        perf_counter=clock.perf_counter,
        datetime_factory=clock.datetime,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return PipelineConfig(
        input_dir=output_path.parent,
        output_path=output_path,
        enable_formatting=False,
        enable_audit_trail=False,
        enable_recommendations=False,
        daily_list_size=0,
        preloaded_agent_frame=frame,
        runtime_hooks=hooks,
        random_seed=42,
    )


@settings(
    max_examples=2,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(st.lists(_VALID_ROW, min_size=1, max_size=3))
def test_pipeline_idempotent_with_seed_and_hooks(
    tmp_path: Path, rows: list[dict[str, Any]]
) -> None:
    dataset = []
    for row in rows:
        converted = dict(row)
        converted["last_interaction_date"] = row["last_interaction_date"].date().isoformat()
        dataset.append(converted)
    frame = pd.DataFrame(dataset)

    first_clock = _DeterministicClock()
    second_clock = _DeterministicClock()

    first_config = _build_config(
        frame.copy(deep=True),
        output_path=tmp_path / "first" / "refined.parquet",
        clock=first_clock,
    )
    second_config = _build_config(
        frame.copy(deep=True),
        output_path=tmp_path / "second" / "refined.parquet",
        clock=second_clock,
    )

    first_result = execute_pipeline(first_config)
    second_result = execute_pipeline(second_config)

    expect(
        first_result.refined.equals(second_result.refined),
        "refined dataframe should be stable",
    )
    report_one = first_result.quality_report.to_dict()
    report_two = second_result.quality_report.to_dict()
    report_one["performance_metrics"] = _stable_metrics(report_one["performance_metrics"])
    report_two["performance_metrics"] = _stable_metrics(report_two["performance_metrics"])
    expect(report_one == report_two, "quality report must remain consistent across runs")
    stable_metrics_one = _stable_metrics(first_result.performance_metrics)
    stable_metrics_two = _stable_metrics(second_result.performance_metrics)
    expect(stable_metrics_one == stable_metrics_two, "deterministic metrics should match")
