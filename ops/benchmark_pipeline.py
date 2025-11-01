from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hotpass import benchmarks
from hotpass.data_sources import ExcelReadOptions


def _format_line(label: str, value: Any) -> str:
    if isinstance(value, float):
        value = f"{value:.4f}"
    return f"{label}: {value}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pipeline benchmarks and summarise results")
    parser.add_argument("--input-dir", type=Path, default=Path.cwd() / "data")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path.cwd() / "data" / "benchmark_refined.xlsx",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--country-code", type=str, default="ZA")
    parser.add_argument("--expectation-suite", type=str, default="default")
    parser.add_argument("--excel-chunk-size", type=int)
    parser.add_argument("--excel-engine", type=str)
    parser.add_argument("--excel-stage-dir", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit JSON results")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.runs <= 0:
        parser.error("--runs must be greater than zero")

    excel_options = None
    if any([args.excel_chunk_size, args.excel_engine, args.excel_stage_dir]):
        excel_options = ExcelReadOptions(
            chunk_size=args.excel_chunk_size,
            engine=args.excel_engine,
            stage_to_parquet=args.excel_stage_dir is not None,
            stage_dir=args.excel_stage_dir,
        )

    result = benchmarks.run_benchmark(
        input_dir=args.input_dir,
        output_path=args.output_path,
        runs=args.runs,
        country_code=args.country_code,
        expectation_suite_name=args.expectation_suite,
        excel_options=excel_options,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(_format_line("Runs", result.runs))
    for label, key in benchmarks.benchmark_fields():
        value = result.metrics.get(key)
        if value is not None:
            print(_format_line(label, value))

    if "source_load_seconds" in result.metrics:
        print("Source Load Durations:")
        for loader, seconds in sorted(result.metrics["source_load_seconds"].items()):
            print(f"  - {loader}: {seconds:.4f}s")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
