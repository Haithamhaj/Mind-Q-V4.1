from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_utf8_roundtrip_files(tmp_path: Path) -> None:
    recommendations = {
        "executive_summary": "ملخص تنفيذي بالعربية",
        "recommendations": [
            {"column_name": "حقل", "reason": "توصية عربية", "evidence_key": "columns.حقل.مؤشر"}
        ],
        "invalid_references": [],
    }
    rec_path = tmp_path / "recommendations.json"
    rec_path.write_text(json.dumps(recommendations, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = tmp_path / "executive_summary.md"
    summary_text = "## ملخص\n\nهذا نص عربي للتأكد من الترميز."
    summary_path.write_text(summary_text, encoding="utf-8")

    rec_raw = rec_path.read_text(encoding="utf-8")
    assert "?" not in rec_raw
    loaded = json.loads(rec_raw)
    assert loaded["recommendations"][0]["reason"] == "توصية عربية"
    assert any("\u0600" <= ch <= "\u06FF" for ch in loaded["recommendations"][0]["reason"])

    summary_raw = summary_path.read_text(encoding="utf-8")
    assert summary_raw == summary_text
    assert "?" not in summary_raw


def test_utf8_console_output() -> None:
    cmd = [
        sys.executable,
        "-c",
        "import sys; "
        "sys.stdout.reconfigure(encoding='utf-8'); "
        "print('مرحبا بالعالم')",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
    stdout = result.stdout.strip()
    assert stdout == "مرحبا بالعالم"
    assert "?" not in stdout
