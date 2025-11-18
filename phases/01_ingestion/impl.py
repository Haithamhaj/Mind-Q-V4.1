from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Set

try:  # pragma: no cover - optional
    import polars as pl  # type: ignore
except Exception:  # pragma: no cover
    pl = None  # type: ignore

from shared import sla as sla_utils  # type: ignore
from backend.src.app.services.system_health import SystemHealth  # type: ignore

# Fallback pandas import is deferred until needed

StageOutputs = Dict[str, Any]
SourceEntry = Dict[str, Any]
PhoneColumns = List[str]

PHONE_PATTERN = re.compile(r"(phone|mobile|msisdn|whatsapp)", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(
    r"(awb|waybill|tracking|shipment|shipmentno|shipment_id|order_id|orderno|reference|ref_|refno|ref#|"
    r"consignment|account|customer|invoice|msisdn|phone|uuid|guid|id$|_id$)",
    re.IGNORECASE,
)
SCIENTIFIC_TOKEN = re.compile(r"^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$")
STREAMING_ENV_FLAG = "MINDQ_ENABLE_STREAMING_INGESTION"
STREAMING_SUFFIXES = {".csv", ".tsv", ".txt"}
PHASE_ID = "01_ingestion"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _read_file_polars(path: Path) -> Tuple[Any, str]:
    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pl.read_parquet(path.as_posix())  # type: ignore[call-arg]
        reader = "polars_parquet"
    else:
        df = pl.read_csv(path.as_posix())  # type: ignore[call-arg]
        reader = "polars_csv"
    return df, reader


def _read_file_pandas(path: Path) -> Tuple[Any, str]:
    import pandas as pd  # type: ignore

    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
        reader = "pandas_parquet"
    else:
        df = pd.read_csv(path, engine="python")
        reader = "pandas_csv"
    return df, reader


def _schema_hash(columns: List[str]) -> str:
    ordered = "\n".join(sorted(columns))
    return hashlib.sha256(ordered.encode("utf-8")).hexdigest()


def _detect_phone_columns(columns: List[str]) -> PhoneColumns:
    return [col for col in columns if PHONE_PATTERN.search(col)]


def _streaming_enabled() -> bool:
    value = os.getenv(STREAMING_ENV_FLAG)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _streaming_schema(path: Path, separator: str = ",") -> Optional[Dict[str, Any]]:
    if pl is None:
        return None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            reader = csv.reader(handle, delimiter=separator)
            header = next(reader, None)
    except Exception:
        return None
    if not header:
        return None
    schema = {}
    for name in header:
        if not name:
            continue
        schema[name] = pl.Utf8  # type: ignore[attr-defined]
    return schema


def _ingest_streaming(files: Sequence[Path], target_path: Path) -> Tuple[Optional[Path], Optional[str]]:
    if pl is None:
        return None, None
    sources = [path for path in files if path.suffix.lower() in STREAMING_SUFFIXES]
    if not sources:
        return None, None
    lazy_frames = []
    error_detail: Optional[str] = None
    for path in sources:
        try:
            separator = "\t" if path.suffix.lower() == ".tsv" else ","
            schema_overrides = _streaming_schema(path, separator=separator)
            options: Dict[str, Any] = {}
            if path.suffix.lower() == ".tsv":
                options["separator"] = "\t"
            if schema_overrides:
                options["schema_overrides"] = schema_overrides
            lazy_frames.append(pl.scan_csv(path.as_posix(), **options))  # type: ignore[call-arg]
        except Exception as exc:
            error_detail = f"{path.name}:{exc}"
            lazy_frames = []
            break
    if not lazy_frames:
        return None, error_detail
    try:
        lazy = lazy_frames[0] if len(lazy_frames) == 1 else pl.concat(lazy_frames)  # type: ignore[arg-type]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        lazy.sink_parquet(target_path.as_posix())  # type: ignore[attr-defined]
    except Exception as exc:
        return None, f"sink_error:{exc}"
    return target_path, None


def _log_record(run_id: str, level: str, message: str, event: str = "streaming_ingestion") -> Dict[str, Any]:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE_ID,
        "run_id": run_id,
        "event": event,
        "level": level,
        "message": message,
    }


def _write_logs(records: List[Dict[str, Any]], path: Path) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _coerce_phone_columns(df: Any, columns: PhoneColumns) -> Any:
    if not columns:
        return df
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return df.with_columns([pl.col(col).cast(pl.Utf8, strict=False).alias(col) for col in columns])  # type: ignore[arg-type]
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        return df
    if isinstance(df, pd.DataFrame):
        for col in columns:
            if col in df.columns:
                df[col] = df[col].astype("string")
    return df


def _normalize_columns(df: Any, ingest_cfg: Dict[str, Any]) -> Tuple[Any, Dict[str, List[str]]]:
    result: Dict[str, List[str]] = {"dtype_overrides": [], "auto_string_cast": []}
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return df, result

    is_polars_frame = pl is not None and isinstance(df, pl.DataFrame)  # type: ignore[attr-defined]
    if is_polars_frame:
        working_df = df.to_pandas()  # type: ignore[attr-defined]
    elif isinstance(df, pd.DataFrame):
        working_df = df.copy()
    else:
        working_df = pd.DataFrame(df)

    dtype_overrides_cfg = ingest_cfg.get("dtype_overrides") or {}
    for col, target in dtype_overrides_cfg.items():
        if col not in working_df.columns:
            continue
        target_str = str(target).lower()
        if target_str in {"string", "str", "text"}:
            working_df[col] = working_df[col].astype("string")
            working_df[col] = working_df[col].fillna("")
            result["dtype_overrides"].append(col)
        elif target_str in {"float", "float64", "double"}:
            working_df[col] = pd.to_numeric(working_df[col], errors="coerce")
            result["dtype_overrides"].append(col)
        elif target_str in {"int", "int64", "integer"}:
            working_df[col] = pd.to_numeric(working_df[col], errors="coerce").astype("Int64")
            result["dtype_overrides"].append(col)

    object_cols = working_df.select_dtypes(include=["object"]).columns
    for col in object_cols:
        series = working_df[col]
        non_null = series.dropna()
        if non_null.empty:
            continue
        sample_types = {type(value) for value in non_null.head(1000)}
        if len(sample_types) > 1:
            working_df[col] = series.map(lambda value: "" if pd.isna(value) else str(value))
            working_df[col] = working_df[col].astype("string")
            result["auto_string_cast"].append(col)

    if is_polars_frame and pl is not None:
        normalized_df = pl.from_pandas(working_df)  # type: ignore[call-arg]
    else:
        normalized_df = working_df

    return normalized_df, result


def _to_polars(df: Any) -> Any:
    if pl is None:
        return df
    if isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return df
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        return df
    if isinstance(df, pd.DataFrame):
        return pl.from_pandas(df)  # type: ignore[call-arg]
    return df


def _compute_missing_summary(df: Any) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
        from pandas.api import types as ptypes  # type: ignore
    except Exception:  # pragma: no cover - defensive
        return []

    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        working = df.to_pandas()  # type: ignore[attr-defined]
    elif isinstance(df, pd.DataFrame):
        working = df.copy()
    else:
        try:
            working = pd.DataFrame(df)
        except Exception:  # pragma: no cover - defensive
            return []

    total_rows = len(working.index)
    if total_rows == 0:
        return []

    summary: List[Dict[str, Any]] = []
    for column in working.columns:
        series = working[column]
        missing = int(series.isna().sum())
        non_null = total_rows - missing
        missing_pct = float(missing / total_rows) if total_rows else 0.0
        unique_non_null = int(series.nunique(dropna=True))
        dtype = str(series.dtype)
        blank_count = 0
        if ptypes.is_string_dtype(series.dtype) or series.dtype == object:
            try:
                stripped = series.astype("string").str.strip()
                blank_count = int(stripped.eq("").sum())
            except Exception:
                blank_count = 0
        try:
            samples = [str(value) for value in series.dropna().head(3).tolist()]
        except Exception:
            samples = []
        summary.append(
            {
                "column": str(column),
                "dtype": dtype,
                "row_count": total_rows,
                "non_null": non_null,
                "missing": missing,
                "missing_pct": missing_pct,
                "blank": blank_count,
                "unique": unique_non_null,
                "sample_values": samples,
            }
        )
    return summary


def _coerce_identifier_columns_to_string(df: Any) -> Tuple[Any, List[str]]:
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - defensive
        return df, []

    is_polars_frame = pl is not None and isinstance(df, pl.DataFrame)  # type: ignore[attr-defined]
    if is_polars_frame:
        working = df.to_pandas()  # type: ignore[attr-defined]
    elif isinstance(df, pd.DataFrame):
        working = df.copy()
    else:
        try:
            working = pd.DataFrame(df)
        except Exception:  # pragma: no cover - defensive
            return df, []

    coerced: List[str] = []
    seen: Set[str] = set()

    def _series_to_string_dtype(series: pd.Series) -> pd.Series:
        mask = series.isna()
        as_str = series.astype(str)
        if mask.any():
            as_str = as_str.where(~mask, None)
        try:
            return as_str.astype("string[python]")
        except Exception:
            return as_str.astype(object)

    for column in working.columns:
        series = working[column]
        column_name = str(column)
        should_coerce = bool(IDENTIFIER_PATTERN.search(column_name))

        sample = series.dropna()
        if not should_coerce and not sample.empty:
            sample_text = sample.astype(str)
            if sample_text.str.contains(r"[Ee][+-]?\d+$", regex=True).any():
                should_coerce = True
            elif sample_text.str.contains(r"^\d{12,}$", regex=True).any():
                should_coerce = True
            else:
                head_text = sample_text.head(100)
                if any(SCIENTIFIC_TOKEN.match(value.strip()) for value in head_text):
                    should_coerce = True

        if should_coerce:
            working[column] = _series_to_string_dtype(series)
            if column_name not in seen:
                coerced.append(column_name)
                seen.add(column_name)

    for column in working.columns:
        column_name = str(column)
        if column_name in seen:
            continue
        series = working[column]
        sample = series.dropna()
        if sample.empty:
            continue
        sample_text = sample.astype(str)
        if sample_text.str.contains(r"[Ee][+-]?\d+$", regex=True).any():
            working[column] = _series_to_string_dtype(series)
            coerced.append(column_name)
            seen.add(column_name)

    return working, coerced


def _detect_numeric_identifier_columns(df: Any) -> List[str]:
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - defensive
        return []

    numeric_identifiers: List[str] = []
    if isinstance(df, pd.DataFrame):
        candidates = df.select_dtypes(include=["number"]).columns
        for column in candidates:
            series = df[column].dropna()
            if series.empty:
                continue
            try:
                series_float = series.astype(float)
            except Exception:
                continue
            max_abs = float(series_float.abs().max())
            if max_abs < 1e9:
                continue
            remainder = (series_float % 1).abs()
            if remainder.gt(1e-6).any():
                continue
            numeric_identifiers.append(str(column))
    return numeric_identifiers


def _coerce_columns_to_strings(df: Any, columns: List[str]) -> Any:
    if not columns:
        return df
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - defensive
        return df
    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except Exception:  # pragma: no cover - defensive
            return df
    if not columns:
        return df
    df = df.copy()
    for column in columns:
        if column not in df.columns:
            continue
        series = df[column]
        mask = series.isna()
        as_str = series.astype(str)
        if mask.any():
            as_str = as_str.where(~mask, None)
        try:
            df[column] = as_str.astype("string[python]")
        except Exception:
            df[column] = as_str.astype(object)
    return df


def _write_parquet_with_retry(df: Any, path: Path, *, max_attempts: int = 3) -> Tuple[Any, List[str]]:
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError("pandas is required to persist parquet outputs") from exc

    if isinstance(df, pd.DataFrame):
        working = df.copy()
    elif pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        working = df.to_pandas()  # type: ignore[attr-defined]
    else:
        working = pd.DataFrame(df)

    coerced: List[str] = []
    attempt = 0
    last_error: Optional[str] = None
    def _resolve_column_name(candidate: str) -> Optional[str]:
        normalized = candidate.strip().strip("\"'")
        if normalized in working.columns:
            return normalized
        target_normalized = normalized.lower()
        for existing in working.columns:
            existing_str = str(existing)
            if existing_str == normalized:
                return existing_str
            if existing_str.lower() == target_normalized:
                return existing_str
            if existing_str.strip().lower() == target_normalized:
                return existing_str
        return None

    while attempt < max_attempts:
        attempt += 1
        try:
            _write_parquet(working, path)
            return working, coerced
        except Exception as exc:
            message = str(exc)
            last_error = message or repr(exc)
            conversion_match = re.search(r"Conversion failed for column (.+?) with type object", message)
            if conversion_match:
                column_name = _resolve_column_name(conversion_match.group(1))
                if column_name is not None:
                    try:
                        working[column_name] = pd.to_numeric(working[column_name], errors="coerce")
                        if column_name not in coerced:
                            coerced.append(column_name)
                        continue
                    except Exception:
                        pass
            match = re.search(r"Could not convert '([^']+)'", message)
            if not match:
                raise
            offending_value = match.group(1)
            candidate_columns: List[str] = []
            offending_pattern = re.escape(offending_value)
            for column in working.columns:
                series = working[column]
                try:
                    series_text = series.astype(str)
                except Exception:
                    continue
                if series_text.str.contains(offending_pattern, regex=True).any():
                    candidate_columns.append(str(column))
            if not candidate_columns:
                raise
            numeric_handled = False
            for column in candidate_columns:
                try:
                    numeric_series = pd.to_numeric(working[column], errors="coerce")
                except Exception:
                    continue
                if numeric_series.notna().any():
                    working[column] = numeric_series
                    if column not in coerced:
                        coerced.append(column)
                    numeric_handled = True
            if numeric_handled:
                continue
            working = _coerce_columns_to_strings(working, candidate_columns)
            for column in candidate_columns:
                if column not in coerced:
                    coerced.append(column)
    detail = (
        f"Failed to persist parquet after {max_attempts} attempts for {path}. "
        f"Last error: {last_error}. Coerced columns: {coerced or ['<none>']}."
    )
    raise RuntimeError(detail)


def _write_parquet(df: Any, path: Path) -> None:
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover - optional
        raise RuntimeError("pandas is required to write parquet") from exc
    
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        working = df.to_pandas()  # type: ignore[attr-defined]
    elif isinstance(df, pd.DataFrame):
        working = df
    else:  # pragma: no cover - fallback attempt
        working = pd.DataFrame(df)
    
    # Ensure object columns with strings are properly typed as string
    for col in working.columns:
        if working[col].dtype == 'object':
            # Check if column contains strings
            sample = working[col].dropna().head(10)
            if not sample.empty and any(isinstance(x, str) for x in sample):
                working[col] = working[col].astype('string')
    
    working.to_parquet(path, index=False)


def _n_rows(df: Any) -> int:
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return int(df.height)  # type: ignore[attr-defined]
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        pd = None  # type: ignore
    if pd is not None and isinstance(df, pd.DataFrame):
        return int(df.shape[0])
    return int(len(df))  # pragma: no cover - generic fallback


def _n_cols(df: Any) -> int:
    if pl is not None and isinstance(df, pl.DataFrame):  # type: ignore[attr-defined]
        return int(len(df.columns))  # type: ignore[attr-defined]
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        pd = None  # type: ignore
    if pd is not None and isinstance(df, pd.DataFrame):
        return int(df.shape[1])
    return int(len(getattr(df, "columns", [])))


def _columns(df: Any) -> List[str]:
    cols = list(getattr(df, "columns", []))
    return [str(c) for c in cols]


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> StageOutputs:  # type: ignore[override]
    start_ts = time.perf_counter()
    stage_id = "stage_01_ingestion"
    cfg_any: Dict[str, Any] = config or {}
    ingest_cfg: Dict[str, Any] = cfg_any.get("ingestion") or {}
    artifacts_root = Path(cfg_any.get("artifacts_root", "artifacts"))
    health = SystemHealth(artifacts_root=artifacts_root)
    out_dir = artifacts_root / run_id / stage_id
    _ensure_dir(out_dir)
    logs: List[Dict[str, Any]] = []

    data_files_any = inputs.get("data_files")
    files_any = data_files_any if data_files_any is not None else inputs.get("files")
    if isinstance(files_any, tuple):
        files_any = list(files_any)
    if not isinstance(files_any, list) or not files_any:
        raise ValueError("inputs['data_files'] or inputs['files'] must be a non-empty list of file paths")

    sla_files_any = inputs.get("sla_files") or []
    if isinstance(sla_files_any, tuple):
        sla_files_any = list(sla_files_any)
    if not isinstance(sla_files_any, list):
        raise ValueError("inputs['sla_files'] must be a list of file paths when provided")

    sla_processed_root_value = cfg_any.get("sla_processed_root", Path("contracts") / "sla_processed")
    sla_processed_root = Path(sla_processed_root_value)
    sla_processed_dir = sla_processed_root / run_id
    sla_manifest_entries: List[Dict[str, Any]] = []
    sla_manifest_notes: List[str] = []
    sla_manifest_path: Optional[Path] = None
    sla_bundle_path: Optional[Path] = None

    resolved_files: List[Path] = []
    source_meta: List[SourceEntry] = []
    min_file_size = int(ingest_cfg.get("min_file_size_bytes", 100 * 1024))
    min_rows_required = int(ingest_cfg.get("min_rows", 10))

    for raw_path in files_any:
        candidate = Path(str(raw_path)).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"input file does not exist: {candidate}")
        stats = candidate.stat()
        source_meta.append(
            {
                "abs_path": candidate.as_posix(),
                "filesize_bytes": int(stats.st_size),
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "reader": None,
                "sheet": None,
            }
        )
        if stats.st_size < min_file_size:
            payload = {
                "phase": "01",
                "n_rows": 0,
                "reason": "input_file_too_small",
                "path": candidate.as_posix(),
                "filesize_bytes": int(stats.st_size),
            }
            (out_dir / "shape_mismatch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "source_meta.json").write_text(json.dumps({"files": source_meta}, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "row_meta.json").write_text(json.dumps({"phase": "01", "n_rows": 0, "source": candidate.as_posix()}, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {
                "run_id": run_id,
                "status": "STOP",
                "outputs": {},
                "metrics": {"n_rows": 0, "n_cols": 0},
                "logs_uri": str(out_dir / "logs.jsonl"),
                "stops": ["input_file_too_small"],
            }
            _write_logs(logs, out_dir / "logs.jsonl")
            return result
        resolved_files.append(candidate)

    streaming_path: Optional[Path] = None
    if resolved_files and _streaming_enabled():
        streaming_path, streaming_error = _ingest_streaming(resolved_files, out_dir / "raw_streaming.parquet")
        if streaming_error:
            logs.append(
                _log_record(
                    run_id,
                    "WARN",
                    f"streaming ingestion failed, falling back to legacy eager path: {streaming_error}",
                )
            )
            streaming_path = None

    if sla_files_any:
        sla_storage_dir = out_dir / "sla_raw"
        for raw_sla in sla_files_any:
            candidate = Path(str(raw_sla)).expanduser().resolve()
            if not candidate.exists():
                raise FileNotFoundError(f"SLA file does not exist: {candidate}")
            try:
                entry = sla_utils.process_sla_file(
                    candidate,
                    run_id=run_id,
                    storage_dir=sla_storage_dir,
                    processed_dir=sla_processed_dir,
                )
            except Exception as exc:  # pragma: no cover - defensive
                message = f"{exc.__class__.__name__}:{exc}"
                sla_manifest_notes.append(f"processing_error::{candidate.name}::{message}")
                entry = {
                    "source_path": candidate.as_posix(),
                    "stored_path": None,
                    "normalized_path": None,
                    "media_type": None,
                    "size_bytes": candidate.stat().st_size if candidate.exists() else None,
                    "sha256": None,
                    "terms": [],
                    "notes": [f"processing_error::{message}"],
                }
            sla_manifest_entries.append(entry)
        manifest_payload = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entries": sla_manifest_entries,
            "notes": sla_manifest_notes,
            "processed_root": sla_processed_dir.as_posix(),
        }
        sla_manifest_path = out_dir / "sla_manifest.json"
        sla_manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        sla_bundle_path = sla_processed_dir / "contracts.json"
        sla_bundle_path.parent.mkdir(parents=True, exist_ok=True)
        sla_bundle_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    frames: List[Any] = []
    readers: List[str] = []
    for idx, path in enumerate(resolved_files):
        df: Any
        reader = ""
        polars_error: Optional[Exception] = None
        if pl is not None:
            try:
                df, reader = _read_file_polars(path)
            except Exception as exc:  # pragma: no cover - fallback to pandas
                polars_error = exc
                reader = ""
        if not reader:
            try:
                df, reader = _read_file_pandas(path)
            except Exception as exc:
                if polars_error is not None:
                    raise RuntimeError(f"failed to read {path} with polars ({polars_error}) and pandas ({exc})") from exc
                raise RuntimeError(f"failed to read {path}: {exc}") from exc
            if polars_error is not None:
                source_meta[idx]["reader_error"] = str(polars_error)
        frames.append(df)
        readers.append(reader)
        source_meta[idx]["reader"] = reader

    if not frames:
        raise RuntimeError("no frames were read from the provided inputs")

    if pl is not None and all(isinstance(df, pl.DataFrame) for df in frames):  # type: ignore[attr-defined]
        combined = pl.concat(frames, how="diagonal")  # type: ignore[var-annotated]
    else:
        try:
            import pandas as pd  # type: ignore
        except Exception as exc:  # pragma: no cover - optional
            raise RuntimeError("pandas is required when polars is unavailable") from exc
        combined = pd.concat(frames, ignore_index=True)  # type: ignore[arg-type]

    n_rows = _n_rows(combined)
    n_cols = _n_cols(combined)

    if n_rows < min_rows_required:
        payload = {"phase": "01", "n_rows": n_rows, "reason": "too_few_rows"}
        (out_dir / "shape_mismatch.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "source_meta.json").write_text(json.dumps({"files": source_meta}, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "row_meta.json").write_text(json.dumps({"phase": "01", "n_rows": n_rows, "source": resolved_files[0].as_posix()}, ensure_ascii=False, indent=2), encoding="utf-8")
        elapsed = time.perf_counter() - start_ts
        minutes = elapsed / 60.0
        denom = max(n_rows / 1_000_000.0, 1e-6)
        health.log_ingestion_latency(run_id, n_rows, minutes / denom)
        health.emit_report(extra={"stage": stage_id, "status": "STOP"})
        result = {
            "run_id": run_id,
            "status": "STOP",
            "outputs": {},
            "metrics": {"n_rows": n_rows, "n_cols": n_cols},
            "logs_uri": str(out_dir / "logs.jsonl"),
            "stops": ["too_few_rows"],
        }
        _write_logs(logs, out_dir / "logs.jsonl")
        return result

    columns = _columns(combined)
    phone_columns = _detect_phone_columns(columns)
    if phone_columns:
        combined = _coerce_phone_columns(combined, phone_columns)
        columns = _columns(combined)

    combined, identifier_columns_coerced = _coerce_identifier_columns_to_string(combined)
    numeric_identifier_columns = _detect_numeric_identifier_columns(combined)
    if numeric_identifier_columns:
        combined = _coerce_columns_to_strings(combined, numeric_identifier_columns)
        for column in numeric_identifier_columns:
            if column not in identifier_columns_coerced:
                identifier_columns_coerced.append(column)
    columns = _columns(combined)

    schema_hash = _schema_hash(columns)

    raw_path = out_dir / "raw.parquet"
    combined, retry_coerced = _write_parquet_with_retry(combined, raw_path)
    for column in retry_coerced:
        if column not in identifier_columns_coerced:
            identifier_columns_coerced.append(column)

    preview_rows = min(5, n_rows)
    preview_data = []
    try:
        import pandas as pd  # type: ignore
    except Exception:  # pragma: no cover - optional
        pd = None  # type: ignore
    if pd is not None and isinstance(combined, pd.DataFrame):
        preview_data = combined.head(preview_rows).to_dict(orient="records")  # type: ignore[call-arg]
    elif pl is not None and isinstance(combined, pl.DataFrame):  # type: ignore[attr-defined]
        preview_data = combined.head(preview_rows).to_dicts()  # type: ignore[call-arg]

    missing_summary = _compute_missing_summary(combined)
    missing_summary_path = out_dir / "missing_summary.json"
    missing_summary_path.write_text(json.dumps(missing_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    high_missing = [entry["column"] for entry in missing_summary if entry.get("missing_pct", 0.0) >= 0.5]

    meta_payload = {
        "run_id": run_id,
        "n_rows": n_rows,
        "n_cols": n_cols,
        "columns": columns,
        "preview": preview_data,
        "source_files": [entry["abs_path"] for entry in source_meta],
        "phone_columns_coerced": phone_columns,
        "schema_hash": schema_hash,
        "missing_summary_path": missing_summary_path.as_posix(),
        "high_missing_columns": high_missing,
        "identifier_columns_coerced": identifier_columns_coerced,
    }
    if sla_manifest_entries:
        meta_payload["sla_documents"] = len(sla_manifest_entries)
        meta_payload["sla_terms"] = sum(len(entry.get("terms", [])) for entry in sla_manifest_entries)
        if sla_manifest_path is not None:
            meta_payload["sla_manifest"] = sla_manifest_path.as_posix()
    if streaming_path is not None:
        meta_payload["raw_streaming"] = streaming_path.as_posix()
    (out_dir / "meta_ingestion.json").write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report_payload = {
        "run_id": run_id,
        "status": "PASS",
        "n_rows": n_rows,
        "n_cols": n_cols,
        "duration_s": 0.0,
        "issues": [],
    }
    if sla_manifest_entries:
        report_payload["sla_documents"] = len(sla_manifest_entries)
        missing_terms = sum(1 for entry in sla_manifest_entries if not entry.get("terms"))
        if missing_terms:
            report_payload["issues"].append(f"sla_terms_missing::{missing_terms}")
    report_payload["duration_s"] = time.perf_counter() - start_ts
    (out_dir / "ingestion_report.json").write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    (out_dir / "row_meta.json").write_text(
        json.dumps({"phase": "01", "n_rows": n_rows, "source": resolved_files[0].as_posix()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (out_dir / "source_meta.json").write_text(json.dumps({"files": source_meta}, ensure_ascii=False, indent=2), encoding="utf-8")

    fingerprints = [
        {
            "path": entry["abs_path"],
            "size": entry["filesize_bytes"],
            "mtime": entry["modified"],
        }
        for entry in source_meta
    ]
    baselines_payload = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": n_rows,
        "n_cols": n_cols,
        "schema_hash": schema_hash,
        "phone_columns_coerced": phone_columns,
        "source_fingerprint": fingerprints,
    }
    if sla_manifest_entries:
        baselines_payload["sla_documents"] = len(sla_manifest_entries)
    (artifacts_root / run_id / "baselines.json").write_text(json.dumps(baselines_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    outputs: Dict[str, Any] = {
        "raw": raw_path.as_posix(),
        "meta": (out_dir / "meta_ingestion.json").as_posix(),
        "missing_summary": missing_summary_path.as_posix(),
    }
    if sla_manifest_path is not None:
        outputs["sla_manifest"] = sla_manifest_path.as_posix()
    if sla_bundle_path is not None:
        outputs["sla_bundle"] = sla_bundle_path.as_posix()
    if streaming_path is not None:
        outputs["raw_streaming"] = streaming_path.as_posix()

    elapsed = time.perf_counter() - start_ts
    minutes = elapsed / 60.0
    denom = max(n_rows / 1_000_000.0, 1e-6)
    health.log_ingestion_latency(run_id, n_rows, minutes / denom)
    health.emit_report(extra={"stage": stage_id, "status": "PASS"})

    result = {
        "run_id": run_id,
        "status": "PASS",
        "outputs": outputs,
        "metrics": {"n_rows": n_rows, "n_cols": n_cols},
        "logs_uri": (out_dir / "logs.jsonl").as_posix(),
    }
    _write_logs(logs, out_dir / "logs.jsonl")
    return result


__all__ = ["run"]
