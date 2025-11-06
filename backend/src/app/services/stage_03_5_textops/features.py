from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np  # type: ignore
from sklearn.decomposition import TruncatedSVD  # type: ignore
from sklearn.feature_extraction.text import HashingVectorizer  # type: ignore


def make_density_features(texts: Sequence[str]) -> Dict[str, List[int]]:
    lens_char = [len(text or "") for text in texts]
    lens_tok = [len((text or "").split()) for text in texts]
    has_emoji = [int(any(ord(ch) > 0x1F000 for ch in (text or ""))) for text in texts]
    return {
        "len_char": lens_char,
        "len_tok": lens_tok,
        "has_emoji": has_emoji,
    }


def sentiment_lite(texts: Sequence[str]) -> List[float]:
    positive = ("ممتاز", "جيد", "great", "good", "شكرا", "ممتازه", "excellent", "awesome")
    negative = ("سيء", "سيئ", "تأخير", "تلف", "إلغاء", "bad", "late", "damaged", "worst")
    scores: List[float] = []
    for text in texts:
        payload = text or ""
        lower = payload.lower()
        p_hits = sum(1 for token in positive if token.lower() in lower)
        n_hits = sum(1 for token in negative if token.lower() in lower)
        total = p_hits + n_hits
        scores.append(0.0 if total == 0 else (p_hits - n_hits) / total)
    return scores


def vectors_hash_svd(
    texts: Sequence[str],
    n_features: int,
    n_components: int,
    seed: int,
) -> Tuple[np.ndarray, Dict[str, float]]:
    if not texts:
        return (
            np.empty((0, n_components), dtype=np.float32),
            {
                "mode": "hash",
                "hash_n_features": float(n_features),
                "svd_components": float(n_components),
                "explained_variance_ratio": 0.0,
            },
        )
    vectorizer = HashingVectorizer(
        n_features=n_features,
        alternate_sign=False,
        ngram_range=(1, 2),
        norm="l2",
    )
    matrix = vectorizer.transform(texts)
    max_rank = max(1, min(matrix.shape) - 1)
    eff_components = int(min(n_components, max_rank))
    if eff_components <= 0:
        eff_components = 1
    svd = TruncatedSVD(n_components=eff_components, random_state=seed)
    reduced = svd.fit_transform(matrix)
    meta = {
        "mode": "hash",
        "hash_n_features": float(n_features),
        "svd_components": float(eff_components),
        "explained_variance_ratio": float(svd.explained_variance_ratio_.sum()),
    }
    return reduced.astype(np.float32), meta


__all__ = ["make_density_features", "sentiment_lite", "vectors_hash_svd"]
