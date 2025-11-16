from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import polars as pl  # type: ignore


def write_fact_business(artifacts_root: Path, run_id: str, rows: Iterable[Mapping[str, object]]) -> Path:
    """Helper used by ML sandbox tests to seed a minimal Stage 10 mart."""

    stage10_dir = artifacts_root / run_id / "stage_10_bi" / "marts"
    stage10_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(list(rows))
    path = stage10_dir / "fact_business.parquet"
    df.write_parquet(path.as_posix())
    return path
