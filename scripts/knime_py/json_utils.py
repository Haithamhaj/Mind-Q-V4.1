from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union


def to_compact_json(data: Any) -> str:
    """Serialize payloads using compact separators while keeping UTF-8 characters."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def write_json_file(path: Union[str, Path], data: Any) -> None:
    """Persist JSON to disk with a readable indentation."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
