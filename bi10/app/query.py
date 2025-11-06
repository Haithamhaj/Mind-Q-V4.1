from __future__ import annotations

import contextlib
import pathlib
from typing import Dict, Tuple, Iterable, Any, List

import duckdb  # type: ignore

_views_cache: Dict[Tuple[str, Tuple[str, ...]], bool] = {}


def _mart_signature(mart_dir: pathlib.Path) -> Tuple[str, Tuple[str, ...]]:
    files = tuple(sorted(p.name for p in mart_dir.glob("*.parquet")))
    return (str(mart_dir.resolve()), files)


@contextlib.contextmanager
def conn_for(run_id: str, artifacts_dir: str) -> Iterable[duckdb.DuckDBPyConnection]:
    mart_dir = pathlib.Path(artifacts_dir) / run_id / "stage_10_bi" / "marts"
    if not mart_dir.exists():
        raise FileNotFoundError(f"mart directory not found: {mart_dir}")
    connection = duckdb.connect(":memory:")
    try:
        signature = _mart_signature(mart_dir)
        # always create fresh views in this transient connection
        for pq in mart_dir.glob("*.parquet"):
            view_name = pq.stem
            connection.execute(f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{pq.as_posix()}')")
        _views_cache.setdefault(signature, True)
        yield connection
    finally:
        connection.close()


def run_sql(connection: duckdb.DuckDBPyConnection, sql: str) -> List[Dict[str, Any]]:
    result = connection.execute(sql)
    arrow_obj = result.arrow()
    if hasattr(arrow_obj, "to_pylist"):
        return arrow_obj.to_pylist()
    table = arrow_obj.read_all() if hasattr(arrow_obj, "read_all") else arrow_obj
    if hasattr(table, "to_pylist"):
        return table.to_pylist()
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    return [dict(zip(columns, row)) for row in rows]


__all__ = ["conn_for", "run_sql"]
