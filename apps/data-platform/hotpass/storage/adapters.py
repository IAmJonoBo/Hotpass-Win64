"""Storage adapter interfaces used by the Hotpass pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any

import polars as pl
import pyarrow as pa


class QueryAdapter(AbstractContextManager["QueryAdapter"], ABC):
    """Abstract interface for executing SQL-like queries against datasets."""

    def __enter__(self) -> QueryAdapter:  # pragma: no cover - trivial
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - trivial
        self.close()

    @abstractmethod
    def register(self, name: str, data: pl.DataFrame | pa.Table | str) -> None:
        """Register a dataset with the adapter under the provided name."""

    @abstractmethod
    def execute(self, sql: str, *, parameters: Sequence[Any] | None = None) -> pl.DataFrame:
        """Execute a query and return the results as a Polars DataFrame."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the adapter."""
