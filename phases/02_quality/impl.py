from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from shared import baseline as baseline_utils  # type: ignore

try:  # pragma: no cover - optional
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover
    pl = None  # type: ignore

PHONE_PATTERN = re.compile(r"(phone|mobile|msisdn|whatsapp)", re.IGNORECASE)
DATETIME_HINT = re.compile(r"(date|time|timestamp)", re.IGNORECASE)
NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7F]")
CARDINALITY_WARN_RATIO = 0.9
CARDINALITY_WARN_COUNT = 500

StageOutputs = Dict[str, Any]
IssueEntry = Dict[str, Any]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_table(raw_path: Path) -> Any:
    if pl is not None:
        try:
            return pl.read_parquet(raw_path.as_posix())  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - fallback to pandas
            pass
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pandas is required for phase 02 quality checks") from exc
    return pd.read_parquet(raw_path)


def _to_pandas(df: Any) -> Any:
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover
        pd = None  # type: ignore
    else:
        if isinstance(df, pd.DataFrame):
            return df
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return df.to_pandas()
    raise RuntimeError("unable to convert dataframe to pandas for quality checks")


def _schema_hash(columns: List[str]) -> str:
    ordered = "\n".join(sorted(columns))
    import hashlib

    return hashlib.sha256(ordered.encode("utf-8")).hexdigest()


def _detect_phone_columns(columns: List[str]) -> List[str]:
    return [col for col in columns if PHONE_PATTERN.search(col)]


def _write_logs(out_dir: Path, logs: List[Dict[str, Any]]) -> None:
    log_path = out_dir / "logs.jsonl"
    with log_path.open("w", encoding="utf-8") as handle:
        for entry in logs:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> StageOutputs:  # type: ignore[override]
    stage_id = "stage_02_quality"
    cfg_any: Dict[str, Any] = config or {}
    artifacts_root = Path(cfg_any.get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / stage_id
    _ensure_dir(out_dir)

    raw_uri = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    if not isinstance(raw_uri, str):
        raise ValueError("Stage 02 requires inputs['raw'] to point to stage_01 raw parquet")
    raw_path = Path(raw_uri).expanduser().resolve()
    if not raw_path.exists():
        raise FileNotFoundError(f"raw parquet not found: {raw_path}")

    baseline = baseline_utils.load(artifacts_root, run_id)
    baseline_rows = int(baseline.get("n_rows", 0))
    baseline_schema_hash = baseline.get("schema_hash")

    logs: List[Dict[str, Any]] = []
    issues: List[IssueEntry] = []

    try:
        table = _read_table(raw_path)
    except Exception as exc:
        report = {
            "run_id": run_id,
            "status": "STOP",
            "error": f"failed_to_read_raw: {exc}",
        }
        (out_dir / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_logs(out_dir, [{"rule": "read_raw", "severity": "STOP", "message": str(exc)}])
        raise RuntimeError(f"Phase 02 unable to read input parquet: {exc}") from exc

    pdf = _to_pandas(table)
    n_rows = int(len(pdf))
    n_cols = int(len(pdf.columns))
    columns = [str(col) for col in pdf.columns]

    if n_rows == 0:
        (out_dir / "row_meta.json").write_text(json.dumps({"phase": "02", "n_rows": n_rows, "source": raw_path.as_posix()}, ensure_ascii=False, indent=2), encoding="utf-8")
        report_zero = {
            "run_id": run_id,
            "status": "STOP",
            "metrics": {"n_rows": 0, "n_cols": n_cols},
            "reason": "zero_rows",
        }
        (out_dir / "quality_report.json").write_text(json.dumps(report_zero, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_logs(out_dir, [{"rule": "row_guard", "severity": "STOP", "message": "input resulted in zero rows"}])
        baseline_utils.enforce_row_guard(
            expected=baseline_rows if baseline_rows else None,
            actual=n_rows,
            phase="02",
            out_dir=out_dir,
            reason="zero_rows_detected",
            force=True,
        )

    if baseline_rows and n_rows != baseline_rows:
        (out_dir / "row_meta.json").write_text(json.dumps({"phase": "02", "n_rows": n_rows, "source": raw_path.as_posix()}, ensure_ascii=False, indent=2), encoding="utf-8")
        report_mismatch = {
            "run_id": run_id,
            "status": "STOP",
            "metrics": {"n_rows": n_rows, "n_cols": n_cols},
            "reason": "row_count_mismatch",
        }
        (out_dir / "quality_report.json").write_text(json.dumps(report_mismatch, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_logs(out_dir, [{"rule": "row_guard", "severity": "STOP", "expected": baseline_rows, "actual": n_rows}])
        baseline_utils.enforce_row_guard(
            expected=baseline_rows,
            actual=n_rows,
            phase="02",
            out_dir=out_dir,
        )

    now_utc = datetime.now(timezone.utc)
    future_cutoff = now_utc + timedelta(hours=24)

    phone_columns = _detect_phone_columns(columns)
    try:
        import pandas as pd  # type: ignore
        from pandas.api import types as ptypes  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pandas is required for quality metrics") from exc

    for col in phone_columns:
        dtype = pdf[col].dtype if col in pdf.columns else None
        if col in pdf.columns and not ptypes.is_string_dtype(dtype):
            sample_value = pdf[col].dropna().iloc[0] if pdf[col].dropna().shape[0] else None
            issues.append({"col": col, "issue": "phone_column_not_string", "severity": "WARN", "sample_value": sample_value, "n": int(pdf[col].notna().sum()), "pct": 1.0})
            logs.append({"rule": "dtype_guard", "column": col, "severity": "WARN", "dtype": str(dtype)})

    # Missingness
    missing_counts = pdf.isna().sum()
    missing_gt_20 = 0
    for col, count in missing_counts.items():
        if count == 0:
            continue
        pct = float(count) / float(n_rows) if n_rows else math.nan
        severity = "WARN" if pct >= 0.2 else "NOTE"
        if pct >= 0.2:
            missing_gt_20 += 1
        sample_value = None
        issues.append({"col": col, "issue": "missing_values", "severity": severity, "sample_value": sample_value, "n": int(count), "pct": pct})
        logs.append({"rule": "missingness", "column": col, "severity": severity, "count": int(count), "pct": pct})

    # Non ASCII
    for col in pdf.columns:
        series = pdf[col]
        if not ptypes.is_string_dtype(series.dtype):
            continue
        mask = series.dropna().astype(str).str.contains(NON_ASCII_PATTERN)
        count = int(mask.sum())
        if count == 0:
            continue
        sample_value = series.dropna().astype(str)[mask].iloc[0]
        issues.append({"col": str(col), "issue": "non_ascii_characters", "severity": "NOTE", "sample_value": sample_value, "n": count, "pct": count / float(n_rows)})
        logs.append({"rule": "non_ascii", "column": str(col), "severity": "NOTE", "count": count})

    # Datetime checks
    datetime_columns: List[str] = []
    for col in pdf.columns:
        series = pdf[col]
        if ptypes.is_datetime64_any_dtype(series.dtype) or DATETIME_HINT.search(str(col)):
            datetime_columns.append(str(col))

    invalid_datetime_cols: List[str] = []
    future_datetime_cols: List[str] = []
    for col in datetime_columns:
        series = pdf[col]
        parsed = pd.to_datetime(series, errors="coerce", utc=True)
        invalid_mask = series.notna() & parsed.isna()
        invalid_count = int(invalid_mask.sum())
        if invalid_count:
            invalid_datetime_cols.append(col)
            issues.append({"col": col, "issue": "invalid_datetime", "severity": "WARN", "sample_value": series[invalid_mask].iloc[0], "n": invalid_count, "pct": invalid_count / float(n_rows)})
            logs.append({"rule": "invalid_datetimes", "column": col, "severity": "WARN", "count": invalid_count})
        future_mask = parsed.notna() & (parsed > future_cutoff)
        future_count = int(future_mask.sum())
        if future_count:
            future_datetime_cols.append(col)
            issues.append({"col": col, "issue": "future_datetime", "severity": "WARN", "sample_value": series[future_mask].iloc[0], "n": future_count, "pct": future_count / float(n_rows)})
            logs.append({"rule": "future_datetimes", "column": col, "severity": "WARN", "count": future_count, "cutoff": future_cutoff.isoformat()})

    # Cardinality
    high_cardinality_cols: List[str] = []
    for col in pdf.columns:
        series = pdf[col]
        if ptypes.is_numeric_dtype(series.dtype):
            continue
        uniques = int(series.nunique(dropna=True))
        if uniques == 0:
            continue
        ratio = uniques / float(n_rows) if n_rows else math.nan
        if uniques >= CARDINALITY_WARN_COUNT or (n_rows and ratio >= CARDINALITY_WARN_RATIO):
            high_cardinality_cols.append(str(col))
            issues.append({"col": str(col), "issue": "high_cardinality", "severity": "WARN", "sample_value": None, "n": uniques, "pct": ratio})
            logs.append({"rule": "high_cardinality", "column": str(col), "severity": "WARN", "unique": uniques, "ratio": ratio})

    # Schema hash comparison (informational)
    current_schema_hash = _schema_hash(columns)
    schema_changed = baseline_schema_hash and baseline_schema_hash != current_schema_hash
    if schema_changed:
        issues.append({"col": "_schema", "issue": "schema_hash_changed", "severity": "NOTE", "sample_value": current_schema_hash, "n": n_cols, "pct": 1.0})
        logs.append({"rule": "schema_hash", "severity": "NOTE", "baseline": baseline_schema_hash, "current": current_schema_hash})

    severity_counts: Dict[str, int] = {}

    status = "PASS"
    if any(issue["severity"] == "WARN" for issue in issues):
        status = "WARN"
    for issue in issues:
        severity = issue.get("severity", "INFO")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    metrics = {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "missing_gt_20_columns": missing_gt_20,
        "schema_hash": current_schema_hash,
        "phone_columns": phone_columns,
    }

    report = {
        "run_id": run_id,
        "status": status,
        "metrics": metrics,
        "issues": len(issues),
    }
    (out_dir / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if issues:
        issues_df = pd.DataFrame(issues)
        issues_path = out_dir / "issues.parquet"
        issues_df.to_parquet(issues_path, index=False)
    else:
        # Ensure file exists even when no issues
        issues_path = out_dir / "issues.parquet"
        pd.DataFrame([], columns=["col", "issue", "severity", "sample_value", "n", "pct"]).to_parquet(issues_path, index=False)

    _write_logs(out_dir, logs)

    row_meta = {"phase": "02", "n_rows": n_rows, "source": raw_path.as_posix()}
    (out_dir / "row_meta.json").write_text(json.dumps(row_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    quality_overview = {
        "run_id": run_id,
        "status": status,
        "metrics": metrics,
        "issues_total": len(issues),
        "issues_by_severity": severity_counts,
        "signals": {
            "phone_columns": phone_columns,
            "missing_gt_20_columns": missing_gt_20,
            "high_cardinality_columns": high_cardinality_cols,
            "invalid_datetime_columns": invalid_datetime_cols,
            "future_datetime_columns": future_datetime_cols,
        },
        "schema_hash": {
            "current": current_schema_hash,
            "baseline": baseline_schema_hash,
            "changed": bool(schema_changed),
        },
    }
    overview_path = out_dir / "quality_overview.json"
    overview_path.write_text(json.dumps(quality_overview, ensure_ascii=False, indent=2), encoding="utf-8")

    shape_guard = {
        "run_id": run_id,
        "status": "PASS",
        "rows": {"baseline": baseline_rows, "current": n_rows},
        "schema_hash": {"baseline": baseline_schema_hash, "current": current_schema_hash},
    }
    shape_guard_path = out_dir / "shape_guard.json"
    shape_guard_path.write_text(json.dumps(shape_guard, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_id": run_id,
        "status": status,
        "outputs": {
            "raw": raw_path.as_posix(),
            "issues": issues_path.as_posix(),
            "quality_overview": overview_path.as_posix(),
            "shape_guard": shape_guard_path.as_posix(),
        },
        "metrics": metrics,
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }


__all__ = ["run"]
