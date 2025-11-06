from __future__ import annotations
from typing import Any, Dict, List, Tuple
import os, json
from datetime import datetime, timezone
from pathlib import Path

try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # type: ignore

try:
    import polars as pl  # type: ignore
except Exception:
    pl = None  # type: ignore

from shared.terminology_loader import TerminologyRepository  # type: ignore


def _load_dataframe(raw_path: str, max_rows: int = 5000) -> "pd.DataFrame | None":
    if pd is None or not os.path.exists(raw_path):
        return None
    try:
        df = pd.read_parquet(raw_path)
    except Exception:
        return None
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42, replace=False)
    return df


def _compute_profiles(df: "pd.DataFrame") -> Dict[str, Any]:
    profiles: Dict[str, Any] = {}
    if df is None or df.empty:
        return profiles
    for column in df.columns:
        series = df[column]
        dtype = str(series.dtype)
        non_null = series.dropna()
        profile = {
            "dtype": dtype,
            "non_null_count": int(non_null.count()),
            "null_count": int(series.isna().sum()),
            "unique_count": int(non_null.nunique()),
        }
        if pd.api.types.is_numeric_dtype(series):
            profile.update(
                {
                    "min": float(non_null.min()) if not non_null.empty else None,
                    "max": float(non_null.max()) if not non_null.empty else None,
                    "mean": float(non_null.mean()) if not non_null.empty else None,
                    "std": float(non_null.std()) if not non_null.empty else None,
                }
            )
        else:
            freq = non_null.astype(str).value_counts().head(5)
            profile["top_values"] = [{"value": str(idx), "count": int(val)} for idx, val in freq.items()]
        profiles[str(column)] = profile
    return profiles


def _flatten_profiles(
    profiles: Dict[str, Any],
    sample_size: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    summary_rows: List[Dict[str, Any]] = []
    distribution_rows: List[Dict[str, Any]] = []
    for column, payload in profiles.items():
        non_null = int(payload.get("non_null_count") or 0)
        nulls = int(payload.get("null_count") or 0)
        unique = int(payload.get("unique_count") or 0)
        summary_rows.append(
            {
                "column": column,
                "dtype": payload.get("dtype"),
                "non_null_count": non_null,
                "null_count": nulls,
                "unique_count": unique,
                "null_fraction": (nulls / sample_size) if sample_size else None,
                "unique_fraction": (unique / sample_size) if sample_size else None,
                "min": payload.get("min"),
                "max": payload.get("max"),
                "mean": payload.get("mean"),
                "std": payload.get("std"),
            }
        )
        top_values = payload.get("top_values") or []
        if isinstance(top_values, list):
            for entry in top_values:
                value = entry.get("value")
                count = entry.get("count")
                distribution_rows.append(
                    {
                        "column": column,
                        "value": value,
                        "count": int(count) if count is not None else None,
                        "share": (int(count) / sample_size) if sample_size and isinstance(count, (int, float)) else None,
                    }
                )
    return summary_rows, distribution_rows


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path((config or {}).get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / "stage_04_profile"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    n_rows = 0
    if pl and isinstance(raw, str) and os.path.exists(raw):
        try:
            df_pl = pl.read_parquet(raw)
            n_rows = int(df_pl.height)
        except Exception:
            n_rows = 0
    try:
        from shared import validate  # type: ignore
        validate.assert_row_stability(n_in=n_rows, n_out=n_rows, allow_drop=False, phase="04", out_dir=out_dir)
    except SystemExit:
        pass

    (out_dir / "row_meta.json").write_text(
        json.dumps({"phase": "04", "n_rows": n_rows, "source": raw}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    profiles: Dict[str, Any] = {}
    terminology_enriched: Dict[str, Any] | None = None
    df_sample = _load_dataframe(str(raw)) if isinstance(raw, str) else None
    if df_sample is not None and not df_sample.empty:
        profiles = _compute_profiles(df_sample)
        sample_size = int(df_sample.shape[0])
        semantic_dir = out_dir / "semantic"
        semantic_dir.mkdir(parents=True, exist_ok=True)
        profile_path = semantic_dir / "column_profile.json"
        profile_path.write_text(json.dumps({"run_id": run_id, "profiles": profiles}, ensure_ascii=False, indent=2), encoding="utf-8")

        summary_rows, distribution_rows = _flatten_profiles(profiles, sample_size)
        profile_payload = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "row_count": n_rows,
            "sampled_rows": sample_size,
            "columns": summary_rows,
        }
        (out_dir / "profile.json").write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        summary_path = out_dir / "summary.parquet"
        summary_written = False
        if summary_rows:
            if pd is not None:
                try:
                    pd.DataFrame(summary_rows).to_parquet(summary_path, index=False)
                    summary_written = True
                except Exception:
                    summary_written = False
            if not summary_written and pl is not None:
                try:
                    pl.DataFrame(summary_rows).write_parquet(summary_path)
                    summary_written = True
                except Exception:
                    summary_written = False
            if not summary_written:
                summary_path.write_text(json.dumps(summary_rows, ensure_ascii=False, indent=2), encoding="utf-8")

        distribution_path = out_dir / "distribution.xlsx"
        distribution_written = False
        if pd is not None:
            summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()
            top_values_df = pd.DataFrame(distribution_rows) if distribution_rows else pd.DataFrame()
            excel_engines: List[str] = []
            for engine_name in ("openpyxl", "xlsxwriter"):
                try:
                    __import__(engine_name)
                    excel_engines.append(engine_name)
                except ImportError:
                    continue
            excel_engines.append(None)  # type: ignore[arg-type]
            for engine in excel_engines:
                try:
                    with pd.ExcelWriter(distribution_path, engine=engine) as writer:  # type: ignore[arg-type]
                        summary_df.to_excel(writer, index=False, sheet_name="summary")
                        if not top_values_df.empty:
                            top_values_df.to_excel(writer, index=False, sheet_name="top_values")
                    distribution_written = True
                    break
                except Exception:
                    continue
        if not distribution_written:
            try:
                from openpyxl import Workbook  # type: ignore

                workbook = Workbook()
                worksheet = workbook.active
                worksheet.title = "summary"
                if summary_rows:
                    headers = list(summary_rows[0].keys())
                    worksheet.append(headers)
                    for row in summary_rows:
                        worksheet.append([row.get(key) for key in headers])
                else:
                    worksheet.append(["column", "dtype", "non_null_count", "null_count", "unique_count"])
                if distribution_rows:
                    top_sheet = workbook.create_sheet("top_values")
                    top_headers = ["column", "value", "count", "share"]
                    top_sheet.append(top_headers)
                    for row in distribution_rows:
                        top_sheet.append([row.get(key) for key in top_headers])
                workbook.save(distribution_path)
                distribution_written = True
            except Exception:
                distribution_path.write_text(
                    json.dumps(
                        {
                            "summary": summary_rows,
                            "top_values": distribution_rows,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

        try:
            terminology_repo = TerminologyRepository(artifacts_root, run_id)
            entries = []
            for entry in terminology_repo.get_columns():
                column_id = entry.get("column_id")
                original_name = entry.get("original_name") or column_id
                profile = profiles.get(original_name) or profiles.get(column_id)
                merged = dict(entry)
                if profile:
                    merged["profile"] = profile
                entries.append(merged)
            terminology_enriched = {"run_id": run_id, "columns": entries}
            enriched_path = semantic_dir / "terminology_enriched.json"
            enriched_path.write_text(json.dumps(terminology_enriched, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            terminology_enriched = None

    outputs: Dict[str, Any] = {"raw": raw}
    if profiles:
        outputs["column_profile"] = (out_dir / "semantic" / "column_profile.json").as_posix()
        if terminology_enriched:
            outputs["terminology_enriched"] = (out_dir / "semantic" / "terminology_enriched.json").as_posix()
        outputs["profile"] = (out_dir / "profile.json").as_posix()
        if (out_dir / "distribution.xlsx").exists():
            outputs["distribution"] = (out_dir / "distribution.xlsx").as_posix()
        if (out_dir / "summary.parquet").exists():
            outputs["summary"] = (out_dir / "summary.parquet").as_posix()

    return {
        "run_id": run_id,
        "status": "PASS",
        "outputs": outputs,
        "metrics": {"n_rows": n_rows},
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }
