#!/usr/bin/env python3
"""Benchmark HotpassConfig.merge over large payloads.

This script materialises synthetic configuration payloads with increasing
complexity and records how long ``HotpassConfig.merge`` takes to apply them.
Results are written to ``dist/benchmarks/hotpass_config_merge.json`` by default
so future runs can be compared for regressions.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from hotpass.config_schema import HotpassConfig


@dataclass(slots=True)
class BenchmarkSample:
    """Captured timing statistics for a particular payload size."""

    payload_size: int
    payload_bytes: int
    iterations: int
    chain_depth: int
    durations: list[float]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.durations)

    @property
    def stdev(self) -> float:
        if len(self.durations) < 2:
            return 0.0
        return statistics.pstdev(self.durations)

    @property
    def minimum(self) -> float:
        return min(self.durations)

    @property
    def maximum(self) -> float:
        return max(self.durations)

    @property
    def merges_per_second(self) -> float:
        total = sum(self.durations)
        if total == 0:
            return float("inf")
        return (self.iterations * self.chain_depth) / total

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload_size": self.payload_size,
            "payload_bytes": self.payload_bytes,
            "iterations": self.iterations,
            "chain_depth": self.chain_depth,
            "durations": self.durations,
            "mean_seconds": self.mean,
            "stdev_seconds": self.stdev,
            "min_seconds": self.minimum,
            "max_seconds": self.maximum,
            "merges_per_second": self.merges_per_second,
        }


def _build_payload(size: int) -> dict[str, Any]:
    """Generate a nested update payload with the requested complexity."""

    webhook_count = max(5, min(size // 10, 200))
    intent_count = max(1, min(size // 25, 25))
    backfill_windows = max(1, min(size // 250, 10))

    payload: dict[str, Any] = {
        "pipeline": {
            "sensitive_fields": [f"field_{idx}" for idx in range(size)],
            "intent_webhooks": [
                f"https://hooks.example/{idx}" for idx in range(webhook_count)
            ],
            "excel_chunk_size": 500,
        },
        "telemetry": {
            "enabled": True,
            "service_name": "hotpass-benchmark",
            "environment": "benchmark",
            "resource_attributes": {
                f"attr_{idx}": f"value_{idx}" for idx in range(size // 2)
            },
        },
        "features": {
            "enrichment": True,
            "entity_resolution": size % 2 == 0,
            "observability": True,
            "acquisition": size % 3 == 0,
        },
        "governance": {
            "intent": [
                f"Benchmark intent {idx}" for idx in range(intent_count)
            ],
            "policy_reference": "benchmark-policy",
        },
        "orchestrator": {
            "parameters": {
                f"param_{idx}": f"value_{idx}" for idx in range(size)
            },
            "backfill": {
                "windows": [
                    {
                        "start_date": f"2025-01-{idx + 1:02d}",
                        "end_date": f"2025-01-{idx + 2:02d}",
                        "versions": [f"v{idx}", f"v{idx+1}"],
                    }
                    for idx in range(backfill_windows)
                ],
                "concurrency_limit": 2,
                "concurrency_key": "hotpass/benchmark",
            },
        },
    }

    return payload


def _benchmark_payload(size: int, iterations: int, chain_depth: int) -> BenchmarkSample:
    payload = _build_payload(size)
    payload_bytes = len(json.dumps(payload).encode("utf-8"))
    durations: list[float] = []

    for _ in range(iterations):
        reference = HotpassConfig()
        start = time.perf_counter()
        candidate = reference
        for _ in range(chain_depth):
            candidate = candidate.merge(payload)
        durations.append(time.perf_counter() - start)

    return BenchmarkSample(
        payload_size=size,
        payload_bytes=payload_bytes,
        iterations=iterations,
        chain_depth=chain_depth,
        durations=durations,
    )


def run_benchmarks(sizes: Iterable[int], iterations: int, chain_depth: int) -> list[BenchmarkSample]:
    results: list[BenchmarkSample] = []
    for size in sizes:
        results.append(_benchmark_payload(size, iterations, chain_depth))
    return results


def _default_output_path() -> Path:
    return Path("dist/benchmarks/hotpass_config_merge.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        metavar="N",
        type=int,
        nargs="*",
        default=[250, 1000, 5000],
        help="Payload sizes to benchmark (default: 250 1000 5000)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations to run per payload size (default: 5)",
    )
    parser.add_argument(
        "--chain-depth",
        type=int,
        default=3,
        help="How many consecutive merge calls to execute per iteration (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Path to write benchmark results (default: dist/benchmarks/hotpass_config_merge.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sizes = sorted({size for size in args.sizes if size > 0})
    if not sizes:
        print("No valid payload sizes supplied.", file=sys.stderr)
        return 2

    results = run_benchmarks(sizes, args.iterations, args.chain_depth)

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp_utc": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "iterations": args.iterations,
        "chain_depth": args.chain_depth,
        "sizes": sizes,
        "results": [sample.as_dict() for sample in results],
    }

    output.write_text(json.dumps(payload, indent=2))

    print(f"Benchmark results written to {output}")
    for sample in results:
        print(
            f"size={sample.payload_size:<6} mean={sample.mean:.6f}s "
            f"merges/s={sample.merges_per_second:.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
