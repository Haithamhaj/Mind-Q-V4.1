from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from backend.src.app.services.stage_03_5_textops import contracts, features, normalize


def test_normalize_arabic_transforms() -> None:
    raw = "إتِّصالٌ ١٢٣٤٥ شكراً"
    result = normalize.normalize_ar_en(
        raw,
        unescape_html=True,
        unify_alef_ya_ta=True,
        strip_diacritics=True,
        unify_digits=True,
    )
    assert "اتصال" in result
    assert "12345" in result
    assert "شكرا" in result


def test_mask_pii_replacements() -> None:
    text = "Call me at +966-555-123456 or mail test@example.com visit https://example.com"
    masked = normalize.mask_pii(text)
    assert "<PHONE>" in masked
    assert "<EMAIL>" in masked
    assert "<URL>" in masked


def test_density_features_counts() -> None:
    texts = ["hello world", "مرحبا", "😊"]
    payload = features.make_density_features(texts)
    assert payload["len_char"] == [11, 5, 1]
    assert payload["len_tok"] == [2, 1, 1]
    assert payload["has_emoji"] == [0, 0, 1]


def test_sentiment_lite_balances() -> None:
    texts = ["good service", "تأخير سيء", "neutral"]
    scores = features.sentiment_lite(texts)
    assert scores[0] > 0
    assert scores[1] < 0
    assert scores[2] == 0


def test_vectors_hash_svd_metadata() -> None:
    texts = ["alpha beta", "gamma delta", "epsilon zeta"]
    reduced, meta = features.vectors_hash_svd(texts, 128, 8, seed=42)
    assert reduced.shape[0] == len(texts)
    assert "explained_variance_ratio" in meta
    assert meta["svd_components"] <= 8


def test_validate_row_keys_detects_nulls() -> None:
    df = pl.DataFrame({"AWB_NO": ["a", None, "c"], "value": [1, 2, 3]})
    with pytest.raises(contracts.ContractError):
        contracts.validate_row_keys(df, ["AWB_NO"])
