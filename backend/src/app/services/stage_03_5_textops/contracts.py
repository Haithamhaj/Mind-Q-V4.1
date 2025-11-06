from __future__ import annotations

from typing import Iterable, Mapping

import polars as pl  # type: ignore
import regex as re  # type: ignore

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:(?:\+?[\d]{1,3})?[\s\-]*\d[\d\-\s]{5,}\d)")
_RAW_ID_RE = re.compile(r"\b\d{10,}\b")
ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


class ContractError(RuntimeError):
    pass


def validate_row_keys(frame: pl.DataFrame, keys: Iterable[str]) -> None:
    for key in keys:
        if key not in frame.columns:
            raise ContractError(f"Missing required join key column: {key}")
        nulls = int(frame[key].null_count())
        empties = int(frame[key].is_in(["", None]).sum())
        if nulls or empties:
            raise ContractError(f"Join key {key} contains null or empty values")


def enforce_privacy_on_evidence(profile: Mapping[str, object]) -> None:
    def _iter_strings(node) -> Iterable[str]:
        if isinstance(node, str):
            yield node
        elif isinstance(node, Mapping):
            for value in node.values():
                yield from _iter_strings(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                yield from _iter_strings(item)

    for value in _iter_strings(profile):
        if ISO_TS_RE.match(value):
            continue
        if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
            raise ContractError("PII detected in evidence payload")
        if _RAW_ID_RE.search(value) and "<ID>" not in value:
            raise ContractError("Potential ID detected without masking")


def assert_timezone(series: pl.Series, tz: str) -> None:
    if series.is_empty():
        return
    if series.dtype != pl.Datetime(time_zone=tz):
        raise ContractError(f"Expected timezone-aware datetime with tz={tz}, got {series.dtype}")


__all__ = ["ContractError", "validate_row_keys", "enforce_privacy_on_evidence", "assert_timezone"]
