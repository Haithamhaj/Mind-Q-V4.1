from __future__ import annotations

from pathlib import Path

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def test_p09_segment_insights(tmp_path: Path) -> None:
    run_id = "run_segments"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=8)
    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    segment_path = out_dir / "segment_insights.parquet"
    insights_df = pl.read_parquet(segment_path.as_posix())
    assert "segment_key" in insights_df.columns
    if insights_df.height > 0:
        assert insights_df["effect_size"].is_null().sum() < insights_df.height
