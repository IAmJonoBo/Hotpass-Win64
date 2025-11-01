"""DuckDB-backed query adapter for Polars datasets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import duckdb
import polars as pl
import pyarrow as pa

from .adapters import QueryAdapter


class DuckDBAdapter(QueryAdapter):
    """Execute ad-hoc SQL queries against in-memory datasets using DuckDB."""

    def __init__(self, *, threads: int | None = None) -> None:
        self._connection = duckdb.connect(database=":memory:")
        self._registered: set[str] = set()
        if threads is not None and threads > 0:
            try:  # pragma: no cover - dependent on DuckDB build
                self._connection.execute("PRAGMA threads=?", [threads])
            except duckdb.Error:
                self._connection.execute(f"PRAGMA threads={threads}")

    def register(self, name: str, data: pl.DataFrame | pa.Table | str) -> None:
        if isinstance(data, pl.DataFrame):
            arrow_obj = data.to_arrow()
            self._connection.register(name, arrow_obj)
        elif isinstance(data, pa.Table):
            self._connection.register(name, data)
        elif isinstance(data, str):
            self._connection.register(name, data)
        else:  # pragma: no cover - defensive branch
            msg = f"Unsupported dataset type for DuckDB registration: {type(data)!r}"
            raise TypeError(msg)
        self._registered.add(name)

    def execute(self, sql: str, *, parameters: Sequence[Any] | None = None) -> pl.DataFrame:
        if parameters:
            cursor = self._connection.execute(sql, parameters)
        else:
            cursor = self._connection.execute(sql)
        arrow_obj = cursor.arrow()
        result = pl.from_arrow(arrow_obj)
        if isinstance(result, pl.Series):  # pragma: no cover - depends on query shape
            return result.to_frame()
        return result

    def close(self) -> None:  # pragma: no cover - exercised via adapter lifecycle
        for name in list(self._registered):
            try:
                self._connection.unregister(name)
            except duckdb.Error:
                pass
        self._registered.clear()
        self._connection.close()
