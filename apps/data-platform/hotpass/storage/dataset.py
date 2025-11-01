"""Polars-backed dataset helpers for the Hotpass pipeline."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import polars as pl
import pyarrow as pa

from .adapters import QueryAdapter


@dataclass
class DatasetTimings:
    """Timings captured while manipulating a :class:`PolarsDataset`."""

    construction_seconds: float = 0.0
    sort_seconds: float = 0.0
    query_seconds: float = 0.0
    parquet_seconds: float = 0.0


class PolarsDataset:
    """Convenience wrapper around a Polars DataFrame with timing metadata."""

    def __init__(self, frame: pl.DataFrame, timings: DatasetTimings | None = None) -> None:
        self._frame = frame
        self.timings = timings or DatasetTimings()

    @classmethod
    def from_rows(cls, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> PolarsDataset:
        start = time.perf_counter()
        frame = pl.DataFrame(rows, schema=list(columns))
        duration = time.perf_counter() - start
        return cls(frame, DatasetTimings(construction_seconds=duration))

    @classmethod
    def from_pandas(cls, frame: pd.DataFrame) -> PolarsDataset:
        start = time.perf_counter()
        polars_frame = pl.from_pandas(frame, include_index=False)
        duration = time.perf_counter() - start
        return cls(polars_frame, DatasetTimings(construction_seconds=duration))

    @property
    def frame(self) -> pl.DataFrame:
        return self._frame

    def replace(self, frame: pl.DataFrame) -> None:
        """Replace the underlying Polars DataFrame."""

        self._frame = frame

    def copy(self) -> PolarsDataset:
        timings = DatasetTimings(
            construction_seconds=self.timings.construction_seconds,
            sort_seconds=self.timings.sort_seconds,
            query_seconds=self.timings.query_seconds,
            parquet_seconds=self.timings.parquet_seconds,
        )
        return PolarsDataset(self._frame.clone(), timings)

    def sort(self, *columns: str, descending: bool = False) -> PolarsDataset:
        start = time.perf_counter()
        self._frame = self._frame.sort(by=list(columns), descending=descending)
        self.timings.sort_seconds += time.perf_counter() - start
        return self

    def to_pandas(self) -> pd.DataFrame:
        return self._frame.to_pandas(use_pyarrow_extension_array=True)

    def to_arrow(self) -> pa.Table:
        return self._frame.to_arrow()

    def write_parquet(self, path: Path, *, compression: CompressionType | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        if compression is not None:
            self._frame.write_parquet(str(path), compression=compression)
        else:
            self._frame.write_parquet(str(path))
        self.timings.parquet_seconds += time.perf_counter() - start

    def value_counts(self, column: str) -> dict[str, int]:
        if column not in self._frame.columns:
            return {}
        counts = self._frame.select(pl.col(column)).drop_nulls().group_by(column).len()
        return {str(row[column]): int(row["len"]) for row in counts.to_dicts()}

    def column_stats(self, column: str) -> dict[str, float]:
        if column not in self._frame.columns or self._frame.is_empty():
            return {"mean": 0.0, "min": 0.0, "max": 0.0}
        stats = self._frame.select(
            pl.col(column).mean().alias("mean"),
            pl.col(column).min().alias("min"),
            pl.col(column).max().alias("max"),
        ).to_dicts()[0]
        return {key: float(value) if value is not None else 0.0 for key, value in stats.items()}

    def query(
        self,
        adapter: QueryAdapter,
        sql: str,
        *,
        parameters: Sequence[Any] | None = None,
        register_as: str = "dataset",
    ) -> pl.DataFrame:
        start = time.perf_counter()
        with adapter as runner:
            runner.register(register_as, self._frame)
            result = runner.execute(sql, parameters=parameters)
        self.timings.query_seconds += time.perf_counter() - start
        return result


CompressionType = Literal[
    "lz4",
    "uncompressed",
    "snappy",
    "gzip",
    "lzo",
    "brotli",
    "zstd",
]
