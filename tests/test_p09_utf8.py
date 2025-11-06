from __future__ import annotations

from pathlib import Path

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def test_p09_utf8_roundtrip(tmp_path: Path) -> None:
    run_id = "run_utf8"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=3)

    clean_path = artifacts_root / run_id / "stage_06_standardize" / "clean.parquet"
    df = pl.read_parquet(clean_path.as_posix())
    df = df.with_columns(
        [
            pl.lit("الرياض").alias("DESTINATION"),
            pl.lit("تم التسليم").alias("STATUS"),
        ]
    )
    df.write_parquet(clean_path.as_posix())

    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    feed_path = artifacts_root / run_id / "stage_09_business_validation" / "bi_feed.parquet"
    feed_df = pl.read_parquet(feed_path.as_posix())
    assert "الرياض" in feed_df["DESTINATION"].unique().to_list()
