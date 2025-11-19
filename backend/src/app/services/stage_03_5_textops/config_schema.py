from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml
from pydantic import BaseModel, Field, ConfigDict


class InputsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shipments_path: str = Field(..., description="Glob pattern pointing at shipments parquet files.")
    docs_path: Optional[str] = Field(None, description="Optional directory holding raw document files.")
    notes_path: Optional[str] = Field(None, description="Optional directory holding notes extracts.")


class SourcesConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    domain_dict: str = Field(..., description="Path template for the Phase 03 domain dictionary.")
    text_catalog: str = Field(..., description="Path template for the Phase 03 text columns catalog.")
    kpi_map: str = Field(..., description="Path to KPI map (placeholder for future linking).")
    dim_keys: str = Field(..., description="Path to dimensional keys (placeholder for future linking).")


class PrivacyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mask_pii: bool = True
    pii_tool: str = Field("rules", description="Masking engine identifier: rules only for now.")


class LangConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    detect_topk: int = 2


class NormalizeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unify_alef_ya_ta: bool = True
    strip_diacritics: bool = True
    unify_digits: bool = True
    unescape_html: bool = True


class VectorizationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = Field("hash", description="Vectorizer mode: hash (default) or tfidf.")
    tfidf_max_features: int = 100_000
    hash_n_features: int = 262_144
    svd_components: int = 64


class SentimentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    engine: str = Field("lite", description="Sentiment engine identifier: lite or transformer.")
    model_name: Optional[str] = None


class EmbeddingsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = Field("local", description="Embedding provider: local or openai.")
    model: Optional[str] = Field(None, description="Embedding model name when provider requires it.")
    dimensions: Optional[int] = None
    batch_size: int = 256
    max_retries: int = 5
    timeout_sec: int = 60
    use_batch_api: bool = False
    api_key: Optional[str] = Field(None, description="Optional override for provider API key.")


class RagConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    index_path: Optional[str] = None
    map_parquet: Optional[str] = None
    doc_segments: Optional[str] = None
    top_k: int = 6
    max_ctx_tokens: int = 1500


class VectorStoreQdrantConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    host: str = Field("http://localhost", description="HTTP endpoint for Qdrant.")
    port: int = 6333
    collection: str = Field("textops_{run_id}", description="Collection name template.")
    prefer_batch: bool = False


class VectorStoreConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field("faiss", description="Vector store backend (faiss or qdrant).")
    qdrant: VectorStoreQdrantConfig = VectorStoreQdrantConfig()


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    provider: str = Field("openai", description="LLM provider identifier (openai, gemini, ...)")
    model: str = Field("gpt-4o-mini", description="Model alias for the configured provider.")
    temperature: float = 0.0
    top_p: float = 0.0
    max_tokens: int = 512
    timeout_sec: int = 180
    credentials_file: Optional[str] = Field(None, description="Optional path to .env-style credentials.")
    tasks: list[str] = Field(default_factory=lambda: ["extract_sla", "extract_sop", "summarize"], description="Enabled LLM tasks.")


class HandoffConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    write_manifest: bool = True
    ready_flag: bool = True


class ThresholdsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stop_unreadable_docs_pct: float = 25.0
    warn_lang_conflict_pct: float = 15.0
    warn_sparse_coverage_pct: float = 30.0
    svd_min_explained_var_pct: float = 0.70
    join_sample_min: int = 1_000


class DocsTextOpsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    doc_roots: Dict[str, str] = Field(default_factory=dict, description="Mapping of document types to directories.")
    reader_priority: List[str] = Field(default_factory=lambda: [".txt", ".md"], description="Ordered suffixes to read.")
    chunk_tokens: int = 200
    chunk_overlap: int = 40
    max_chars: int = 4000
    client_map: Optional[str] = Field(None, description="Optional JSON mapping of doc paths to client_id.")
    llm_enabled: bool = True


class TextOpsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = "1.0"
    seed: int = 42
    timezone: str = "Asia/Riyadh"
    inputs: InputsConfig
    sources: SourcesConfig
    privacy: PrivacyConfig = PrivacyConfig()
    lang: LangConfig = LangConfig()
    normalize: NormalizeConfig = NormalizeConfig()
    vectorization: VectorizationConfig = VectorizationConfig()
    sentiment: SentimentConfig = SentimentConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    rag: RagConfig = RagConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    llm: LlmConfig = LlmConfig()
    docs_textops: DocsTextOpsConfig = DocsTextOpsConfig()
    handoff: HandoffConfig = HandoffConfig()
    thresholds: ThresholdsConfig = ThresholdsConfig()


def _load_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration file {path} must contain a YAML mapping.")
    return payload


def load_config(path: Path, overrides: Optional[Mapping[str, Any]] = None) -> TextOpsConfig:
    base = _load_yaml(path) if path.exists() else {}
    merged: Dict[str, Any] = dict(base)
    if overrides:
        def _merge(dst: Dict[str, Any], src: Mapping[str, Any]) -> Dict[str, Any]:
            for key, value in src.items():
                if isinstance(value, Mapping) and isinstance(dst.get(key), Mapping):
                    dst[key] = _merge(dict(dst[key]), value)
                else:
                    dst[key] = value
            return dst
        merged = _merge(dict(base), overrides)
    return TextOpsConfig.model_validate(merged)


__all__ = ["TextOpsConfig", "load_config"]
