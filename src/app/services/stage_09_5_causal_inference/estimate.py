from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np  # type: ignore
import pandas as pd  # type: ignore
from pandas import Series

from .config_loader import CausalConfig

np.random.seed(42)
random.seed(42)


@dataclass
class EstimationOutputs:
    ate: Optional[float]
    cate_mean: Optional[float]
    cate_series: Optional[Series]
    cate_segments: List[Dict[str, Any]]
    method_baseline: Optional[str]
    method_advanced: Optional[str]
    baseline_estimate: Any = None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _prepare_features(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    selected = [col for col in columns if col in df.columns]
    if not selected:
        return pd.DataFrame({"intercept": np.ones(len(df))})

    features = df[selected].copy()
    for col in features.select_dtypes(include="bool").columns:
        features[col] = features[col].astype(int)

    cat_cols = [
        col
        for col in selected
        if features[col].dtype.name in {"object", "category"} or pd.api.types.is_string_dtype(features[col])
    ]
    if cat_cols:
        features = pd.get_dummies(features, columns=cat_cols, dummy_na=True)

    return features.fillna(0.0)


def estimate_propensity(df: pd.DataFrame, treatment: str, features: Iterable[str]) -> Series:
    """Estimate propensity scores using a logistic regression baseline."""
    from sklearn.linear_model import LogisticRegression  # type: ignore

    if treatment not in df.columns:
        raise ValueError(f"Treatment column '{treatment}' missing for propensity estimation")

    X = _prepare_features(df, features)
    treated = df[treatment]
    if pd.api.types.is_bool_dtype(treated):
        y = treated.fillna(False).astype(int)
    elif pd.api.types.is_numeric_dtype(treated):
        numeric = treated.fillna(0).astype(float)
        if numeric.nunique(dropna=True) <= 1:
            raise ValueError("Treatment column must contain variation for propensity estimation")
        median = numeric.median(skipna=True)
        if median == 0:
            y = (numeric > 0).astype(int)
        else:
            y = (numeric >= median).astype(int)
    else:
        numeric = pd.to_numeric(treated, errors="coerce")
        if numeric.notna().any():
            filled = numeric.fillna(numeric.median(skipna=True) or 0)
            y = (filled >= filled.median(skipna=True)).astype(int)
        else:
            normalized = treated.astype(str).str.strip().str.lower()
            mapping = {
                "true": 1,
                "yes": 1,
                "y": 1,
                "on": 1,
                "treated": 1,
                "false": 0,
                "no": 0,
                "n": 0,
                "off": 0,
                "control": 0,
            }
            y = normalized.map(mapping).fillna(0).astype(int)
    if y.nunique() <= 1:
        raise ValueError("Treatment column must contain at least two distinct values for propensity estimation")

    model = LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs")
    model.fit(X, y)
    scores = model.predict_proba(X)[:, 1]
    return pd.Series(scores, index=df.index, name="propensity_score")


def _summarise_segments(
    df: pd.DataFrame, cate: Series, modifiers: Iterable[str], top_k: int = 5
) -> List[Dict[str, Any]]:
    if cate is None or cate.empty:
        return []

    results: List[Dict[str, Any]] = []
    for modifier in modifiers:
        if modifier not in df.columns:
            continue
        grouped = cate.groupby(df[modifier])
        summaries: List[Tuple[str, int, float]] = []
        for level, values in grouped:
            clean_values = values.dropna()
            if clean_values.empty:
                continue
            mean_effect = clean_values.mean()
            summaries.append((str(level), int(clean_values.count()), float(mean_effect)))

        summaries.sort(key=lambda item: abs(item[2]), reverse=True)
        for level, n, effect in summaries[:top_k]:
            results.append({"segment": f"{modifier}={level}", "n": n, "effect": effect})
    return results


def _run_xlearner(data: pd.DataFrame, config: CausalConfig) -> Optional[Series]:
    try:
        from causalml.inference.meta import BaseXRegressor  # type: ignore
        from sklearn.ensemble import GradientBoostingRegressor  # type: ignore
    except Exception:
        return None

    treatment = config.treatment
    outcome = config.outcome
    feature_cols = list({*config.common_causes, *config.effect_modifiers})
    if treatment not in data.columns or outcome not in data.columns:
        return None

    X = _prepare_features(data, feature_cols)
    if X.empty:
        X = pd.DataFrame({"intercept": np.ones(len(data))})
    y = pd.to_numeric(data[outcome], errors="coerce").fillna(0.0)
    t = pd.to_numeric(data[treatment], errors="coerce").fillna(0.0)
    t = (t > t.median(skipna=True)).astype(int)

    learner = BaseXRegressor(learner=GradientBoostingRegressor(random_state=42))
    try:
        tau_hat = learner.fit_predict(X=X.values, treatment=t.values, y=y.values)
    except Exception:
        return None

    return pd.Series(tau_hat, index=data.index, name="cate")


def run_estimators(
    model: Any,
    estimand: Any,
    data: pd.DataFrame,
    config: CausalConfig,
) -> EstimationOutputs:
    baseline_method: Optional[str] = None
    baseline_ate: Optional[float] = None
    advanced_method: Optional[str] = None
    cate_series: Optional[Series] = None
    cate_mean: Optional[float] = None
    cate_segments: List[Dict[str, Any]] = []
    baseline_raw: Any = None

    for method in config.estimation_methods:
        method = method.strip().lower()
        if method.startswith("backdoor.") and baseline_method is None:
            method_name = {
                "backdoor.psm": "backdoor.propensity_score_matching",
                "backdoor.matching": "backdoor.propensity_score_matching",
                "backdoor.iptw": "backdoor.propensity_score_weighting",
            }.get(method)
            if not method_name:
                continue
            try:
                estimate = model.estimate_effect(
                    identified_estimand=estimand,
                    method_name=method_name,
                    target_units="ate",
                    confidence_intervals=True,
                )
                baseline_ate = _safe_float(getattr(estimate, "value", None)) or _safe_float(estimate)
                baseline_method = method_name
                baseline_raw = estimate
            except Exception:
                continue

        if method.startswith("meta.") and advanced_method is None:
            if method == "meta.xlearner":
                cate_series = _run_xlearner(data, config)
                if cate_series is not None:
                    cleaned = cate_series.dropna()
                    cate_mean = cleaned.mean() if not cleaned.empty else None
                    cate_segments = _summarise_segments(
                        data, cate_series, config.effect_modifiers or config.common_causes
                    )
                    advanced_method = "CausalML_XLearner"

    return EstimationOutputs(
        ate=baseline_ate,
        cate_mean=cate_mean,
        cate_series=cate_series,
        cate_segments=cate_segments,
        method_baseline=baseline_method,
        method_advanced=advanced_method,
        baseline_estimate=baseline_raw,
    )
