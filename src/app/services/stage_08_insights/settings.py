from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple


def _to_list(value: Optional[Iterable[str] | str], *, allow_empty: bool = False) -> List[str]:
    if value is None:
        return [] if allow_empty else []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        items = [str(item).strip() for item in value]
    cleaned = [item for item in items if item]
    if cleaned:
        return cleaned
    return [] if allow_empty else []


def _to_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return default


def _to_float(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _resolve_tuple(raw: object, *, length: int, default: Tuple[int, ...]) -> Tuple[int, ...]:
    if raw is None:
        return default
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        values = [int(float(item)) for item in raw[:length]]
        if len(values) == length:
            return tuple(values)
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if len(parts) == length:
            try:
                return tuple(int(float(part)) for part in parts)
            except ValueError:
                return default
    return default


def _resolve_float_tuple(raw: object, *, length: int, default: Tuple[float, ...]) -> Tuple[float, ...]:
    if raw is None:
        return default
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        values = [float(item) for item in raw[:length]]
        if len(values) == length:
            return tuple(values)
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if len(parts) == length:
            try:
                return tuple(float(part) for part in parts)
            except ValueError:
                return default
    return default


def _lower_keys(config: Mapping[str, object]) -> Mapping[str, object]:
    return {str(key).lower(): value for key, value in config.items()}


def _get(config: Mapping[str, object], *keys: str, default: object) -> object:
    lowered = _lower_keys(config)
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return default


DEFAULT_SEGMENTS = ["CARRIER", "REGION"]
DEFAULT_NUMERIC_HINTS: List[str] = []
DEFAULT_TEXT_COLS = ["NOTES", "COMMENTS", "REMARKS"]


@dataclass
class Stage08Settings:
    artifacts_root: str = "artifacts"
    timezone: str = "Asia/Riyadh"
    seed: int = 42
    policy_path: str = "contracts/impute/policy.yml"

    emit_threshold: float = 0.50
    high_bucket: float = 0.70
    confidence_weights: Tuple[float, float, float] = (0.60, 0.25, 0.15)

    max_features: int = 200
    max_segments: int = 150
    n_min_per_segment: int = 300
    max_cells_seg_time: int = 2000

    time_window_days: int = 60
    split_windows: Tuple[int, int] = (30, 30)
    business_hours: Tuple[int, int] = (8, 20)
    holidays: List[str] = field(default_factory=list)

    enable_seg_time: bool = False
    candidates_enable: bool = True
    enable_sampling_over_5m: bool = True
    sample_fraction: float = 0.5
    sampling_threshold_rows: int = 5_000_000
    missing_ratio_threshold: float = 0.9
    critical_missing_warn: float = 0.1
    critical_missing_stop: float = 0.2

    enable_simpson_detect: bool = False
    enable_contrast_sets: bool = False
    enable_partial_stratified: bool = True
    enable_permutation: bool = False
    enable_bh_fdr: bool = False

    permutation_iters: int = 1000
    alpha_fdr: float = 0.10

    numeric_hints: List[str] = field(default_factory=lambda: list(DEFAULT_NUMERIC_HINTS))
    text_cols: List[str] = field(default_factory=lambda: list(DEFAULT_TEXT_COLS))
    text_join_key: Optional[str] = "row_id"

    timestamp_col: Optional[str] = "created_at"
    segments: List[str] = field(default_factory=lambda: list(DEFAULT_SEGMENTS))
    segment_max_arity: int = 2

    enable_text_pipeline: bool = True
    enable_sentiment_pipeline: bool = True

    enable_sampling_logging: bool = True
    enforce_readiness_gates: bool = True
    textops_card_limit: int = 3

    @classmethod
    def from_config(cls, config: Optional[Mapping[str, object]]) -> "Stage08Settings":
        if config is None:
            config = {}
        lowered = _lower_keys(config)

        artifacts_root = str(_get(lowered, "artifacts_root", default="artifacts"))
        timezone = str(_get(lowered, "timezone", default=cls.timezone))
        seed = _to_int(_get(lowered, "seed", default=cls.seed), cls.seed)

        emit_threshold = _to_float(_get(lowered, "emit_threshold", "confidence_emit_threshold", default=cls.emit_threshold), cls.emit_threshold)
        env_emit = os.getenv("STAGE08_EMIT_THRESHOLD")
        if env_emit:
            try:
                emit_threshold = float(env_emit)
            except ValueError:
                pass

        high_bucket = _to_float(_get(lowered, "high_bucket", default=cls.high_bucket), cls.high_bucket)
        env_high = os.getenv("STAGE08_HIGH_BUCKET")
        if env_high:
            try:
                high_bucket = float(env_high)
            except ValueError:
                pass

        confidence_weights = _resolve_float_tuple(
            _get(lowered, "confidence_weights", "conf_weights", default=cls.confidence_weights),
            length=3,
            default=cls.confidence_weights,
        )
        env_weights = os.getenv("STAGE08_CONF_WEIGHTS")
        if env_weights:
            try:
                parsed = tuple(float(part.strip()) for part in env_weights.split(",") if part.strip())
                if len(parsed) == 3:
                    confidence_weights = parsed  # type: ignore[assignment]
            except ValueError:
                pass

        policy_path = str(_get(lowered, "policy_path", default=cls.policy_path))
        env_policy_path = os.getenv("STAGE08_POLICY_PATH")
        if env_policy_path:
            policy_path = env_policy_path

        critical_missing_warn = _to_float(
            _get(lowered, "critical_missing_warn", default=cls.critical_missing_warn),
            cls.critical_missing_warn,
        )
        env_critical_missing_warn = os.getenv("STAGE08_CRITICAL_MISSING_WARN")
        if env_critical_missing_warn:
            try:
                critical_missing_warn = float(env_critical_missing_warn)
            except ValueError:
                pass

        critical_missing_stop = _to_float(
            _get(lowered, "critical_missing_stop", default=cls.critical_missing_stop),
            cls.critical_missing_stop,
        )
        env_critical_missing_stop = os.getenv("STAGE08_CRITICAL_MISSING_STOP")
        if env_critical_missing_stop:
            try:
                critical_missing_stop = float(env_critical_missing_stop)
            except ValueError:
                pass

        max_features = _to_int(_get(lowered, "max_features", default=cls.max_features), cls.max_features)
        max_segments = _to_int(_get(lowered, "max_segments", default=cls.max_segments), cls.max_segments)
        n_min_per_segment = _to_int(_get(lowered, "n_min_per_segment", default=cls.n_min_per_segment), cls.n_min_per_segment)
        max_cells_seg_time = _to_int(_get(lowered, "max_cells_seg_time", default=cls.max_cells_seg_time), cls.max_cells_seg_time)

        time_window_days = _to_int(_get(lowered, "time_window_days", default=cls.time_window_days), cls.time_window_days)
        split_windows = _resolve_tuple(_get(lowered, "split_windows", default=cls.split_windows), length=2, default=cls.split_windows)
        business_hours = _resolve_tuple(_get(lowered, "business_hours", default=cls.business_hours), length=2, default=cls.business_hours)
        holidays = _to_list(_get(lowered, "holidays", default=[]), allow_empty=True)

        enable_seg_time = _to_bool(_get(lowered, "enable_seg_time", default=cls.enable_seg_time), cls.enable_seg_time)
        candidates_enable = _to_bool(_get(lowered, "candidates_enable", default=cls.candidates_enable), cls.candidates_enable)
        enable_sampling_over_5m = _to_bool(_get(lowered, "enable_sampling_over_5m", default=cls.enable_sampling_over_5m), cls.enable_sampling_over_5m)
        sample_fraction = _to_float(_get(lowered, "sample_fraction", default=cls.sample_fraction), cls.sample_fraction)
        sampling_threshold_rows = _to_int(_get(lowered, "sampling_threshold_rows", default=cls.sampling_threshold_rows), cls.sampling_threshold_rows)
        missing_ratio_threshold = _to_float(_get(lowered, "missing_ratio_threshold", default=cls.missing_ratio_threshold), cls.missing_ratio_threshold)
        env_missing = os.getenv("STAGE08_MISSING_RATIO_THRESHOLD")
        if env_missing:
            try:
                missing_ratio_threshold = float(env_missing)
            except ValueError:
                pass
        enable_simpson_detect = _to_bool(_get(lowered, "enable_simpson_detect", default=cls.enable_simpson_detect), cls.enable_simpson_detect)
        enable_contrast_sets = _to_bool(_get(lowered, "enable_contrast_sets", default=cls.enable_contrast_sets), cls.enable_contrast_sets)
        enable_partial_stratified = _to_bool(_get(lowered, "enable_partial_stratified", default=cls.enable_partial_stratified), cls.enable_partial_stratified)
        enable_permutation = _to_bool(_get(lowered, "enable_permutation", default=cls.enable_permutation), cls.enable_permutation)
        enable_bh_fdr = _to_bool(_get(lowered, "enable_bh_fdr", default=cls.enable_bh_fdr), cls.enable_bh_fdr)

        permutation_iters = _to_int(_get(lowered, "permutation_iters", default=cls.permutation_iters), cls.permutation_iters)
        alpha_fdr = _to_float(_get(lowered, "alpha_fdr", default=cls.alpha_fdr), cls.alpha_fdr)

        numeric_hints = _to_list(_get(lowered, "numeric_hints", "numeric_cols", default=DEFAULT_NUMERIC_HINTS), allow_empty=True)
        text_cols = _to_list(_get(lowered, "text_cols", "text_columns", default=DEFAULT_TEXT_COLS), allow_empty=True)
        text_join_key_raw = _get(lowered, "text_join_key", default=cls.text_join_key)
        text_join_key = None if text_join_key_raw in {None, "", "none"} else str(text_join_key_raw)

        timestamp_col_raw = _get(lowered, "timestamp_col", "timestamp", default=cls.timestamp_col)
        timestamp_col = None if timestamp_col_raw in {None, "", "none"} else str(timestamp_col_raw)

        segments = _to_list(_get(lowered, "segments", default=DEFAULT_SEGMENTS), allow_empty=True)
        if not segments:
            segments = list(DEFAULT_SEGMENTS)
        segment_max_arity = _to_int(_get(lowered, "segment_max_arity", default=cls.segment_max_arity), cls.segment_max_arity)

        enable_text_pipeline = _to_bool(_get(lowered, "enable_text_pipeline", default=cls.enable_text_pipeline), cls.enable_text_pipeline)
        enable_sentiment_pipeline = _to_bool(_get(lowered, "enable_sentiment_pipeline", default=cls.enable_sentiment_pipeline), cls.enable_sentiment_pipeline)
        enable_sampling_logging = _to_bool(_get(lowered, "enable_sampling_logging", default=cls.enable_sampling_logging), cls.enable_sampling_logging)
        enforce_readiness_gates = _to_bool(_get(lowered, "enforce_readiness_gates", default=cls.enforce_readiness_gates), cls.enforce_readiness_gates)
        textops_card_limit = _to_int(_get(lowered, "textops_card_limit", default=cls.textops_card_limit), cls.textops_card_limit)

        return cls(
            artifacts_root=artifacts_root,
            timezone=timezone,
            seed=seed,
            policy_path=policy_path,
            emit_threshold=emit_threshold,
            high_bucket=high_bucket,
            confidence_weights=confidence_weights,
            max_features=max_features,
            max_segments=max_segments,
            n_min_per_segment=n_min_per_segment,
            max_cells_seg_time=max_cells_seg_time,
            time_window_days=time_window_days,
            split_windows=split_windows,
            business_hours=business_hours,
            holidays=holidays,
            enable_seg_time=enable_seg_time,
            candidates_enable=candidates_enable,
            enable_sampling_over_5m=enable_sampling_over_5m,
            sample_fraction=sample_fraction,
            sampling_threshold_rows=sampling_threshold_rows,
            missing_ratio_threshold=missing_ratio_threshold,
            critical_missing_warn=critical_missing_warn,
            critical_missing_stop=critical_missing_stop,
            enable_simpson_detect=enable_simpson_detect,
            enable_contrast_sets=enable_contrast_sets,
            enable_partial_stratified=enable_partial_stratified,
            enable_permutation=enable_permutation,
            enable_bh_fdr=enable_bh_fdr,
            permutation_iters=permutation_iters,
            alpha_fdr=alpha_fdr,
            numeric_hints=numeric_hints,
            text_cols=text_cols,
            text_join_key=text_join_key,
            timestamp_col=timestamp_col,
            segments=segments,
            segment_max_arity=segment_max_arity,
            enable_text_pipeline=enable_text_pipeline,
            enable_sentiment_pipeline=enable_sentiment_pipeline,
            enable_sampling_logging=enable_sampling_logging,
            enforce_readiness_gates=enforce_readiness_gates,
            textops_card_limit=textops_card_limit,
        )


__all__ = ["Stage08Settings"]
