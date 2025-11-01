from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("frictionless")

from hotpass.data_sources import ExcelReadOptions, load_reachout_database  # noqa: E402

from tests.helpers.assertions import expect


def test_load_reachout_database_chunk_size_applies(
    sample_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_rows: list[int | None] = []
    original = pd.read_excel

    def _spy_read_excel(*args, **kwargs):
        captured_rows.append(kwargs.get("nrows"))
        return original(*args, **kwargs)

    monkeypatch.setattr(pd, "read_excel", _spy_read_excel)

    df = load_reachout_database(sample_data_dir, "ZA", ExcelReadOptions(chunk_size=1))

    expect(len(df) == 2, "DataFrame should have 2 rows")
    # Both organisation and contact sheets should be streamed.
    expect(captured_rows.count(1) >= 2, "Chunk size should be applied to both sheets")


def test_excel_stage_to_parquet_invoked(
    sample_data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def _fake_to_parquet(self: pd.DataFrame, path: Path, *, index: bool = False) -> None:
        calls.append(Path(path))

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _fake_to_parquet, raising=False)

    load_reachout_database(
        sample_data_dir,
        "ZA",
        ExcelReadOptions(chunk_size=1, stage_dir=tmp_path, stage_to_parquet=True),
    )

    expect(bool(calls), "Expected staging to parquet when enabled")
