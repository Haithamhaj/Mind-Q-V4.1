from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover
    pl = None  # type: ignore


def _read_table(path: Path) -> Any:
    if pl is not None:
        if path.suffix.lower() in {".parquet", ".pq"}:
            return pl.read_parquet(path.as_posix())  # type: ignore[call-arg]
        return pl.read_csv(path.as_posix())  # type: ignore[call-arg]
    import pandas as pd  # type: ignore

    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    return pd.read_csv(path, engine="python")


def _as_preview(df: Any, limit: int = 3) -> List[Dict[str, Any]]:
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return df.head(limit).to_dicts()  # type: ignore[call-arg]
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        pd = None  # type: ignore
    if pd is not None and isinstance(df, pd.DataFrame):
        return df.head(limit).to_dict(orient="records")
    return []


def _row_count(df: Any) -> int:
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return int(df.height)  # type: ignore[attr-defined]
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        pd = None  # type: ignore
    if pd is not None and isinstance(df, pd.DataFrame):
        return int(df.shape[0])
    return int(len(df))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Peek at an ingestion input file")
    parser.add_argument("--input", required=True, help="Path to CSV/Parquet file")
    parser.add_argument("--rows", type=int, default=3, help="Number of rows to preview (default: 3)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.input).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    table = _read_table(path)
    payload = {
        "abs_path": path.as_posix(),
        "filesize_bytes": path.stat().st_size,
        "row_count": _row_count(table),
        "preview": _as_preview(table, limit=max(args.rows, 0)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
