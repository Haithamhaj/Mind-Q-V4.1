from __future__ import annotations
from typing import Any, Iterable, Dict
import json


def write_jsonl(records: Iterable[Dict[str, Any]], path: str) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
