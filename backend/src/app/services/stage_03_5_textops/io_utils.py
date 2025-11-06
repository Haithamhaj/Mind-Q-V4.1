from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path
from typing import Any, Dict, Iterable, List

import polars as pl  # type: ignore


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def expand_path(template: str, run_id: str) -> Path:
    formatted = template.format(run_id=run_id)
    return Path(formatted).expanduser().resolve()


def glob_paths(pattern: str) -> List[Path]:
    expanded = os.path.expanduser(pattern)
    matches = [Path(match).resolve() for match in glob(expanded)]
    return matches


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_parquet_dataset(pattern: str) -> pl.DataFrame:
    matches = glob_paths(pattern)
    if not matches:
        raise FileNotFoundError(f"No parquet files matched pattern: {pattern}")
    frames = [pl.read_parquet(path.as_posix()) for path in matches]
    return pl.concat(frames, how="vertical") if len(frames) > 1 else frames[0]


def write_parquet(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path.as_posix())


def safe_listdir(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        return os.listdir(path)
    except OSError:
        return []


__all__ = [
    "ensure_dir",
    "expand_path",
    "glob_paths",
    "read_json",
    "write_json",
    "read_parquet_dataset",
    "write_parquet",
    "safe_listdir",
]
