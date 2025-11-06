from __future__ import annotations

from pathlib import Path

import pytest

pl = pytest.importorskip("polars")  # type: ignore

from tests.p09_utils import load_impl, write_stage_artifacts


def test_p09_benchmarks(tmp_path: Path) -> None:
    run_id = "run_benchmarks"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=20)
    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    bench_path = out_dir / "benchmarks.parquet"
    assert bench_path.exists()
    benchmarks = pl.read_parquet(bench_path.as_posix())
    assert {"DESTINATION", "STATUS", "orders_cnt", "cod_avg_p50", "cod_avg_p90"} <= set(benchmarks.columns)
