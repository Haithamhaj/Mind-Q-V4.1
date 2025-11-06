from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import os
import re
from pathlib import Path

try:
    import pandas as pd  # type: ignore
    from pandas.api import types as ptypes  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore
    ptypes = None  # type: ignore

try:
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover
    pl = None  # type: ignore

from shared import baseline as baseline_utils  # type: ignore
from .terminology import ColumnSummary, build_terminology, canonicalize_column_id  # type: ignore

TERMINOLOGY_SAMPLE_LIMIT = 40
VALUE_COUNTS_LIMIT = 20
PHONE_PATTERN = re.compile(r"[+\(]?\d[\d\)\-\s]{5,}$")


def _load_row_count(raw_path: str) -> int:
    if not os.path.exists(raw_path):
        return 0
    try:
        if pl is not None:
            frame = pl.read_parquet(raw_path)
            return int(frame.height)
        if pd is not None:
            frame_pd = pd.read_parquet(raw_path)
            return int(len(frame_pd))
    except Exception:
        return 0
    return 0


def _load_sample_dataframe(raw_path: str, max_rows: int = 2000) -> "pd.DataFrame":
    if pd is None or not os.path.exists(raw_path):
        raise RuntimeError("pandas is required to build schema terminology samples")
    try:
        df = pd.read_parquet(raw_path)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"failed to read parquet for schema terminology: {exc}") from exc
    if df.empty:
        return df
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42, replace=False)
    return df


def _normalize_for_terminology(
    df: "pd.DataFrame",
    uniqueness_threshold: float,
    *,
    value_counts_limit: int = VALUE_COUNTS_LIMIT,
) -> Tuple["pd.DataFrame", List[Dict[str, Any]], List[str], List[ColumnSummary], Dict[str, Dict[str, Any]]]:
    if pd is None:
        raise RuntimeError("pandas is required to normalize terminology inputs")

    normalized = df.copy()
    entries: List[Dict[str, Any]] = []
    selected_columns: List[str] = []
    summaries: List[ColumnSummary] = []
    value_counts_map: Dict[str, Dict[str, Any]] = {}

    total_rows = len(df)
    if total_rows == 0:
        return normalized, entries, selected_columns, summaries, value_counts_map

    for col in df.columns:
        series = df[col]
        non_null_mask = series.notna()
        non_null_count = int(non_null_mask.sum())
        null_fraction = float(1 - (non_null_count / total_rows)) if total_rows else 0.0

        str_values = series[non_null_mask].astype(str).str.strip()
        str_values = str_values[str_values != ""]
        unique_count = int(str_values.nunique()) if len(str_values) else 0
        unique_ratio = float(unique_count / len(str_values)) if len(str_values) else 0.0

        kind = "text"
        skip_reason: Optional[str] = None
        selected = False

        if ptypes is not None and (ptypes.is_numeric_dtype(series.dtype) or ptypes.is_bool_dtype(series.dtype)):
            kind = "numeric"
            skip_reason = "non_text_dtype"
        elif ptypes is not None and ptypes.is_datetime64_any_dtype(series.dtype):
            kind = "datetime"
            skip_reason = "non_text_dtype"
        else:
            numeric_ratio = float(pd.to_numeric(str_values, errors="coerce").notna().mean()) if len(str_values) else 0.0
            datetime_ratio = (
                float(pd.to_datetime(str_values, errors="coerce", utc=True).notna().mean())
                if len(str_values)
                else 0.0
            )
            phone_ratio = float(str_values.str.fullmatch(PHONE_PATTERN).mean()) if len(str_values) else 0.0

            if numeric_ratio >= 0.95:
                kind = "numeric_text"
                skip_reason = "numeric_text_detected"
                normalized[col] = pd.to_numeric(series, errors="coerce")
            elif datetime_ratio >= 0.95:
                kind = "datetime_text"
                skip_reason = "datetime_text_detected"
                normalized[col] = pd.to_datetime(series, errors="coerce")
            elif phone_ratio >= 0.9:
                kind = "phone_text"
                skip_reason = "phone_pattern_detected"
                normalized[col] = series
            else:
                kind = "text"
                normalized[col] = series.astype(str).str.strip().where(series.notna(), None)
                if len(str_values) == 0:
                    skip_reason = "empty_values"
                else:
                    selected = unique_ratio < uniqueness_threshold
                    if not selected:
                        skip_reason = "unique_ratio_threshold"

        meta: Dict[str, Any] = {
            "column": str(col),
            "original_dtype": str(series.dtype),
            "normalized_dtype": str(normalized[col].dtype),
            "detected_kind": kind,
            "non_null_count": non_null_count,
            "null_fraction": null_fraction,
            "unique_count": unique_count,
            "unique_ratio": unique_ratio,
            "selected_for_terminology": selected,
            "skip_reason": skip_reason,
        }

        if selected:
            meta["skip_reason"] = None
            selected_columns.append(str(col))
            freq_series = str_values.value_counts().head(value_counts_limit)
            top_values = [{"value": str(idx), "count": int(count)} for idx, count in freq_series.items()]
            meta["preview_top_values"] = top_values
            value_counts_map[str(col)] = {
                "unique_count": unique_count,
                "top_values": top_values,
            }
            samples = [str(val) for val in str_values.unique()[:TERMINOLOGY_SAMPLE_LIMIT]]
            summaries.append(
                ColumnSummary(
                    column_id=canonicalize_column_id(col),
                    original_name=str(col),
                    samples=samples,
                    frequent_values=[(str(idx), int(count)) for idx, count in freq_series.items()],
                    dtype=str(normalized[col].dtype),
                    null_fraction=null_fraction,
                    unique_count=unique_count,
                )
            )

        entries.append(meta)

    return normalized, entries, selected_columns, summaries, value_counts_map


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path((config or {}).get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / "stage_03_schema"
    out_dir.mkdir(parents=True, exist_ok=True)
    semantic_dir = out_dir / "semantic"
    semantic_dir.mkdir(parents=True, exist_ok=True)

    raw = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    n_rows = 0
    if isinstance(raw, str):
        n_rows = _load_row_count(raw)
    baseline = baseline_utils.load(artifacts_root, run_id)
    expected_rows = int(baseline.get("n_rows", 0)) if baseline else None
    baseline_utils.enforce_row_guard(expected=expected_rows, actual=n_rows, phase="03", out_dir=out_dir)

    schema_payload = {"info": "schema extracted", "n_rows": n_rows, "source": raw}
    schema_path = out_dir / "schema_v1.json"
    schema_path.write_text(json.dumps(schema_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    row_meta = {"phase": "03", "n_rows": n_rows, "source": raw}
    (out_dir / "row_meta.json").write_text(json.dumps(row_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    terminology_cfg = (config or {}).get("terminology", {})
    terminology_enabled = bool(terminology_cfg.get("enabled", True))
    sample_rows_cfg = int(terminology_cfg.get("sample_rows", 2000))
    uniqueness_threshold = float(terminology_cfg.get("uniqueness_threshold", 0.20))

    logs: List[Dict[str, Any]] = []
    normalization_entries: List[Dict[str, Any]] = []
    selected_columns: List[str] = []
    column_summaries: List[ColumnSummary] = []
    value_counts_map: Dict[str, Dict[str, Any]] = {}
    normalization_error: Optional[str] = None
    normalized_df: Optional["pd.DataFrame"] = None

    if terminology_enabled and isinstance(raw, str) and os.path.exists(raw) and pd is not None:
        try:
            full_df = pd.read_parquet(raw)
        except Exception as exc:  # pragma: no cover
            normalization_error = str(exc)
            logs.append({"event": "normalization_failed", "stage": "read", "error": normalization_error})
            full_df = None
        if full_df is not None:
            if full_df.empty:
                logs.append({"event": "normalization_skipped", "reason": "empty_dataframe"})
            else:
                try:
                    normalized_df, normalization_entries, selected_columns, column_summaries, value_counts_map = _normalize_for_terminology(
                        full_df,
                        uniqueness_threshold,
                    )
                    logs.append(
                        {
                            "event": "normalization_complete",
                            "selected_columns": len(selected_columns),
                            "total_columns": len(normalization_entries),
                            "uniqueness_threshold": uniqueness_threshold,
                        }
                    )
                except Exception as exc:  # pragma: no cover
                    normalization_error = str(exc)
                    logs.append({"event": "normalization_failed", "stage": "transform", "error": normalization_error})
    else:
        if not terminology_enabled:
            logs.append({"event": "normalization_skipped", "reason": "terminology_disabled"})
        elif not isinstance(raw, str) or not raw:
            logs.append({"event": "normalization_skipped", "reason": "missing_raw"})
        elif not os.path.exists(raw):
            logs.append({"event": "normalization_skipped", "reason": "raw_not_found"})
        elif pd is None:
            normalization_error = "pandas_not_available"
            logs.append({"event": "normalization_skipped", "reason": normalization_error})

    normalized_dir = semantic_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalization_report_path = normalized_dir / "normalization_report.json"
    filter_report_path = normalized_dir / "terminology_filter_report.json"
    value_counts_path = normalized_dir / "terminology_value_counts.json"
    normalized_sample_path = normalized_dir / "normalized_sample.parquet"

    normalization_report = {
        "run_id": run_id,
        "status": "error" if normalization_error else "ok",
        "uniqueness_threshold": uniqueness_threshold,
        "total_columns": len(normalization_entries),
        "selected_column_count": len(selected_columns),
        "columns": normalization_entries,
    }
    if normalization_error:
        normalization_report["error"] = normalization_error
    normalization_report_path.write_text(json.dumps(normalization_report, ensure_ascii=False, indent=2), encoding="utf-8")

    filter_report = {
        "run_id": run_id,
        "selected_columns": selected_columns,
        "excluded_columns": [
            {"column": entry["column"], "reason": entry.get("skip_reason")}
            for entry in normalization_entries
            if not entry["selected_for_terminology"]
        ],
    }
    filter_report_path.write_text(json.dumps(filter_report, ensure_ascii=False, indent=2), encoding="utf-8")

    value_counts_payload = {
        "run_id": run_id,
        "columns": value_counts_map,
    }
    value_counts_path.write_text(json.dumps(value_counts_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if pd is not None:
        rows = []
        for column, payload in value_counts_map.items():
            for entry in payload.get("top_values", []):
                rows.append({
                    "column": column,
                    "value": entry.get("value"),
                    "count": entry.get("count"),
                })
        normalized_sample = pd.DataFrame(rows, columns=["column", "value", "count"])
        normalized_sample.to_parquet(normalized_sample_path, index=False)
    else:
        normalized_sample_path.write_text("", encoding="utf-8")

    terminology_result: Optional[Dict[str, Any]] = None
    if terminology_enabled and isinstance(raw, str) and os.path.exists(raw) and pd is not None:
        if column_summaries:
            try:
                terminology_result = build_terminology(
                    None,
                    run_id,
                    semantic_dir,
                    provider=terminology_cfg.get("provider"),
                    model=terminology_cfg.get("model"),
                    temperature=float(terminology_cfg.get("temperature", 0.1)),
                    max_tokens=int(terminology_cfg.get("max_tokens", 800)),
                    max_rows=sample_rows_cfg,
                    uniqueness_threshold=uniqueness_threshold,
                    summaries=column_summaries,
                )
                logs.append({"event": "terminology_generated", "columns": len(column_summaries)})
            except Exception as exc:  # pragma: no cover
                logs.append({"event": "terminology_error", "error": str(exc)})
                terminology_result = {"error": str(exc)}
        else:
            logs.append({"event": "terminology_skipped", "reason": "no_columns_selected"})
    elif not terminology_enabled:
        logs.append({"event": "terminology_skipped", "reason": "disabled"})

    outputs: Dict[str, Any] = {
        "raw": raw,
        "schema": schema_path.as_posix(),
        "normalized_sample": normalized_sample_path.as_posix(),
        "normalization_report": normalization_report_path.as_posix(),
        "terminology_filter_report": filter_report_path.as_posix(),
        "terminology_value_counts": value_counts_path.as_posix(),
    }

    terminology_path: Optional[str] = None
    aliases_path: Optional[str] = None
    glossary_path: Optional[str] = None
    terminology_logs_path: Optional[str] = None

    if terminology_result:
        terminology_path = terminology_result.get("terminology_path")
        aliases_path = terminology_result.get("aliases_path")
        glossary_path = terminology_result.get("glossary_path")
        terminology_logs_path = terminology_result.get("logs_path")

    if not terminology_path:
        default_terminology_path = semantic_dir / "terminology.json"
        if not default_terminology_path.exists():
            default_terminology_path.write_text(
                json.dumps({"run_id": run_id, "columns": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        terminology_path = default_terminology_path.as_posix()

    if not aliases_path:
        default_aliases_path = semantic_dir / "aliases.json"
        if not default_aliases_path.exists():
            default_aliases_path.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")
        aliases_path = default_aliases_path.as_posix()

    if not glossary_path:
        default_glossary_path = semantic_dir / "column_glossary.json"
        if not default_glossary_path.exists():
            default_glossary_path.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
        glossary_path = default_glossary_path.as_posix()

    if not terminology_logs_path:
        default_logs_path = semantic_dir / "terminology_logs.jsonl"
        if not default_logs_path.exists():
            default_logs_path.write_text("", encoding="utf-8")
        terminology_logs_path = default_logs_path.as_posix()

    outputs["terminology"] = terminology_path
    outputs["aliases"] = aliases_path
    outputs["glossary"] = glossary_path
    outputs["terminology_logs"] = terminology_logs_path

    logs_path = out_dir / "logs.jsonl"
    logs_payload = "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in logs)
    logs_path.write_text(logs_payload, encoding="utf-8")

    context = {
        "terminology": terminology_result,
        "normalization": {
            "selected_columns": selected_columns,
            "total_columns": len(normalization_entries),
            "error": normalization_error,
            "uniqueness_threshold": uniqueness_threshold,
        },
    }

    return {
        "run_id": run_id,
        "status": "PASS",
        "outputs": outputs,
        "metrics": {"n_rows": n_rows},
        "context": context,
        "logs_uri": logs_path.as_posix(),
    }
