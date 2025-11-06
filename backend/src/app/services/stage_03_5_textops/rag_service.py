from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

import numpy as np  # type: ignore
import polars as pl  # type: ignore

try:  # pragma: no cover - optional dependency
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None  # type: ignore

from .emb_openai import embed_texts_openai


class RagNotAvailable(RuntimeError):
    pass


def _require_faiss() -> None:
    if faiss is None:  # pragma: no cover - import guard
        raise RagNotAvailable("faiss is not installed")


def load_index(path: str):
    _require_faiss()
    return faiss.read_index(path)  # type: ignore[attr-defined]


def encode_question(question: str, cfg: Dict[str, object]) -> np.ndarray:
    embeddings_cfg = cfg.get("embeddings", {})
    if not isinstance(embeddings_cfg, dict):
        raise RagNotAvailable("Invalid embeddings configuration")
    provider = embeddings_cfg.get("provider", "local")
    if provider != "openai":
        raise RagNotAvailable("Only OpenAI embeddings are implemented")
    model = embeddings_cfg.get("model")
    if not isinstance(model, str):
        raise RagNotAvailable("Embeddings model missing")
    dimensions = embeddings_cfg.get("dimensions")
    dim = int(dimensions) if isinstance(dimensions, (int, float)) else None
    batch_size = int(embeddings_cfg.get("batch_size", 256))
    max_retries = int(embeddings_cfg.get("max_retries", 5))
    timeout_sec = int(embeddings_cfg.get("timeout_sec", 60))
    vector = embed_texts_openai(
        [question],
        model=model,
        dimensions=dim,
        batch_size=batch_size,
        max_retries=max_retries,
        timeout_sec=timeout_sec,
    )
    return vector.astype("float32")


def retrieve_documents(
    question: str,
    cfg: Dict[str, object],
    *,
    top_k: int,
) -> List[int]:
    rag_cfg = cfg.get("rag", {})
    if not isinstance(rag_cfg, dict):
        raise RagNotAvailable("Invalid RAG configuration")
    index_path = rag_cfg.get("index_path")
    if not isinstance(index_path, str):
        raise RagNotAvailable("Index path missing")
    index = load_index(index_path)
    vector = encode_question(question, cfg)
    distances, indices = index.search(vector, top_k)  # type: ignore[attr-defined]
    return indices[0].tolist()


def answer_with_citations(question: str, cfg: Dict[str, object]) -> Dict[str, object]:
    rag_cfg = cfg.get("rag", {})
    if not isinstance(rag_cfg, dict):
        raise RagNotAvailable("Invalid RAG configuration")
    if not rag_cfg.get("enabled"):
        raise RagNotAvailable("RAG disabled")
    map_path = rag_cfg.get("map_parquet")
    seg_path = rag_cfg.get("doc_segments")
    if not isinstance(map_path, str) or not isinstance(seg_path, str):
        raise RagNotAvailable("Mapping paths missing")
    top_k = int(rag_cfg.get("top_k", 6))
    max_ctx = int(rag_cfg.get("max_ctx_tokens", 1500))
    indices = retrieve_documents(question, cfg, top_k=top_k)
    seg_map = pl.read_parquet(map_path)
    segs = pl.read_parquet(seg_path)
    vector_ids = set(indices)
    rows = seg_map.filter(pl.col("vector_id").is_in(vector_ids))
    segment_ids = rows["segment_id"].to_list() if rows.height > 0 else []
    picked: List[int] = []
    context_parts: List[str] = []
    for entry in segs.iter_rows(named=True):
        sid = entry.get("segment_id")
        if sid not in segment_ids:
            continue
        text = entry.get("text")
        if not isinstance(text, str):
            continue
        candidate = f"[{sid}] {text.strip()}"
        new_len = len("\n".join(context_parts)) + len(candidate)
        if new_len > max_ctx:
            break
        context_parts.append(candidate)
        picked.append(sid)
    return {
        "context": "\n".join(context_parts),
        "citations": picked,
    }


__all__ = ["answer_with_citations", "RagNotAvailable"]
