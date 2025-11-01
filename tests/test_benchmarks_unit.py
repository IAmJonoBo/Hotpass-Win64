"""Unit-level coverage for the benchmarks helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from hotpass import benchmarks


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_run_benchmark_averages_metrics(monkeypatch, tmp_path: Path) -> None:
    samples = [
        {
            "total_seconds": 2.0,
            "rows_per_second": 10.0,
            "source_load_seconds": {"excel": 1.0},
        },
        {
            "total_seconds": 4.0,
            "rows_per_second": 5.0,
            "source_load_seconds": {"excel": 3.0},
        },
    ]

    def fake_run_pipeline(config):  # noqa: ANN001
        data = samples.pop(0)
        return SimpleNamespace(performance_metrics=data)

    monkeypatch.setattr(benchmarks, "run_pipeline", fake_run_pipeline)

    result = benchmarks.run_benchmark(
        input_dir=tmp_path,
        output_path=tmp_path / "out.xlsx",
        runs=2,
    )

    expect(result.runs == 2, "Expected run count should be preserved")
    expect(abs(result.metrics["total_seconds"] - 3.0) < 1e-9, "Totals should be averaged")
    expect(result.metrics["source_load_seconds"]["excel"] == 2.0, "Nested metrics averaged")
    expect(len(result.samples) == 2, "All sample metrics captured")


def test_run_benchmark_rejects_invalid_runs(tmp_path: Path) -> None:
    try:
        benchmarks.run_benchmark(
            input_dir=tmp_path,
            output_path=tmp_path / "out.xlsx",
            runs=0,
        )
    except ValueError as exc:  # pragma: no cover - defensive guard
        expect(
            "runs must be a positive integer" in str(exc),
            "Validation message should mention runs",
        )
    else:  # pragma: no cover - required for expect helper
        raise AssertionError("Expected ValueError for invalid runs")


def test_benchmark_fields_returns_copy() -> None:
    fields = benchmarks.benchmark_fields()
    fields.append(("Custom", "custom"))

    expect(
        ("Custom", "custom") not in benchmarks.benchmark_fields(),
        "Returned list should be a copy",
    )
