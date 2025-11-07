"""Benchmark HotpassConfig.merge performance on synthetic payloads.

This script generates configurable nested updates that exercise the deep merge
logic within :class:`hotpass.config_schema.HotpassConfig`.  The benchmark is
intended to provide a reproducible baseline that can be compared across
optimisations or configuration changes.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from hotpass.config_schema import HotpassConfig


def _build_update(
    iteration: int,
    *,
    agents: int,
    providers_per_agent: int,
    tasks_per_agent: int,
    collectors: int,
    targets: int,
) -> dict[str, Any]:
    """Construct a synthetic update payload with nested acquisition/intent data."""

    def _suffix(index: int) -> str:
        return f"{iteration}-{index}"

    provider_template = {
        "enabled": True,
        "weight": 1.0,
        "options": {"api_key": "benchmark", "timeout": 3 + iteration % 5},
    }
    task_template = {
        "kind": "search",
        "enabled": True,
        "options": {"page_size": 25, "language": "en"},
    }

    agent_payload = []
    for agent_index in range(agents):
        providers = [
            {
                **provider_template,
                "name": f"provider-{_suffix(agent_index * providers_per_agent + p)}",
            }
            for p in range(providers_per_agent)
        ]
        tasks = [
            {
                **task_template,
                "name": f"task-{_suffix(agent_index * tasks_per_agent + t)}",
                "provider": providers[0]["name"] if providers else None,
            }
            for t in range(tasks_per_agent)
        ]
        targets_payload = [
            {
                "identifier": f"target-{_suffix(agent_index * targets + t)}",
                "domain": f"example-{t}.test",
                "location": "ZA",
                "metadata": {"priority": t % 3},
            }
            for t in range(targets)
        ]
        agent_payload.append(
            {
                "name": f"agent-{_suffix(agent_index)}",
                "description": "Benchmark acquisition agent",
                "search_terms": [f"query {_suffix(agent_index)}"],
                "region": "global",
                "concurrency": 2 + (agent_index % 3),
                "providers": providers,
                "targets": targets_payload,
                "tasks": tasks,
            }
        )

    collector_payload = [
        {
            "name": f"collector-{_suffix(index)}",
            "weight": 0.5 + (index % 5) * 0.1,
            "options": {"window_days": 30 + index},
        }
        for index in range(collectors)
    ]

    intent_targets = [
        {
            "identifier": f"intent-target-{_suffix(index)}",
            "slug": f"intent-{_suffix(index)}",
            "metadata": {"segment": "benchmark", "index": index},
        }
        for index in range(targets)
    ]

    update_payload = {
        "profile": {
            "name": "benchmark",
            "industry": "aviation",
        },
        "pipeline": {
            "input_dir": f"./data/benchmark/{iteration}",
            "output_path": f"./dist/benchmark/{iteration}/refined.xlsx",
            "backfill": iteration % 2 == 0,
            "incremental": iteration % 3 == 0,
            "run_id": f"benchmark-{iteration}",
            "excel_chunk_size": 5000,
            "acquisition": {
                "enabled": True,
                "deduplicate": True,
                "provenance_namespace": "benchmark",
                "agents": agent_payload,
                "credentials": {
                    f"provider-{_suffix(i)}": "token-placeholder" for i in range(agents)
                },
            },
            "intent": {
                "enabled": True,
                "collectors": collector_payload,
                "targets": intent_targets,
            },
        },
        "governance": {
            "intent": [
                "benchmark default",
                "ensure deterministic-first enrichment",
            ],
        },
        "features": {
            "enrichment": True,
            "compliance": iteration % 4 == 0,
        },
    }

    return update_payload


def _summarise(durations: list[float]) -> dict[str, float]:
    durations_ms = [value * 1000.0 for value in durations]
    durations_ms.sort()
    percentile = lambda p: durations_ms[math.ceil(p * (len(durations_ms) - 1))]
    return {
        "iterations": len(durations_ms),
        "min_ms": durations_ms[0],
        "max_ms": durations_ms[-1],
        "mean_ms": mean(durations_ms),
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
    }


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    config = HotpassConfig()
    durations: list[float] = []

    for iteration in range(args.iterations):
        update = _build_update(
            iteration,
            agents=args.agents,
            providers_per_agent=args.providers,
            tasks_per_agent=args.tasks,
            collectors=args.collectors,
            targets=args.targets,
        )
        start = perf_counter()
        config = config.merge(update)
        durations.append(perf_counter() - start)

    summary = _summarise(durations)
    summary["agents"] = args.agents
    summary["providers_per_agent"] = args.providers
    summary["tasks_per_agent"] = args.tasks
    summary["collectors"] = args.collectors
    summary["targets"] = args.targets
    return summary


def _write_results(summary: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark HotpassConfig.merge")
    parser.add_argument("--iterations", type=int, default=10, help="Merge iterations to run")
    parser.add_argument("--agents", type=int, default=25, help="Agents per update payload")
    parser.add_argument(
        "--providers", type=int, default=3, help="Providers per agent in the payload"
    )
    parser.add_argument("--tasks", type=int, default=4, help="Tasks per agent in the payload")
    parser.add_argument(
        "--collectors", type=int, default=6, help="Intent collectors included in each update"
    )
    parser.add_argument(
        "--targets", type=int, default=8, help="Targets included for acquisition/intent"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/benchmarks/hotpass_config_merge.json"),
        help="Where to write the benchmark summary JSON",
    )
    args = parser.parse_args()

    summary = run_benchmark(args)
    _write_results(summary, args.output)

    print("HotpassConfig.merge benchmark")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

