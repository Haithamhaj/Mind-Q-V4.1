from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import polars as pl
import yaml

logger = logging.getLogger(__name__)

DEFAULT_RULES: Dict[str, Any] = {
    "priority_signals": [
        {
            "column": "PAYMENT_METHOD",
            "mapping": {
                "COD": "COD",
                "CASH_ON_DELIVERY": "COD",
                "PREPAID": "Prepaid",
                "ONLINE": "Prepaid",
            },
        },
        {
            "column": "PAY_MODE",
            "mapping": {
                "PPD": "Prepaid",
                "PPD_PREPAID": "Prepaid",
                "PPU": "COD",
                "COD": "COD",
            },
        },
    ],
    "explicit_prepaid_flag": {"column": "IS_PREPAID", "truthy_values": [1, "1", "Y", "YES", "True", "true"]},
    "fallback_by_cod_amount": {
        "enabled": True,
        "treat_zero_dash_empty_as": "Prepaid",
        "treat_positive_as": "COD",
    },
}


def _normalize_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def _canonical_label(value: Any) -> str:
    normalized = _normalize_token(str(value)) or ""
    if normalized in {"COD", "CASH_ON_DELIVERY"}:
        return "COD"
    if normalized in {"PREPAID", "PPD", "ONLINE"}:
        return "Prepaid"
    return "Unknown"


def _merge_rules(base: Mapping[str, Any], override: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "priority_signals": [deepcopy(entry) for entry in base.get("priority_signals", []) if isinstance(entry, Mapping)],
        "explicit_prepaid_flag": deepcopy(base.get("explicit_prepaid_flag")) if base.get("explicit_prepaid_flag") else {},
        "fallback_by_cod_amount": deepcopy(base.get("fallback_by_cod_amount", {})),
    }
    if not override:
        return merged
    if isinstance(override.get("priority_signals"), Sequence):
        merged["priority_signals"] = [
            deepcopy(entry) for entry in override["priority_signals"] if isinstance(entry, Mapping)
        ]
    fallback = override.get("fallback_by_cod_amount")
    if isinstance(fallback, Mapping):
        merged.setdefault("fallback_by_cod_amount", {}).update(fallback)  # type: ignore[arg-type]
    explicit = override.get("explicit_prepaid_flag")
    if isinstance(explicit, Mapping):
        merged["explicit_prepaid_flag"] = deepcopy(explicit)
    return merged


def load_payment_rules(contracts_dir: Path, client_id: Optional[str]) -> Dict[str, Any]:
    """
    Load contracts/payment/payment_rules.yml and merge default + client-specific overrides.
    Falls back to DEFAULT_RULES when the file is missing or malformed.
    """

    rules_path = contracts_dir / "payment" / "payment_rules.yml"
    payload: Dict[str, Any] = {}
    if rules_path.exists():
        try:
            loaded = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                payload = dict(loaded)
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            logger.warning("Stage06 payment: failed to parse %s (%s); using defaults.", rules_path, exc)
    else:
        logger.info("Stage06 payment: payment rules missing at %s; using defaults.", rules_path)

    defaults = payload.get("default") if isinstance(payload, Mapping) else None
    merged = _merge_rules(DEFAULT_RULES, defaults if isinstance(defaults, Mapping) else None)

    client_cfg = None
    normalized_client = _normalize_token(client_id)
    if normalized_client and isinstance(payload, Mapping):
        clients = payload.get("clients")
        if isinstance(clients, Mapping):
            for raw_client, config in clients.items():
                if _normalize_token(raw_client) == normalized_client and isinstance(config, Mapping):
                    client_cfg = config
                    break
    merged = _merge_rules(merged, client_cfg)
    return merged


def _normalized_signal_mapping(mapping: Mapping[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for raw_value, target in mapping.items():
        key = _normalize_token(raw_value)
        if not key:
            continue
        normalized[key] = _canonical_label(target)
    return normalized


def _truthy_values(values: Optional[Iterable[Any]]) -> Tuple[str, ...]:
    if not values:
        return tuple()
    normalized: Tuple[str, ...] = tuple(
        sorted({token for token in (_normalize_token(value) for value in values) if token})
    )
    return normalized


def derive_payment_type(df: pl.DataFrame, rules: Dict[str, Any]) -> pl.DataFrame:
    """
    Adds a PAYMENT_TYPE column with values {"COD", "Prepaid", "Unknown"} using the configured rules.
    """

    result = df
    if "PAYMENT_TYPE" in result.columns:
        result = result.drop("PAYMENT_TYPE")
    result = result.with_columns(pl.lit("Unknown").alias("PAYMENT_TYPE"))

    priority_signals = rules.get("priority_signals") or []
    for idx, signal in enumerate(priority_signals):
        column = signal.get("column")
        mapping = signal.get("mapping")
        if not isinstance(column, str) or column not in result.columns or not isinstance(mapping, Mapping):
            continue
        norm_map = _normalized_signal_mapping(mapping)
        if not norm_map:
            continue
        normalized_col = (
            pl.col(column)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_uppercase()
        )
        normalized_col = normalized_col.replace("", None)
        candidate = pl.lit(None)
        for token, label in norm_map.items():
            candidate = pl.when(normalized_col == token).then(pl.lit(label)).otherwise(candidate)
        temp_col = f"__payment_signal_{idx}"
        result = result.with_columns(candidate.alias(temp_col))
        result = result.with_columns(
            pl.when((pl.col("PAYMENT_TYPE") == "Unknown") & pl.col(temp_col).is_not_null())
            .then(pl.col(temp_col))
            .otherwise(pl.col("PAYMENT_TYPE"))
            .alias("PAYMENT_TYPE")
        ).drop(temp_col)

    flag_cfg = rules.get("explicit_prepaid_flag") or {}
    flag_col = flag_cfg.get("column")
    truthy_tokens = _truthy_values(flag_cfg.get("truthy_values"))
    if isinstance(flag_col, str) and flag_col in result.columns and truthy_tokens:
        flag_expr = (
            pl.col(flag_col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_uppercase()
        )
        result = result.with_columns(
            pl.when(flag_expr.is_in(list(truthy_tokens)))
            .then(pl.lit("Prepaid"))
            .otherwise(pl.col("PAYMENT_TYPE"))
            .alias("PAYMENT_TYPE")
        )

    fallback_cfg = rules.get("fallback_by_cod_amount") or {}
    fallback_enabled = bool(fallback_cfg.get("enabled", False))
    if fallback_enabled and "COD_AMOUNT" in result.columns:
        zero_label = _canonical_label(fallback_cfg.get("treat_zero_dash_empty_as") or "Prepaid")
        positive_label = _canonical_label(fallback_cfg.get("treat_positive_as") or "COD")
        cod_raw = pl.col("COD_AMOUNT").cast(pl.Utf8)
        stripped = cod_raw.str.strip_chars()
        sanitized = stripped.str.replace_all(r"[^0-9\.\-]", "")
        zero_like = (
            cod_raw.is_null()
            | (stripped == "")
            | (stripped == "-")
            | (sanitized == "")
            | (sanitized == "-")
            | (sanitized == "0")
            | (sanitized == "0.0")
            | (sanitized == "0.00")
        )
        converted = sanitized.cast(pl.Float64, strict=False)
        result = result.with_columns(
            [
                pl.when(zero_like).then(0.0).otherwise(converted).fill_null(0.0).alias("COD_AMOUNT_NUM"),
                ((~zero_like) & converted.is_null()).alias("__cod_parse_failed"),
            ]
        )
        parse_fail_col = "__cod_parse_failed"
        if parse_fail_col in result.columns:
            try:
                parse_fail_count = int(result[parse_fail_col].sum() or 0)
            except TypeError:
                parse_fail_count = 0
            if parse_fail_count:
                logger.warning(
                    "Stage06 payment: %d COD_AMOUNT value(s) failed parsing; treated as zero.", parse_fail_count
                )
            result = result.drop(parse_fail_col)
        result = result.with_columns(
            pl.when((pl.col("PAYMENT_TYPE") == "Unknown") & (pl.col("COD_AMOUNT_NUM") > 0))
            .then(pl.lit(positive_label))
            .otherwise(pl.col("PAYMENT_TYPE"))
            .alias("PAYMENT_TYPE")
        )
        result = result.with_columns(
            pl.when((pl.col("PAYMENT_TYPE") == "Unknown") & (pl.col("COD_AMOUNT_NUM") <= 0))
            .then(pl.lit(zero_label))
            .otherwise(pl.col("PAYMENT_TYPE"))
            .alias("PAYMENT_TYPE")
        )
        result = result.drop("COD_AMOUNT_NUM")

    return result
