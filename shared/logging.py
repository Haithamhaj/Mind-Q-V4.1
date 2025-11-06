from __future__ import annotations
from typing import Any, Iterable, Dict
import json
import logging


def write_jsonl(records: Iterable[Dict[str, Any]], path: str) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def setup_logger(file_path: str) -> logging.Logger:
    handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(f"eda.{file_path}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    handler.setFormatter(formatter)
    return logger
