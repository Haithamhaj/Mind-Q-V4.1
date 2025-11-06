from __future__ import annotations

from pathlib import Path

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def test_p09_tiles(tmp_path: Path) -> None:
    run_id = "run_tiles"
    artifacts_root = write_stage_artifacts(
        tmp_path,
        run_id,
        n_rows=10,
        cod_values=[5.0, 10.0, 15.0],
        status_cycle=["DELIVERED", "IN_TRANSIT", "DELIVERED"],
    )
    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    out_dir = artifacts_root / run_id / "stage_09_business_validation" / "bi_tiles"
    day_tiles = pl.read_parquet((out_dir / "day.parquet").as_posix())
    assert {"orders_cnt", "orders_cnt_prev", "delta_orders_cnt", "cod_rate"} <= set(day_tiles.columns)
    assert day_tiles["orders_cnt_prev"].is_null().sum() < day_tiles.height  # ensure comparisons available

    week_tiles = pl.read_parquet((out_dir / "week.parquet").as_posix())
    assert {"orders_cnt", "orders_cnt_prev", "delta_orders_cnt"} <= set(week_tiles.columns)
