from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml  # type: ignore
from scipy.stats import chi2_contingency, pearsonr  # type: ignore

from shared.correlation_semantics import (  # type: ignore
    CorrelationHistoryTracker,
    ShippingCorrelationEnricher,
)

READINESS_RANDOM_SEED = 42
MAX_SAMPLE_ROWS = 250_000
MIN_PAIR_N = 150
MAX_RESULTS_PER_BUCKET = 25
MAX_CATEGORY_CARDINALITY = 20
MIN_ABS_CORR_NUMERIC = 0.2
MIN_EFFECT_NUM_CAT = 0.08
MIN_EFFECT_CAT_CAT = 0.1

DEFAULT_KPI_NAMES: Tuple[str, ...] = ("cod_amount", "sla_achieved", "rto_rate", "rto_flag")
BACKEND_ROOT = Path(__file__).resolve().parents[2]
KPI_CONTRACT_PATH = BACKEND_ROOT / "contracts" / "kpis.yml"

EXCLUDE_PATTERN = re.compile(
    r"(?:^|_)(?:id|guid|uuid|hash|md5|sha|token|tracking|reference|ref|awb|order|shipment)$",
    re.IGNORECASE,
)
EXCLUDE_KEYWORDS = (
    "_id",
    "_uuid",
    "_guid",
    "_hash",
    "_token",
    "_is_missing",
    "_checksum",
    "checksum",
    "signature",
)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_kpi_synonyms() -> Dict[str, List[str]]:
    if KPI_CONTRACT_PATH.exists():
        try:
            payload = yaml.safe_load(KPI_CONTRACT_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        if isinstance(payload, Mapping):
            raw = payload.get("kpis")
            if isinstance(raw, Mapping):
                synonyms: Dict[str, List[str]] = {}
                for canonical, values in raw.items():
                    entries: List[str] = []
                    if isinstance(values, str):
                        entries.append(values)
                    elif isinstance(values, (list, tuple, set)):
                        entries.extend(str(item) for item in values if isinstance(item, str))
                    if entries:
                        canonical_str = str(canonical)
                        synonyms[canonical_str] = [canonical_str] + entries
                if synonyms:
                    return synonyms
    return {name: [name] for name in DEFAULT_KPI_NAMES}


def _is_excluded(name: str) -> bool:
    lowered = str(name).strip().lower()
    if not lowered:
        return True
    if EXCLUDE_PATTERN.search(lowered):
        return True
    return any(keyword in lowered for keyword in EXCLUDE_KEYWORDS)


def _numeric_columns(df: pd.DataFrame, excluded: Dict[str, str]) -> List[str]:
    numeric: List[str] = []
    for column in df.columns:
        if column in excluded:
            continue
        series = df[column]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            unique = series.nunique(dropna=True)
            if unique <= 3:
                excluded[str(column)] = "low_variability_numeric"
                continue
            numeric.append(str(column))
    return numeric


def _categorical_columns(df: pd.DataFrame, excluded: Dict[str, str]) -> List[str]:
    categorical: List[str] = []
    for column in df.columns:
        if column in excluded:
            continue
        series = df[column]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            continue
        unique = series.nunique(dropna=True)
        if unique < 2:
            excluded[str(column)] = "single_category"
            continue
        if unique > MAX_CATEGORY_CARDINALITY:
            excluded[str(column)] = "high_cardinality"
            continue
        categorical.append(str(column))
    return categorical


def _analyze_columns(df: pd.DataFrame) -> Tuple[List[str], List[str], Dict[str, str]]:
    excluded: Dict[str, str] = {}
    for column in df.columns:
        name = str(column)
        series = df[column]
        if _is_excluded(name):
            excluded[name] = "pattern_excluded"
            continue
        if series.isna().mean() >= 0.95:
            excluded[name] = "mostly_missing"
            continue
        if series.nunique(dropna=True) <= 1:
            excluded[name] = "no_variation"
            continue
    numeric = _numeric_columns(df, excluded)
    categorical = _categorical_columns(df, excluded)
    return numeric, categorical, excluded


def _safe_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(result):
        return result
    return None


def _pearson_pairs(
    df: pd.DataFrame,
    columns: Sequence[str],
    *,
    enricher: Optional[ShippingCorrelationEnricher] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    results: List[Dict[str, Any]] = []
    evaluated = 0
    for idx, col_a in enumerate(columns):
        series_a = df[col_a]
        for col_b in columns[idx + 1 :]:
            evaluated += 1
            pair = df[[col_a, col_b]].dropna()
            n = int(pair.shape[0])
            if n < MIN_PAIR_N:
                continue
            try:
                corr_value, p_value = pearsonr(pair[col_a], pair[col_b])
            except Exception:
                continue
            corr = _safe_float(corr_value)
            if corr is None:
                continue
            abs_corr = abs(corr)
            if abs_corr < MIN_ABS_CORR_NUMERIC:
                continue
            record = {
                "feature_a": col_a,
                "feature_b": col_b,
                "correlation": corr,
                "abs_correlation": abs_corr,
                "sample_size": n,
                "method": "pearson",
                "kind": "numeric_numeric",
            }
            if isinstance(p_value, (int, float)) and math.isfinite(float(p_value)):
                record["p_value"] = float(p_value)
            if enricher is not None:
                record.update(
                    enricher.enrich_pair(
                        col_a,
                        col_b,
                        corr,
                        n,
                        method="pearson",
                    )
                )
            results.append(record)
    results.sort(key=lambda item: item["abs_correlation"], reverse=True)
    return results[:MAX_RESULTS_PER_BUCKET], evaluated


def _eta_squared(numeric: pd.Series, categorical: pd.Series) -> Optional[Tuple[float, Dict[str, Any]]]:
    frame = pd.DataFrame({"numeric": numeric, "category": categorical}).dropna()
    if frame.empty:
        return None
    groups = frame.groupby("category")["numeric"]
    if groups.ngroups < 2:
        return None
    overall_mean = float(frame["numeric"].mean())
    counts = groups.size().astype(float)
    means = groups.mean().astype(float)
    ss_between = float(((means - overall_mean) ** 2 * counts).sum())
    ss_total = float(((frame["numeric"] - overall_mean) ** 2).sum())
    if ss_total <= 0:
        return None
    eta = ss_between / ss_total
    if not math.isfinite(eta):
        return None
    group_stats = groups.agg(["mean", "count"]).sort_values("mean", ascending=False)
    top = group_stats.iloc[0]
    bottom = group_stats.iloc[-1]
    insight = {
        "top_category": {
            "value": str(group_stats.index[0]),
            "mean": float(top["mean"]),
            "count": int(top["count"]),
        },
        "bottom_category": {
            "value": str(group_stats.index[-1]),
            "mean": float(bottom["mean"]),
            "count": int(bottom["count"]),
        },
        "mean_gap": float(top["mean"] - bottom["mean"]),
        "category_count": int(groups.ngroups),
    }
    return eta, insight


def _numeric_categorical_pairs(
    df: pd.DataFrame,
    numeric_cols: Sequence[str],
    categorical_cols: Sequence[str],
    *,
    enricher: Optional[ShippingCorrelationEnricher] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    results: List[Dict[str, Any]] = []
    evaluated = 0
    for num_col in numeric_cols:
        numeric_series = df[num_col]
        for cat_col in categorical_cols:
            evaluated += 1
            frame = pd.DataFrame({"numeric": numeric_series, "category": df[cat_col]}).dropna()
            n = int(frame.shape[0])
            if n < MIN_PAIR_N:
                continue
            effect = _eta_squared(frame["numeric"], frame["category"])
            if effect is None:
                continue
            eta, insight = effect
            if eta < MIN_EFFECT_NUM_CAT:
                continue
            record = {
                "feature_a": num_col,
                "feature_b": cat_col,
                "correlation": eta,
                "abs_correlation": eta,
                "sample_size": n,
                "method": "eta_squared",
                "kind": "numeric_categorical",
                "notes": insight,
            }
            if enricher is not None:
                record.update(
                    enricher.enrich_pair(
                        num_col,
                        cat_col,
                        eta,
                        n,
                        method="eta_squared",
                        notes=insight,
                    )
                )
            results.append(record)
    results.sort(key=lambda item: item["abs_correlation"], reverse=True)
    return results[:MAX_RESULTS_PER_BUCKET], evaluated


def _cramers_v(cat_a: pd.Series, cat_b: pd.Series) -> Optional[Tuple[float, Dict[str, Any]]]:
    frame = pd.DataFrame({"a": cat_a, "b": cat_b}).dropna()
    if frame.empty:
        return None
    contingency = pd.crosstab(frame["a"], frame["b"])
    if contingency.shape[0] < 2 or contingency.shape[1] < 2:
        return None
    n = contingency.values.sum()
    if n < MIN_PAIR_N:
        return None
    chi2, _, _, _ = chi2_contingency(contingency, correction=False)
    phi2 = chi2 / n
    r, c = contingency.shape
    phi2corr = max(0.0, phi2 - ((c - 1) * (r - 1)) / max(n - 1, 1))
    rcorr = r - ((r - 1) ** 2) / max(n - 1, 1)
    ccorr = c - ((c - 1) ** 2) / max(n - 1, 1)
    denominator = min((rcorr - 1), (ccorr - 1))
    if denominator <= 0:
        return None
    value = math.sqrt(phi2corr / denominator)
    if not math.isfinite(value):
        return None
    top_pair = contingency.stack().idxmax()
    insight = {
        "top_pair": {
            "value_a": str(top_pair[0]),
            "value_b": str(top_pair[1]),
            "count": int(contingency.loc[top_pair[0], top_pair[1]]),
        },
        "category_a": contingency.shape[0],
        "category_b": contingency.shape[1],
    }
    return value, insight


def _categorical_pairs(
    df: pd.DataFrame,
    categorical_cols: Sequence[str],
    *,
    enricher: Optional[ShippingCorrelationEnricher] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    results: List[Dict[str, Any]] = []
    evaluated = 0
    for idx, col_a in enumerate(categorical_cols):
        series_a = df[col_a]
        for col_b in categorical_cols[idx + 1 :]:
            evaluated += 1
            effect = _cramers_v(series_a, df[col_b])
            if effect is None:
                continue
            value, insight = effect
            if value < MIN_EFFECT_CAT_CAT:
                continue
            n = int(pd.DataFrame({"a": series_a, "b": df[col_b]}).dropna().shape[0])
            record = {
                "feature_a": col_a,
                "feature_b": col_b,
                "correlation": value,
                "abs_correlation": value,
                "sample_size": n,
                "method": "cramers_v",
                "kind": "categorical_categorical",
                "notes": insight,
            }
            if enricher is not None:
                record.update(
                    enricher.enrich_pair(
                        col_a,
                        col_b,
                        value,
                        n,
                        method="cramers_v",
                        notes=insight,
                    )
                )
            results.append(record)
    results.sort(key=lambda item: item["abs_correlation"], reverse=True)
    return results[:MAX_RESULTS_PER_BUCKET], evaluated


def _flatten_records(groups: Mapping[str, Sequence[Mapping[str, Any]]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for category, entries in groups.items():
        for entry in entries:
            record = dict(entry)
            record["category"] = category
            records.append(record)
    return records


def run(run_id: str, inputs: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    artifacts_root = Path((config or {}).get("artifacts_root", "artifacts")).expanduser().resolve()
    out_dir = artifacts_root / run_id / "stage_07_7_business_correlations"
    _ensure_dir(out_dir)

    features_uri = (
        (inputs or {}).get("features")
        or (inputs or {}).get("features_curated")
        or artifacts_root / run_id / "stage_06_feature_eng" / "features.parquet"
    )
    features_path = Path(features_uri).expanduser().resolve()
    if not features_path.exists():
        raise FileNotFoundError(f"feature dataset not found for business correlations: {features_path}")

    df_full = pd.read_parquet(features_path)
    total_rows = int(df_full.shape[0])
    if total_rows == 0:
        payload = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": features_path.as_posix(),
            "sample_size": 0,
            "total_rows": 0,
            "highlights": {"numeric_numeric": [], "numeric_categorical": [], "categorical_categorical": []},
            "excluded_columns": {},
            "notes": ["dataset_empty"],
        }
        (out_dir / "business_correlations.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "run_id": run_id,
            "status": "EMPTY",
            "outputs": {
                "business_correlations": (out_dir / "business_correlations.json").as_posix(),
                "business_correlations_table": None,
            },
            "metrics": {"sample_size": 0, "total_rows": 0},
        }

    if total_rows > MAX_SAMPLE_ROWS:
        df = df_full.sample(n=MAX_SAMPLE_ROWS, random_state=READINESS_RANDOM_SEED).reset_index(drop=True)
    else:
        df = df_full.copy()
    sample_size = int(df.shape[0])

    numeric_cols, categorical_cols, excluded_columns = _analyze_columns(df)

    numeric_frame = (
        df.select_dtypes(include=["number", "bool"])
        .apply(pd.to_numeric, errors="coerce")
        .copy()
    )
    numeric_stats: Dict[str, Dict[str, float]] = {}
    for col in numeric_frame.columns:
        series = numeric_frame[col].dropna()
        if series.empty:
            continue
        try:
            mean = float(series.mean())
        except Exception:
            mean = 0.0
        try:
            std = float(series.std())
        except Exception:
            std = 0.0
        numeric_stats[str(col)] = {"mean": mean, "std": std}

    kpi_synonyms = _load_kpi_synonyms()
    enricher = ShippingCorrelationEnricher(
        artifacts_root,
        run_id,
        numeric_stats=numeric_stats,
        kpi_synonyms=kpi_synonyms,
    )
    history_tracker = CorrelationHistoryTracker(artifacts_root)

    numeric_pairs, numeric_evaluated = _pearson_pairs(df, numeric_cols, enricher=enricher)
    num_cat_pairs, num_cat_evaluated = _numeric_categorical_pairs(
        df,
        numeric_cols,
        categorical_cols,
        enricher=enricher,
    )
    cat_cat_pairs, cat_cat_evaluated = _categorical_pairs(
        df,
        categorical_cols,
        enricher=enricher,
    )

    highlights = {
        "numeric_numeric": numeric_pairs,
        "numeric_categorical": num_cat_pairs,
        "categorical_categorical": cat_cat_pairs,
    }

    history_tracker.mark_and_update(run_id, numeric_pairs)
    history_tracker.mark_and_update(run_id, num_cat_pairs)
    history_tracker.mark_and_update(run_id, cat_cat_pairs)

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": features_path.as_posix(),
        "sample_size": sample_size,
        "total_rows": total_rows,
        "filters": {
            "max_sample_rows": MAX_SAMPLE_ROWS,
            "min_pair_n": MIN_PAIR_N,
            "max_category_cardinality": MAX_CATEGORY_CARDINALITY,
        },
        "excluded_columns": excluded_columns,
        "evaluated_pairs": {
            "numeric_numeric": numeric_evaluated,
            "numeric_categorical": num_cat_evaluated,
            "categorical_categorical": cat_cat_evaluated,
        },
        "highlights": highlights,
    }

    json_path = out_dir / "business_correlations.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    table_path = out_dir / "business_correlations.parquet"
    records = _flatten_records(highlights)
    if records:
        table = pd.DataFrame(records)
        table.to_parquet(table_path, index=False)
        table_uri = table_path.as_posix()
    else:
        table_uri = None

    # Generate summary.json
    summary_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": features_path.as_posix(),
        "sample_size": sample_size,
        "total_rows": total_rows,
        "summary": {
            "numeric_numeric_count": len(numeric_pairs),
            "numeric_categorical_count": len(num_cat_pairs),
            "categorical_categorical_count": len(cat_cat_pairs),
            "total_highlights": len(numeric_pairs) + len(num_cat_pairs) + len(cat_cat_pairs),
        },
        "top_positive_drivers": [
            {
                "feature_a": item.get("feature_a", ""),
                "feature_b": item.get("feature_b", ""),
                "correlation": item.get("abs_correlation", 0.0),
                "kind": item.get("kind", ""),
            }
            for item in (numeric_pairs + num_cat_pairs + cat_cat_pairs)[:10]
            if item.get("abs_correlation", 0.0) > 0.3
        ],
        "top_negative_drivers": [
            {
                "feature_a": item.get("feature_a", ""),
                "feature_b": item.get("feature_b", ""),
                "correlation": item.get("abs_correlation", 0.0),
                "kind": item.get("kind", ""),
            }
            for item in sorted(
                numeric_pairs + num_cat_pairs + cat_cat_pairs,
                key=lambda x: x.get("correlation", 0.0),
            )[:10]
            if item.get("correlation", 0.0) < -0.3
        ],
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Link to network.json from stage_07_correlations (should exist from phase 07)
    correlations_dir = artifacts_root / run_id / "stage_07_correlations"
    network_path = correlations_dir / "network.json"
    # If network.json doesn't exist, create a simple one from business correlations
    if not network_path.exists():
        # Build network graph from business correlations
        nodes_map: Dict[str, Dict[str, Any]] = {}
        edges_list: List[Dict[str, Any]] = []
        node_ids_set: Set[str] = set()
        
        # Process all correlation pairs to build network
        all_pairs = numeric_pairs + num_cat_pairs + cat_cat_pairs
        for pair in all_pairs[:100]:  # Limit to top 100
            feature_a = str(pair.get("feature_a", ""))
            feature_b = str(pair.get("feature_b", ""))
            corr_value = float(pair.get("abs_correlation", 0.0))
            
            if not feature_a or not feature_b or corr_value < 0.2:
                continue
            
            # Add nodes
            for feat in [feature_a, feature_b]:
                if feat not in node_ids_set:
                    node_ids_set.add(feat)
                    nodes_map[feat] = {
                        "id": feat,
                        "label": feat,
                        "type": "feature",
                        "score": 0.0,
                    }
            
            # Add edge
            edges_list.append({
                "source": feature_a,
                "target": feature_b,
                "value": round(corr_value, 4),
                "label": "correlation",
            })
        
        # Build network structure
        network = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": list(nodes_map.values()),
            "edges": edges_list,
            "categories": ["feature"],
            "source": "stage_07_7_business_correlations",
        }
        correlations_dir.mkdir(parents=True, exist_ok=True)
        network_path.write_text(json.dumps(network, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = {
        "sample_size": sample_size,
        "total_rows": total_rows,
        "numeric_numeric_highlights": len(numeric_pairs),
        "numeric_categorical_highlights": len(num_cat_pairs),
        "categorical_categorical_highlights": len(cat_cat_pairs),
    }

    outputs_dict = {
        "business_correlations": json_path.as_posix(),
        "business_correlations_table": table_uri,
        "summary": summary_path.as_posix(),
    }
    
    # Add network.json to outputs if it exists
    if network_path.exists():
        outputs_dict["network"] = network_path.as_posix()

    return {
        "run_id": run_id,
        "status": "PASS",
        "outputs": outputs_dict,
        "metrics": metrics,
    }


__all__ = ["run"]
