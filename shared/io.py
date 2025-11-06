from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable, List, Optional
import json


def detect_encoding(path: str, fallback: str = "utf-8") -> str:
    return fallback


def sniff_delimiter(path: str, delimiters: Iterable[str], encoding: str = "utf-8") -> str:
    return next(iter(delimiters), ",")


def find_header_row(path: str, delimiter: str, max_seek: int = 10, encoding: str = "utf-8") -> Optional[int]:
    return 0


def read_raw_lines(path: str, max_lines: int = 20, encoding: str = "utf-8") -> List[str]:
    try:
        text = Path(path).read_text(encoding=encoding, errors="ignore")
        return text.splitlines()[:max_lines]
    except Exception:
        return []


def write_parquet(df: Any, path: str) -> None:
    try:
        import polars as pl  # type: ignore

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(df).write_parquet(path) if not isinstance(df, pl.DataFrame) else df.write_parquet(path)
    except Exception:
        pass


def write_json(payload: Any, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def preview_df(df: Any, n: int = 50) -> list:
    try:
        return df.head(n).to_dicts()
    except Exception:
        return []
