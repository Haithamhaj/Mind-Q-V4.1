from __future__ import annotations

import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd
import yaml
from zoneinfo import ZoneInfo

from backend.src.app.services import nzv_policy
from shared import baseline as baseline_utils  # type: ignore
from shared import validate  # type: ignore

# Default imputation policy now uses the relaxed thresholds so geo-heavy tables are not blocked.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = BACKEND_ROOT / "contracts" / "impute" / "policy_relaxed.yml"
FALLBACK_GROUP_ROWS = 500
INDICATOR_SUFFIX = "__is_missing"
ID_LIKE_PATTERN = re.compile(r"(phone|mobile|msisdn|whatsapp|awb|reference|ref|id|account|tracking)", re.IGNORECASE)
GEO_FALLBACK = {"latitude", "longitude"}
PREDICTION_COL_CANDIDATES = ("prediction_time", "prediction_ts", "prediction_timestamp")


def _normalize(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_plan(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_json_safe(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_missing_summary_map(artifacts_root: Path, run_id: str) -> Tuple[Dict[str, Mapping[str, Any]], Dict[str, Mapping[str, Any]]]:
    summary_path = artifacts_root / run_id / "stage_01_ingestion" / "missing_summary.json"
    payload = _load_json_safe(summary_path)
    mapping: Dict[str, Mapping[str, Any]] = {}
    lowered: Dict[str, Mapping[str, Any]] = {}
    if isinstance(payload, list):
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            column = entry.get("column")
            if not isinstance(column, str):
                continue
            mapping[column] = entry
            lowered[column.lower()] = entry
    return mapping, lowered


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.timedelta64):
        return str(pd.to_timedelta(value))
    return str(value)


def _build_nzv_column_stats(series: pd.Series, n_rows: int) -> Dict[str, Any]:
    name = str(series.name)
    n_valid = int(series.notna().sum())
    missing_pct = float(series.isna().sum()) / n_rows if n_rows else 0.0
    unique_count = int(series.nunique(dropna=True)) if n_valid else 0

    top_values: List[Dict[str, Any]] = []
    dominant_value: Any = None
    dominant_pct = 0.0
    if n_rows and n_valid:
        non_null = series.dropna()
        try:
            counts = non_null.value_counts(dropna=False).head(10)
        except TypeError:
            counts = non_null.astype(str).value_counts(dropna=False).head(10)
        for value, count in counts.items():
            pct = float(count) / float(n_rows) if n_rows else 0.0
            safe_value = _json_safe_value(value)
            top_values.append({"value": safe_value, "pct": pct})
            if dominant_value is None:
                dominant_value = safe_value
                dominant_pct = pct

    return {
        "name": name,
        "n_rows": n_rows,
        "n_valid": n_valid,
        "missing_pct": missing_pct,
        "unique_count": unique_count,
        "dominant_value": dominant_value,
        "dominant_pct": dominant_pct,
        "top_values": top_values,
    }


def _generate_nzv_payload(df: pd.DataFrame, run_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    policy = nzv_policy.load_policy()
    n_rows = int(len(df))
    columns_payload: List[Dict[str, Any]] = []
    n_constant_like = 0
    n_high_imbalance = 0
    n_nzv_columns = 0

    for column in df.columns:
        series = df[column]
        stats = _build_nzv_column_stats(series, n_rows)
        classification = nzv_policy.classify_column(stats, policy=policy)
        record = {
            "name": stats["name"],
            "n_valid": stats["n_valid"],
            "missing_pct": stats["missing_pct"],
            "unique_count": stats["unique_count"],
            "dominant_value": stats["dominant_value"],
            "dominant_pct": stats["dominant_pct"],
            "top_values": stats["top_values"],
            "nzv_category": classification["nzv_category"],
            "is_nzv": bool(classification["is_nzv"]),
            "nzv_reason": classification["reason"],
        }
        columns_payload.append(record)
        if record["nzv_category"] == "constant_like":
            n_constant_like += 1
        if record["nzv_category"] == "high_imbalance":
            n_high_imbalance += 1
        if record["is_nzv"]:
            n_nzv_columns += 1

    n_total_columns = len(columns_payload)
    nzv_summary = {
        "n_nzv_columns": n_nzv_columns,
        "n_constant_like": n_constant_like,
        "n_high_imbalance": n_high_imbalance,
        "n_total_columns": n_total_columns,
        "nzv_ratio": (float(n_nzv_columns) / float(n_total_columns)) if n_total_columns else 0.0,
    }
    payload = {
        "run_id": run_id,
        "n_rows": n_rows,
        "columns": columns_payload,
        "nzv_summary": nzv_summary,
    }
    return payload, nzv_summary


def _compose_cleaning_summary(
    missing_map: Dict[str, Mapping[str, Any]],
    missing_lower: Dict[str, Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    *,
    geo_warn_threshold: float,
    geo_stop_threshold: float,
) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for decision in decisions:
        feature = decision.get("feature")
        if not isinstance(feature, str):
            continue
        normalized = feature.lower()
        base = missing_map.get(feature) or missing_lower.get(normalized)
        missing_pct_stage01 = float(base.get("missing_pct", 0.0)) if isinstance(base, Mapping) else None
        missing_count_stage01 = int(base.get("missing", 0)) if isinstance(base, Mapping) else None
        blank_stage01 = int(base.get("blank", 0)) if isinstance(base, Mapping) else None
        dtype = decision.get("dtype") or (base.get("dtype") if isinstance(base, Mapping) else None)
        missing_pct_decision = decision.get("missing_pct")
        geo_strategy = decision.get("geo_strategy")
        geo_status: Optional[str] = None
        geo_missing_status: Optional[str] = None
        try:
            pct_value = float(missing_pct_decision)
        except (TypeError, ValueError):
            pct_value = None
        if pct_value is not None:
            if pct_value >= geo_stop_threshold:
                geo_missing_status = "stop"
            elif pct_value >= geo_warn_threshold:
                geo_missing_status = "warn"
            else:
                geo_missing_status = "ok"
        if geo_strategy in {"impute"}:
            geo_status = "imputed"
        elif geo_strategy in {"drop", "skip"}:
            geo_status = "dropped"
        elif geo_strategy == "drop_for_model_only":
            geo_status = "dropped_model_only"
        elif geo_strategy == "indicator_only":
            geo_status = geo_missing_status or "indicator_only"
        else:
            geo_status = geo_missing_status
        summary.append(
            {
                "column": feature,
                "dtype": dtype,
                "missing_pct_stage01": missing_pct_stage01,
                "missing_count_stage01": missing_count_stage01,
                "blank_count_stage01": blank_stage01,
                "action": decision.get("action"),
                "status": decision.get("status"),
                "strategy": decision.get("strategy"),
                "filled_rows": decision.get("filled"),
                "indicator": decision.get("indicator"),
                "indicator_created": decision.get("indicator_created"),
                "model_exclusion": bool(decision.get("model_exclusion")),
                "reason": decision.get("reason"),
                "group_used": decision.get("group_used"),
                "missing_pct_decision": missing_pct_decision,
                "geo_status": geo_status,
                "geo_missing_status": geo_missing_status,
                "geo_strategy": geo_strategy,
            }
        )
        seen.add(normalized)

    for column, base in missing_map.items():
        normalized = column.lower()
        if normalized in seen:
            continue
        summary.append(
            {
                "column": column,
                "dtype": base.get("dtype"),
                "missing_pct_stage01": base.get("missing_pct"),
                "missing_count_stage01": base.get("missing"),
                "blank_count_stage01": base.get("blank"),
                "action": "unchanged",
                "status": "unchanged",
                "strategy": None,
                "filled_rows": 0,
                "indicator": None,
                "indicator_created": False,
                "model_exclusion": False,
                "reason": None,
                "group_used": None,
                "missing_pct_decision": None,
                "geo_status": None,
                "geo_missing_status": None,
                "geo_strategy": None,
            }
        )

    summary.sort(key=lambda item: (-(item.get("missing_pct_stage01") or 0.0), str(item.get("column"))))
    return summary


def _save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_policy(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"default policy not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _missing_pct(series: pd.Series) -> float:
    return float(series.isna().mean()) if len(series) else 0.0


def _infer_kind(series: pd.Series, name: str) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return "numeric"
    if pd.api.types.is_string_dtype(series):
        sample = series.dropna().head(1000)
        if not sample.empty:
            converted = pd.to_numeric(sample, errors="coerce")
            if converted.notna().sum() and converted.notna().mean() >= 0.9:
                return "numeric"
    if re.search(r"(date|time)", name, re.IGNORECASE):
        return "datetime"
    return "categorical"


def _is_id_like(series: pd.Series, name: str) -> bool:
    if ID_LIKE_PATTERN.search(name):
        return True
    nunique = series.nunique(dropna=True)
    return nunique >= 0.9 * len(series) if len(series) else False


def _is_geo(name: str, geo_policy: Dict[str, Any]) -> bool:
    if not isinstance(geo_policy, Mapping):
        return name.lower() in GEO_FALLBACK
    normalized = name.lower()
    columns_cfg = geo_policy.get("columns")
    if isinstance(columns_cfg, Mapping):
        if normalized in {str(key).lower() for key in columns_cfg.keys()}:
            return True
    elif isinstance(columns_cfg, (list, tuple, set)):
        if normalized in {str(col).lower() for col in columns_cfg}:
            return True
    overrides_cfg = geo_policy.get("overrides")
    if isinstance(overrides_cfg, Mapping):
        if normalized in {str(key).lower() for key in overrides_cfg.keys()}:
            return True
    return normalized in GEO_FALLBACK


def _geo_strategy(name: str, geo_policy: Dict[str, Any]) -> str:
    """
    Resolve the geo handling strategy for a column.
    Returns one of: indicator_only, impute, skip, drop, drop_for_model_only.
    Defaults to indicator_only for backwards compatibility.
    """
    if not isinstance(geo_policy, Mapping):
        return "indicator_only"
    normalized = name.lower()

    def _strategy_from(value: Any) -> Optional[str]:
        if isinstance(value, Mapping):
            candidate = value.get("strategy")
        else:
            candidate = value
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()
        return None

    columns_cfg = geo_policy.get("columns")
    if isinstance(columns_cfg, Mapping):
        for key, value in columns_cfg.items():
            if str(key).lower() == normalized:
                resolved = _strategy_from(value)
                if resolved:
                    return resolved
    overrides_cfg = geo_policy.get("overrides")
    if isinstance(overrides_cfg, Mapping):
        for key, value in overrides_cfg.items():
            if str(key).lower() == normalized:
                resolved = _strategy_from(value)
                if resolved:
                    return resolved
    default_strategy = geo_policy.get("strategy")
    if isinstance(default_strategy, str) and default_strategy.strip():
        return default_strategy.strip().lower()
    return "indicator_only"


def _winsorize(series: pd.Series, limits: Sequence[float] | None) -> pd.Series:
    if not limits or series.dropna().empty:
        return series
    lower, upper = limits
    result = series.copy()
    non_null = series.dropna()
    if lower is not None:
        lower_val = non_null.quantile(lower)
        result.loc[result < lower_val] = lower_val
    if upper is not None:
        upper_val = non_null.quantile(upper)
        result.loc[result > upper_val] = upper_val
    return result


def _mode_or_nan(series: pd.Series) -> Any:
    modes = series.mode(dropna=True)
    if not modes.empty:
        return modes.iloc[0]
    return np.nan


def _eligible_group_keys(df: pd.DataFrame, keys: Sequence[str] | None) -> List[str]:
    return [key for key in (keys or []) if key in df.columns]


def _coerce_timezone(series: pd.Series, tz_info: Optional[ZoneInfo]) -> pd.Series:
    if tz_info is None:
        return series
    if series.dt.tz is None:
        return series.dt.tz_localize(tz_info, nonexistent="NaT", ambiguous="NaT")
    return series.dt.tz_convert(tz_info)


def _build_plan(df: pd.DataFrame, policy: Dict[str, Any], *, strategy_override: str | None) -> Dict[str, Any]:
    strategy = (strategy_override or policy.get("strategy") or "hybrid").lower()
    numeric_cfg = policy.get("numeric") or {}
    categorical_cfg = policy.get("categorical") or {}
    time_cfg = policy.get("time_aware") or {}
    geo_cfg = policy.get("geo") or {}
    geo_allow_high_missing = {
        str(col).lower()
        for col in (geo_cfg.get("allow_high_missing_columns") or [])
        if isinstance(col, str) and col.strip()
    }
    high_missing_threshold = float(policy.get("high_missing_exclude_threshold", 0.95))
    numeric_indicator_threshold = float(numeric_cfg.get("indicator_if_missing_pct_gt", 0.0))
    numeric_group_rows = int(numeric_cfg.get("group_valid_min_rows", FALLBACK_GROUP_ROWS))
    group_keys_numeric = _eligible_group_keys(df, numeric_cfg.get("group_keys"))
    group_keys_categorical = _eligible_group_keys(df, categorical_cfg.get("group_keys"))

    policies: List[Dict[str, Any]] = []
    model_exclusions: List[str] = []

    for column in df.columns:
        series = df[column]
        missing_pct = _missing_pct(series)
        dtype = _infer_kind(series, column)
        indicator_name = f"{_normalize(column)}{INDICATOR_SUFFIX}"
        reasons: List[str] = []
        params: Dict[str, Any] = {"missing_pct": missing_pct}
        entry: Dict[str, Any] = {"feature": column, "dtype": dtype, "params": params}
        indicator_needed = missing_pct > 0.0

        is_geo = _is_geo(column, geo_cfg)
        geo_strategy = _geo_strategy(column, geo_cfg) if is_geo else None
        if is_geo:
            entry["geo_strategy"] = geo_strategy

        feature_lower = column.lower()
        allow_high_missing = is_geo and feature_lower in geo_allow_high_missing
        if allow_high_missing and geo_strategy in {"drop", "skip", "drop_for_model_only"}:
            geo_strategy = "impute"
            entry["geo_strategy"] = geo_strategy
            reasons.append("geo allow_high_missing")

        if missing_pct >= high_missing_threshold and not allow_high_missing:
            entry["action"] = "drop_for_model_only"
            reasons.append(f"missing_pct={missing_pct:.3f} >= {high_missing_threshold:.2f}")
            if indicator_needed:
                entry["indicator"] = indicator_name
            model_exclusions.append(column)
        elif is_geo and geo_strategy in {"drop", "skip"}:
            entry["action"] = "skip"
            if indicator_needed:
                entry["indicator"] = indicator_name
            reasons.append("geo drop")
            policies.append(entry)
            continue
        elif is_geo and geo_strategy == "drop_for_model_only":
            entry["action"] = "drop_for_model_only"
            reasons.append("geo drop_for_model_only")
            if indicator_needed:
                entry["indicator"] = indicator_name
            model_exclusions.append(column)
        elif is_geo and geo_strategy == "indicator_only":
            entry["action"] = "indicator_only"
            reasons.append("geo indicator")
            if indicator_needed:
                entry["indicator"] = indicator_name
        elif is_geo and geo_strategy == "impute":
            entry["action"] = "impute"
            reasons.append("geo impute")
            geo_impute_cfg = geo_cfg.get("impute")
            dtype_override = None
            if isinstance(geo_impute_cfg, Mapping):
                impute_strategy_override = geo_impute_cfg.get("strategy")
                if isinstance(impute_strategy_override, str) and impute_strategy_override.strip():
                    entry["strategy"] = impute_strategy_override.strip().lower()
                indicator_preference = geo_impute_cfg.get("indicator")
                if indicator_preference is False:
                    indicator_needed = False
                dtype_override = geo_impute_cfg.get("dtype")
            if isinstance(dtype_override, str) and dtype_override.strip():
                dtype = dtype_override.strip().lower()
                entry["dtype"] = dtype
            if indicator_needed and entry.get("indicator") is None:
                entry["indicator"] = indicator_name
        elif _is_id_like(series, column):
            entry["action"] = "indicator_only"
            reasons.append("id_like heuristic")
            if indicator_needed:
                entry["indicator"] = indicator_name
        elif dtype == "numeric":
            entry["action"] = "impute"
            if not isinstance(entry.get("strategy"), str) or not entry["strategy"]:
                entry["strategy"] = "groupwise_then_median" if strategy != "baseline" and group_keys_numeric else "median"
            else:
                entry["strategy"] = entry["strategy"].lower()
            entry["winsor_limits"] = numeric_cfg.get("winsor_limits")
            if group_keys_numeric:
                entry["group_keys"] = group_keys_numeric
            params["group_valid_min_rows"] = numeric_group_rows
            indicator_trigger = missing_pct >= numeric_indicator_threshold if numeric_indicator_threshold else indicator_needed
            if indicator_trigger:
                entry["indicator"] = indicator_name
            reasons.append(f"numeric_{entry['strategy']}")
        elif dtype == "datetime" and time_cfg.get("enable", False):
            entry["action"] = "impute"
            entry["strategy"] = "time_aware"
            entity_keys = _eligible_group_keys(df, time_cfg.get("within_entity"))
            if entity_keys:
                entry["entity_keys"] = entity_keys
                params["entity_keys"] = entity_keys
            if time_cfg.get("max_gap_hours") is not None:
                entry["max_gap_hours"] = float(time_cfg.get("max_gap_hours"))
                params["max_gap_hours"] = float(time_cfg.get("max_gap_hours"))
            if indicator_needed:
                entry["indicator"] = indicator_name
            reasons.append("time_aware")
        else:
            entry["action"] = "impute"
            preferred = "groupwise_mode" if strategy in {"groupwise", "hybrid"} and group_keys_categorical else "mode_with_unknown"
            entry["strategy"] = preferred
            if group_keys_categorical:
                entry["group_keys"] = group_keys_categorical
            entry["unknown_token"] = categorical_cfg.get("unknown_token", "Unknown")
            params["group_valid_min_rows"] = numeric_group_rows
            if indicator_needed:
                entry["indicator"] = indicator_name
            reasons.append(preferred)

        if indicator_needed and entry.get("indicator") is None and entry.get("action") == "impute":
            entry["indicator"] = indicator_name

        entry["why"] = "; ".join(reasons) if reasons else None
        policies.append(entry)

    plan = {
        "generated_by": "auto",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "policies": policies,
        "gates": policy.get("gates", {}),
        "model_exclusions": model_exclusions,
        "policy_version": policy.get("version"),
        "numeric_group_valid_min_rows": numeric_group_rows,
    }
    timezone_name = (policy.get("time_aware") or {}).get("timezone")
    if timezone_name:
        plan["time_aware_timezone"] = timezone_name
    return plan


def _apply_numeric(
    df: pd.DataFrame,
    feature: str,
    policy: Dict[str, Any],
    strategy_default: str,
    min_group_rows: int,
) -> Tuple[int, str, str]:
    strategy = str(policy.get("strategy") or strategy_default or "median").lower()
    df[feature] = pd.to_numeric(df[feature], errors="coerce")
    mask_before = df[feature].isna()
    if policy.get("winsor_limits"):
        df[feature] = _winsorize(df[feature], policy.get("winsor_limits"))
    filled = 0
    strategy_used = strategy
    group_used = "baseline"

    if strategy in {"groupwise", "groupwise_then_median", "hybrid"}:
        keys = [k for k in (policy.get("group_keys") or []) if k in df.columns and k != feature]
        if keys:
            grouped = df[keys + [feature]].groupby(keys, dropna=False)
            counts = grouped[feature].transform("count")
            medians = grouped[feature].transform("median")
            eligible = counts >= min_group_rows
            target_mask = mask_before & eligible & medians.notna()
            if target_mask.any():
                df.loc[target_mask, feature] = medians[target_mask]
                filled += int(target_mask.sum())
                group_used = "groupwise"
            else:
                strategy_used = "median"
                group_used = "fallback_small_group"
        else:
            strategy_used = "median"
            group_used = "fallback_no_keys"

    remaining_mask = df[feature].isna()
    if remaining_mask.any():
        fill_value = policy.get("fill_value")
        if fill_value is None or (isinstance(fill_value, str) and not fill_value):
            non_null = df[feature].dropna()
            fill_value = float(non_null.median(skipna=True)) if not non_null.empty else 0.0
        df.loc[remaining_mask, feature] = fill_value
        filled += int(remaining_mask.sum())
        if group_used == "baseline":
            group_used = "median"
        strategy_used = "median" if strategy_used.startswith("groupwise") else strategy_used

    return filled, strategy_used, group_used


def _apply_categorical(
    df: pd.DataFrame,
    feature: str,
    policy: Dict[str, Any],
    strategy_default: str,
    min_group_rows: int,
) -> Tuple[int, str, str]:
    strategy = str(policy.get("strategy") or strategy_default or "mode_with_unknown").lower()
    mask_before = df[feature].isna()
    filled = 0
    strategy_used = strategy
    group_used = "baseline"

    if strategy in {"groupwise", "groupwise_mode"}:
        keys = [k for k in (policy.get("group_keys") or []) if k in df.columns and k != feature]
        if keys:
            grouped = df[keys + [feature]].groupby(keys, dropna=False)
            counts = grouped[feature].transform("count")
            modes = grouped[feature].transform(_mode_or_nan)
            target_mask = mask_before & counts.ge(min_group_rows) & modes.notna()
            if target_mask.any():
                df.loc[target_mask, feature] = modes[target_mask]
                filled += int(target_mask.sum())
                group_used = "groupwise"
            else:
                strategy_used = "mode_with_unknown"
                group_used = "fallback_small_group"
        else:
            strategy_used = "mode_with_unknown"
            group_used = "fallback_no_keys"

    remaining_mask = df[feature].isna()
    if remaining_mask.any():
        fill_value = policy.get("fill_value")
        if not isinstance(fill_value, str) or not fill_value:
            fill_value = policy.get("unknown_token", "Unknown")
        df.loc[remaining_mask, feature] = fill_value
        filled += int(remaining_mask.sum())
        if group_used == "baseline":
            group_used = "mode_with_unknown"

    return filled, strategy_used, group_used


def _time_fill_series(series: pd.Series, max_gap_hours: Optional[float]) -> pd.Series:
    if series.notna().sum() == 0:
        return series
    forward = series.ffill()
    backward = series.bfill()
    result = series.copy()
    for idx, value in enumerate(series.to_numpy()):
        if pd.isna(value):
            prev_val = forward.iloc[idx]
            next_val = backward.iloc[idx]
            chosen = pd.NaT
            if pd.notna(prev_val):
                chosen = prev_val
            elif pd.notna(next_val):
                chosen = next_val
            if pd.isna(chosen):
                continue
            if max_gap_hours is not None and pd.notna(prev_val) and pd.notna(next_val):
                gap = abs((next_val - prev_val).total_seconds()) / 3600.0
                if gap > max_gap_hours:
                    continue
            result.iloc[idx] = chosen
    return result


def _apply_datetime(
    df: pd.DataFrame,
    feature: str,
    policy: Dict[str, Any],
    tz_info: Optional[ZoneInfo],
    max_gap_hours: Optional[float],
    entity_keys: List[str],
    prediction_series: Optional[pd.Series],
) -> Tuple[int, str, bool]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df[feature] = pd.to_datetime(df[feature], errors="coerce")
    converted = False
    series_tz = getattr(df[feature].dt, "tz", None)
    if tz_info is not None:
        df[feature] = _coerce_timezone(df[feature], tz_info)
        converted = True
    if tz_info is not None:
        now_ts = pd.Timestamp.now(tz=tz_info)
    else:
        now_ts = pd.Timestamp.utcnow().tz_localize(None)
        if series_tz is not None:
            now_ts = now_ts.tz_localize(series_tz)  # pragma: no cover - defensive
    df[feature] = df[feature].mask(df[feature] > now_ts)
    mask_before = df[feature].isna()
    if not mask_before.any():
        return 0, "coerce", converted

    filled = 0
    strategy_used = "time_aware"
    if entity_keys:
        def _fill_group(group: pd.Series) -> pd.Series:
            nonlocal filled
            original_missing = group.isna()
            result = _time_fill_series(group, max_gap_hours)
            filled += int((original_missing & result.notna()).sum())
            return result

        df[feature] = df.groupby(entity_keys, dropna=False)[feature].transform(_fill_group)
    else:
        strategy_used = "coerce"

    if prediction_series is not None and not prediction_series.isna().all():
        aligned_pred = prediction_series
        if tz_info is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                aligned_pred = pd.to_datetime(aligned_pred, errors="coerce")
            aligned_pred = _coerce_timezone(aligned_pred, tz_info)
        df.loc[df[feature].notna() & aligned_pred.notna() & (df[feature] > aligned_pred), feature] = pd.NaT

    return filled, strategy_used, converted


def _column_psi(base: pd.Series, comp: pd.Series) -> Optional[float]:
    base_vals = pd.to_numeric(base, errors="coerce").dropna().to_numpy()
    comp_vals = pd.to_numeric(comp, errors="coerce").dropna().to_numpy()
    if base_vals.size == 0 or comp_vals.size == 0:
        return None
    unique_vals = np.unique(base_vals)
    if unique_vals.size <= 1:
        return 0.0
    if unique_vals.size <= 5:
        all_values = np.union1d(base_vals, comp_vals)
        base_dist = np.array([(base_vals == val).mean() for val in all_values])
        comp_dist = np.array([(comp_vals == val).mean() for val in all_values])
    else:
        quantiles = np.linspace(0, 1, min(10, unique_vals.size) + 1)
        breaks = np.unique(np.quantile(base_vals, quantiles))
        if breaks.size <= 2:
            return 0.0
        bins = np.concatenate(([-np.inf], breaks[1:-1], [np.inf]))
        base_hist, _ = np.histogram(base_vals, bins=bins)
        comp_hist, _ = np.histogram(comp_vals, bins=bins)
        if base_hist.sum() == 0 or comp_hist.sum() == 0:
            return 0.0
        base_dist = base_hist / base_hist.sum()
        comp_dist = comp_hist / comp_hist.sum()
    eps = 1e-6
    base_dist = np.clip(base_dist, eps, None)
    comp_dist = np.clip(comp_dist, eps, None)
    return float(np.sum((base_dist - comp_dist) * np.log(base_dist / comp_dist)))


def _apply_plan(
    original: pd.DataFrame,
    plan: Dict[str, Any],
    *,
    strategy: str,
    min_group_rows: int,
    tz_info: Optional[ZoneInfo],
    tz_name: Optional[str],
    psi_keys: Optional[List[str]],
    warn_threshold: float,
    stop_threshold: float,
    prediction_series: Optional[pd.Series],
) -> Dict[str, Any]:
    frame = original.copy()
    logs: List[Dict[str, Any]] = []
    changelog: List[Dict[str, Any]] = []
    imputed_columns: List[str] = []
    indicator_columns: List[str] = []
    column_decisions: List[Dict[str, Any]] = []
    model_exclusions_plan = list(plan.get("model_exclusions") or [])
    model_exclusions_seen = set(model_exclusions_plan)
    timezone_converted: List[str] = []

    policies = plan.get("policies") or []
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        params = policy.setdefault("params", {})
        feature = policy.get("feature")
        if not isinstance(feature, str) or feature not in frame.columns:
            logs.append({"event": "skip_missing_feature", "feature": feature, "severity": "WARN"})
            continue
        action = policy.get("action", "impute")
        dtype = policy.get("dtype", "categorical")
        indicator_name = policy.get("indicator")
        mask_before = frame[feature].isna()

        missing_pct_value = params.get("missing_pct")
        try:
            missing_pct_value = float(missing_pct_value)
        except (TypeError, ValueError):
            missing_pct_value = None

        decision_entry: Dict[str, Any] = {
            "feature": feature,
            "dtype": dtype,
            "action": action,
            "indicator": indicator_name,
            "missing_pct": missing_pct_value,
            "reason": policy.get("why"),
            "model_exclusion": feature in model_exclusions_seen,
            "geo_strategy": policy.get("geo_strategy"),
        }

        if action == "skip":
            decision_entry["status"] = "skip"
            decision_entry["indicator_created"] = False
            column_decisions.append(decision_entry)
            frame.drop(columns=[feature], inplace=True, errors="ignore")
            logs.append({"event": "skip_column", "feature": feature})
            continue
        if action == "indicator_only":
            if indicator_name and indicator_name not in frame.columns:
                frame[indicator_name] = mask_before.astype("int8")
                indicator_columns.append(indicator_name)
            decision_entry.update(
                {
                    "status": "indicator_only",
                    "strategy": None,
                    "filled": 0,
                    "indicator_created": bool(indicator_name),
                }
            )
            column_decisions.append(decision_entry)
            logs.append({"event": "indicator_only", "feature": feature, "indicator": indicator_name})
            changelog.append(
                {
                    "feature": feature,
                    "action": "indicator_only",
                    "indicator": indicator_name,
                    "missing_before": int(mask_before.sum()),
                }
            )
            continue
        if action == "drop_for_model_only":
            if indicator_name and indicator_name not in frame.columns:
                frame[indicator_name] = mask_before.astype("int8")
                indicator_columns.append(indicator_name)
            if feature not in model_exclusions_seen:
                model_exclusions_plan.append(feature)
                model_exclusions_seen.add(feature)
            decision_entry.update(
                {
                    "status": "drop_for_model_only",
                    "strategy": None,
                    "filled": 0,
                    "model_exclusion": True,
                    "indicator_created": bool(indicator_name),
                }
            )
            column_decisions.append(decision_entry)
            logs.append({"event": "mark_model_exclusion", "feature": feature, "indicator": indicator_name})
            changelog.append(
                {
                    "feature": feature,
                    "action": "drop_for_model_only",
                    "indicator": indicator_name,
                    "missing_before": int(mask_before.sum()),
                }
            )
            continue

        filled = 0
        strategy_used = policy.get("strategy") or strategy
        if dtype == "numeric":
            filled, strategy_used, group_used = _apply_numeric(frame, feature, policy, strategy, min_group_rows)
            params["group_used"] = group_used
            params.setdefault("group_valid_min_rows", min_group_rows)
            if group_used.startswith("fallback"):
                logs.append(
                    {
                        "event": "groupwise_fallback",
                        "feature": feature,
                        "severity": "WARN",
                        "reason": group_used,
                        "threshold": min_group_rows,
                    }
                )
                policy["why"] = f"{policy.get('why', '')}|{group_used}".strip("|")
        elif dtype == "datetime":
            entity_keys = [k for k in (policy.get("entity_keys") or []) if k in frame.columns]
            max_gap_hours = policy.get("max_gap_hours")
            if max_gap_hours is not None:
                try:
                    max_gap_hours = float(max_gap_hours)
                except (TypeError, ValueError):
                    max_gap_hours = None
            filled, strategy_used, converted = _apply_datetime(
                frame,
                feature,
                policy,
                tz_info,
                max_gap_hours,
                entity_keys,
                prediction_series,
            )
            if converted:
                timezone_converted.append(feature)
        else:
            filled, strategy_used, group_used = _apply_categorical(frame, feature, policy, strategy, min_group_rows)
            params["group_used"] = group_used
            params.setdefault("group_valid_min_rows", min_group_rows)
            if group_used.startswith("fallback"):
                logs.append(
                    {
                        "event": "groupwise_fallback",
                        "feature": feature,
                        "severity": "WARN",
                        "reason": group_used,
                        "threshold": min_group_rows,
                    }
                )
                policy["why"] = f"{policy.get('why', '')}|{group_used}".strip("|")

        if filled > 0:
            imputed_columns.append(feature)
        if indicator_name and indicator_name not in frame.columns:
            frame[indicator_name] = mask_before.astype("int8")
            indicator_columns.append(indicator_name)
        decision_entry.update(
            {
                "status": "impute",
                "strategy": strategy_used,
                "filled": filled,
                "group_used": params.get("group_used"),
                "indicator_created": bool(indicator_name),
            }
        )
        column_decisions.append(decision_entry)
        logs.append(
            {
                "event": "impute",
                "feature": feature,
                "dtype": dtype,
                "strategy": strategy_used,
                "filled": filled,
                "indicator": indicator_name,
            }
        )
        changelog.append(
            {
                "feature": feature,
                "action": "impute",
                "dtype": dtype,
                "strategy": strategy_used,
                "filled": filled,
                "missing_before": int(mask_before.sum()),
                "indicator": indicator_name,
            }
        )

    secondary_skip = plan.get("secondary_skip") or []
    for feature in secondary_skip:
        dtype_name: Optional[str] = None
        if feature in frame.columns:
            try:
                dtype_name = frame[feature].dtype.name  # type: ignore[attr-defined]
            except Exception:
                dtype_name = None
            frame.drop(columns=[feature], inplace=True, errors="ignore")
            logs.append({"event": "secondary_skip", "feature": feature})
        column_decisions.append(
            {
                "feature": feature,
                "dtype": dtype_name,
                "action": "secondary_skip",
                "status": "secondary_skip",
                "indicator": None,
                "missing_pct": None,
                "reason": "secondary_skip",
                "model_exclusion": False,
                "indicator_created": False,
            }
        )

    psi_entries: List[Dict[str, Any]] = []
    psi_warn: List[Dict[str, Any]] = []
    psi_stop: List[Dict[str, Any]] = []
    psi_missing: List[str] = []

    psi_targets = psi_keys if psi_keys else sorted(set(imputed_columns))
    for key in psi_targets:
        if key not in frame.columns or key not in original.columns:
            psi_missing.append(key)
            logs.append({"event": "psi_key_missing", "feature": key, "severity": "WARN"})
            continue
        psi_val = _column_psi(original[key], frame[key])
        if psi_val is None:
            continue
        entry = {"feature": key, "psi": psi_val}
        psi_entries.append(entry)
        if psi_val > stop_threshold:
            psi_stop.append(entry)
        elif psi_val > warn_threshold:
            psi_warn.append(entry)

    if timezone_converted:
        logs.append(
            {
                "event": "time_aware_timezone",
                "severity": "INFO",
                "tz": tz_name,
                "columns": sorted(set(timezone_converted)),
            }
        )

    return {
        "frame": frame,
        "logs": logs,
        "changelog": changelog,
        "imputed_columns": sorted(set(imputed_columns)),
        "indicator_columns": sorted(set(indicator_columns)),
        "model_exclusions": model_exclusions_plan,
        "psi": {"evaluated": psi_entries, "warn": psi_warn, "stop": psi_stop, "missing": psi_missing},
        "rows_imputed_total": int(sum(entry.get("filled", 0) for entry in changelog)),
        "timezone_converted": sorted(set(timezone_converted)),
        "decisions": column_decisions,
    }


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    config = config or {}
    artifacts_root = Path(config.get("artifacts_root", "artifacts")).expanduser().resolve()
    out_dir = artifacts_root / run_id / "stage_05_missing"
    _ensure_dir(out_dir)

    raw_uri = (inputs or {}).get("raw") or (inputs or {}).get("raw_uri")
    if not isinstance(raw_uri, str):
        raise ValueError("Stage 05 requires inputs['raw'] with parquet path")
    raw_path = Path(raw_uri).expanduser().resolve()
    if not raw_path.exists():
        raise FileNotFoundError(f"Stage 05 input not found: {raw_path}")

    df = pd.read_parquet(raw_path)
    try:
        baseline = baseline_utils.load(artifacts_root, run_id)
    except FileNotFoundError:
        baseline = {}
    expected_rows = baseline.get("n_rows")

    missing_cfg = config.get("missing") or {}
    policy_path_cfg = missing_cfg.get("policy_path")
    policy_path = Path(policy_path_cfg).expanduser() if policy_path_cfg else DEFAULT_POLICY_PATH
    policy_payload = _load_policy(policy_path) if policy_path.exists() else {}

    plan_path = out_dir / "imputation_plan.json"
    plan = _load_plan(plan_path)
    plan_source = "manual" if plan.get("policies") else "auto"

    if not plan.get("policies"):
        plan = _build_plan(df, policy_payload, strategy_override=missing_cfg.get("strategy_override"))
        plan["policy_path"] = str(policy_path)
        _save_json(plan_path, plan)
        plan_source = "auto"

    geo_cfg = policy_payload.get("geo") or {}
    geo_columns_cfg = [str(col) for col in (geo_cfg.get("columns") or [])]
    geo_warn_threshold = float(geo_cfg.get("missing_warn_threshold", 0.3))
    geo_stop_threshold = float(geo_cfg.get("missing_stop_threshold", 0.5))
    geo_reference = {col.lower() for col in geo_columns_cfg} if geo_columns_cfg else set()
    geo_reference.update(name.lower() for name in GEO_FALLBACK)
    geo_allow_high_missing = {str(col).lower() for col in geo_cfg.get("allow_high_missing_columns", [])}

    geo_missing_stats: List[Dict[str, Any]] = []
    for entry in plan.get("policies") or []:
        if not isinstance(entry, dict):
            continue
        feature = entry.get("feature")
        if not isinstance(feature, str):
            continue
        why = str(entry.get("why") or "").lower()
        feature_lower = feature.lower()
        is_core_geo = feature_lower in geo_reference
        is_marker = "geo indicator" in why
        if not is_core_geo and not is_marker:
            continue
        params = entry.setdefault("params", {})
        missing_pct = params.get("missing_pct")
        if missing_pct is None:
            missing_pct = float(df[feature].isna().mean()) if feature in df.columns else 0.0
            params["missing_pct"] = missing_pct
        else:
            missing_pct = float(missing_pct)
        geo_missing_stats.append({"feature": feature, "missing_pct": missing_pct})

    gates = plan.get("gates") or policy_payload.get("gates") or {}
    warn_threshold = float(gates.get("psi_warn", 0.2))
    stop_threshold = float(gates.get("psi_stop", 0.3))
    psi_keys = gates.get("psi_keys")
    if isinstance(psi_keys, list):
        psi_keys = [str(key) for key in psi_keys]
    else:
        psi_keys = None

    numeric_group_rows = int(
        plan.get("numeric_group_valid_min_rows")
        or (policy_payload.get("numeric") or {}).get("group_valid_min_rows")
        or FALLBACK_GROUP_ROWS
    )
    plan["numeric_group_valid_min_rows"] = numeric_group_rows

    timezone_name = plan.get("time_aware_timezone") or (policy_payload.get("time_aware") or {}).get("timezone")
    tz_info: Optional[ZoneInfo] = None
    if timezone_name:
        try:
            tz_info = ZoneInfo(timezone_name)
        except Exception as exc:  # pragma: no cover - invalid tz
            raise RuntimeError(f"invalid timezone configured for phase05: {timezone_name}") from exc
        plan["time_aware_timezone"] = timezone_name

    prediction_series: Optional[pd.Series] = None
    for candidate in PREDICTION_COL_CANDIDATES:
        if candidate in df.columns:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                prediction_series = pd.to_datetime(df[candidate], errors="coerce")
            if tz_info is not None:
                prediction_series = _coerce_timezone(prediction_series, tz_info)
            break

    strategy_effective = plan.get("strategy", missing_cfg.get("strategy_override") or policy_payload.get("strategy") or "hybrid")

    apply_result = _apply_plan(
        df,
        plan,
        strategy=strategy_effective,
        min_group_rows=numeric_group_rows,
        tz_info=tz_info,
        tz_name=timezone_name,
        psi_keys=psi_keys,
        warn_threshold=warn_threshold,
        stop_threshold=stop_threshold,
        prediction_series=prediction_series,
    )
    column_decisions = apply_result.pop("decisions", [])
    missing_map, missing_lower = _load_missing_summary_map(artifacts_root, run_id)
    cleaning_summary = _compose_cleaning_summary(
        missing_map,
        missing_lower,
        column_decisions,
        geo_warn_threshold=geo_warn_threshold,
        geo_stop_threshold=geo_stop_threshold,
    )
    cleaning_summary_path = out_dir / "cleaning_summary.json"
    _save_json(cleaning_summary_path, cleaning_summary)

    _save_json(plan_path, plan)

    df_imputed: pd.DataFrame = apply_result["frame"]
    nzv_payload, nzv_summary = _generate_nzv_payload(df_imputed, run_id)
    nzv_summary_path = out_dir / "nzv_summaries.json"
    _save_json(nzv_summary_path, nzv_payload)

    row_guard_status = "ok"
    gating_reasons: List[str] = []
    stops_entries: List[str] = []
    if expected_rows is not None and gates.get("stop_if_rowcount_changes", True):
        try:
            validate.assert_row_stability(
                n_in=int(expected_rows),
                n_out=int(len(df_imputed)),
                allow_drop=False,
                phase="05",
                out_dir=out_dir,
            )
        except (ValueError, TypeError):
            row_guard_status = "unknown"
        except SystemExit:
            row_guard_status = "mismatch"
            gating_reasons.append("row_count_mismatch")
            stops_entries.append("row_guard_mismatch")

    psi_info = apply_result["psi"]
    psi_stop = psi_info.get("stop") or []
    psi_warn = psi_info.get("warn") or []
    if psi_stop:
        gating_reasons.append("psi_stop")
        stops_entries.extend(
            f"psi_stop::{entry.get('feature')}::{float(entry.get('psi', 0.0)):.4f}" for entry in psi_stop if isinstance(entry, dict)
        )
    elif psi_warn:
        gating_reasons.append("psi_warn")

    geo_stop_details = []
    geo_bypassed_details = []
    for item in geo_missing_stats:
        missing_pct = float(item["missing_pct"])
        feature_name = item["feature"]
        feature_lower = feature_name.lower()
        if missing_pct >= geo_stop_threshold:
            if feature_lower in geo_allow_high_missing or "geo indicator" in item.get("why", "").lower():
                geo_bypassed_details.append({"feature": feature_name, "missing_pct": missing_pct})
            else:
                geo_stop_details.append({"feature": feature_name, "missing_pct": missing_pct})

    geo_warn_details = [
        {"feature": item["feature"], "missing_pct": float(item["missing_pct"])}
        for item in geo_missing_stats
        if geo_warn_threshold <= float(item["missing_pct"]) < geo_stop_threshold
    ]

    if geo_stop_details:
        formatted = ", ".join(f"{entry['feature']}({entry['missing_pct']:.1%})" for entry in geo_stop_details)
        gating_reasons.append(f"geo_missing_stop[{formatted}]")
        stops_entries.extend(
            f"geo_missing::{entry['feature']}::{entry['missing_pct']:.4f}" for entry in geo_stop_details
        )
    elif geo_bypassed_details:
        formatted = ", ".join(f"{entry['feature']}({entry['missing_pct']:.1%})" for entry in geo_bypassed_details)
        gating_reasons.append(f"geo_missing_warn[{formatted}]")
        # mark reason to indicate bypassed stop for transparency
        gating_reasons.append("geo_missing_stop_bypassed")
    elif geo_warn_details:
        formatted = ", ".join(f"{entry['feature']}({entry['missing_pct']:.1%})" for entry in geo_warn_details)
        gating_reasons.append(f"geo_missing_warn[{formatted}]")

    status = "PASS"
    if row_guard_status == "mismatch" or psi_stop or geo_stop_details:
        status = "STOP"
    elif psi_warn or geo_warn_details:
        status = "WARN"

    changelog_path = out_dir / "changelog.jsonl"
    logs_path = out_dir / "logs.jsonl"
    _write_jsonl(changelog_path, apply_result["changelog"])
    _write_jsonl(logs_path, apply_result["logs"])

    clean_imputed_path = out_dir / "clean_imputed.parquet"
    df_imputed.to_parquet(clean_imputed_path, index=False)
    legacy_path = out_dir / "imputed.parquet"
    if legacy_path != clean_imputed_path:
        df_imputed.to_parquet(legacy_path, index=False)

    metrics_payload = {
        "run_id": run_id,
        "plan_source": plan_source,
        "strategy_effective": strategy_effective,
        "cols_changed_count": len(apply_result["imputed_columns"]),
        "rows_imputed_total": apply_result["rows_imputed_total"],
        "indicator_columns": apply_result["indicator_columns"],
        "model_exclusions": plan.get("model_exclusions") or apply_result["model_exclusions"],
        "psi": psi_info,
        "row_guard_status": row_guard_status,
        "gating_reasons": gating_reasons,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan_path": plan_path.as_posix(),
        "raw_in": raw_path.as_posix(),
        "raw_out": clean_imputed_path.as_posix(),
        "tz_applied": timezone_name,
        "group_valid_min_rows": numeric_group_rows,
        "processed_columns": len(column_decisions),
        "cleaning_summary_path": cleaning_summary_path.as_posix(),
        "geo_missing": {
            "warn_threshold": geo_warn_threshold,
            "stop_threshold": geo_stop_threshold,
            "columns": geo_missing_stats,
        },
        "column_decisions": column_decisions,
        "nzv_summary": nzv_summary,
    }
    metrics_path = out_dir / "metrics.json"
    _save_json(metrics_path, metrics_payload)
    psi_summary_path = out_dir / "psi_summary.json"
    _save_json(psi_summary_path, psi_info)

    row_meta = {
        "phase": "05",
        "n_rows": int(len(df_imputed)),
        "n_cols": int(len(df_imputed.columns)),
        "source": clean_imputed_path.as_posix(),
    }
    _save_json(out_dir / "row_meta.json", row_meta)

    summary = {
        "imputed_columns": apply_result["imputed_columns"],
        "indicator_columns": apply_result["indicator_columns"],
        "model_exclusions": plan.get("model_exclusions") or apply_result["model_exclusions"],
        "nzv_summary": nzv_summary,
    }
    _save_json(out_dir / "summary.json", summary)
    imputation_report_path = out_dir / "imputation_report.json"
    imputation_report = {
        "run_id": run_id,
        "generated_at": metrics_payload["generated_at"],
        "plan_source": plan_source,
        "strategy_effective": strategy_effective,
        "row_guard_status": row_guard_status,
        "gating_reasons": gating_reasons,
        "rows_imputed_total": apply_result["rows_imputed_total"],
        "processed_columns": len(column_decisions),
        "summary": summary,
        "column_decisions": column_decisions,
        "geo_missing": metrics_payload["geo_missing"],
        "psi": psi_info,
        "cleaning_summary": cleaning_summary_path.as_posix(),
        "plan": plan_path.as_posix(),
        "nzv_summary": nzv_summary,
        "nzv_summaries": nzv_summary_path.as_posix(),
    }
    _save_json(imputation_report_path, imputation_report)

    outputs = {
        "raw": clean_imputed_path.as_posix(),
        "metrics": metrics_path.as_posix(),
        "plan": plan_path.as_posix(),
        "cleaning_summary": cleaning_summary_path.as_posix(),
        "legacy_raw": legacy_path.as_posix(),
        "imputed": legacy_path.as_posix(),
        "imputation_report": imputation_report_path.as_posix(),
        "psi_summary": psi_summary_path.as_posix(),
        "nzv_summaries": nzv_summary_path.as_posix(),
    }

    result: Dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "outputs": outputs,
        "metrics": metrics_payload,
        "logs_uri": logs_path.as_posix(),
    }
    if stops_entries and status == "STOP":
        result["stops"] = stops_entries
    return result


__all__ = ["run"]
