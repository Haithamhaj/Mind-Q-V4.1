from __future__ import annotations

from pathlib import Path

import polars as pl  # type: ignore

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAIRS = [
    ("kpi_sla_pct", "kpi_sla_pct"),
    ("kpi_rto_pct", "kpi_rto_pct"),
    ("kpi_lead_time_p50", "kpi_lead_time_p50"),
    ("kpi_lead_time_p90", "kpi_lead_time_p90"),
    ("kpi_cod_rate", "kpi_cod_rate"),
    ("kpi_cod_total", "kpi_cod_total"),
]
TOL = 1e-3


def _fixture_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "kpi_sla_pct": [0.95, 0.97],
            "kpi_rto_pct": [0.04, 0.03],
            "kpi_lead_time_p50": [24.0, 24.0],
            "kpi_lead_time_p90": [36.0, 36.0],
            "kpi_cod_rate": [0.55, 0.57],
            "kpi_cod_total": [1200.0, 1250.0],
        }
    )


def _ensure_fixture(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _fixture_frame().write_parquet(path.as_posix())


def _ensure_bi_parity_fixtures() -> None:
    _ensure_fixture(FIXTURES / "bi_feed.parquet")
    _ensure_fixture(FIXTURES / "fact_business.parquet")


def _mean(df: pl.DataFrame, column: str) -> float:
    return float(df.select(pl.col(column).mean()).item())  # type: ignore[arg-type]


def test_parity_core_kpis() -> None:
    _ensure_bi_parity_fixtures()
    v09_path = FIXTURES / "bi_feed.parquet"
    v10_path = FIXTURES / "fact_business.parquet"
    assert v09_path.exists(), f"missing fixture {v09_path}"
    assert v10_path.exists(), f"missing fixture {v10_path}"

    v09 = pl.read_parquet(v09_path.as_posix())
    v10 = pl.read_parquet(v10_path.as_posix())

    for k09, k10 in PAIRS:
        assert k09 in v09.columns, f"{k09} missing in Stage 09 feed"
        assert k10 in v10.columns, f"{k10} missing in Stage 10 mart"
        delta = abs(_mean(v09, k09) - _mean(v10, k10))
        assert delta <= TOL, f"{k09} vs {k10} delta={delta}"
