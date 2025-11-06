from __future__ import annotations

import os
import time
from typing import Iterable, List, Optional, Sequence

import numpy as np  # type: ignore

try:  # pragma: no cover - optional dependency
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class OpenAIEmbeddingError(RuntimeError):
    pass


def _client() -> "OpenAI":  # type: ignore[override]
    if OpenAI is None:  # pragma: no cover - import guard
        raise OpenAIEmbeddingError("openai package not installed")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIEmbeddingError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)


def _batched(texts: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    chunk: List[str] = []
    for text in texts:
        chunk.append(text)
        if len(chunk) >= size:
            yield tuple(chunk)
            chunk = []
    if chunk:
        yield tuple(chunk)


def embed_texts_openai(
    texts: Sequence[str],
    *,
    model: str,
    dimensions: Optional[int] = None,
    batch_size: int = 256,
    max_retries: int = 5,
    timeout_sec: int = 60,
) -> np.ndarray:
    if not texts:
        return np.empty((0, dimensions or 0), dtype=np.float32)
    client = _client()
    embeddings: List[np.ndarray] = []
    for batch in _batched(texts, batch_size):
        retries = 0
        while True:
            try:
                response = client.embeddings.create(
                    model=model,
                    input=list(batch),
                    dimensions=dimensions,
                )
                for data in response.data:
                    embeddings.append(np.asarray(data.embedding, dtype=np.float32))
                break
            except Exception as exc:  # pragma: no cover - network
                retries += 1
                if retries > max_retries:
                    raise OpenAIEmbeddingError(str(exc)) from exc
                time.sleep(min(timeout_sec, 1.5 * retries))
    return np.vstack(embeddings)


__all__ = ["embed_texts_openai", "OpenAIEmbeddingError"]
