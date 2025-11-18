from __future__ import annotations

import json
import math
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import importlib.metadata as importlib_metadata
import numpy as np  # type: ignore
import polars as pl  # type: ignore
from dotenv import dotenv_values, load_dotenv
from polars.datatypes import Datetime as PlDatetime  # type: ignore

from .config_schema import TextOpsConfig, load_config
from .contracts import ContractError, enforce_privacy_on_evidence, validate_row_keys
from .evidence import build_examples, build_text_profile, top_terms_keyphrases
from .features import make_density_features, sentiment_lite, vectors_hash_svd
from .kpi_linker import build_kpi_links
from .llm_assist import RagBundle, run_llm_tasks
from .logging_utils import append_log, artefact_manifest, sha256_file, utcnow_iso, write_json, write_jsonl
from .normalize import normalize_ar_en, mask_pii
from .emb_openai import OpenAIEmbeddingError, embed_texts_openai

DEFAULT_CONFIG_PATH = Path("config/textops.yaml")
PROJECT_ROOT = Path(__file__).resolve().parents[5]
BACKEND_ROOT = PROJECT_ROOT / "backend"
ENV_KEY_PREFIXES: Tuple[str, ...] = (
    "OPENAI_",
    "AZURE_OPENAI_",
    "GOOGLE_",
    "ANTHROPIC_",
    "MISTRAL_",
    "KPI_",
)

JOIN_KEY_CANDIDATES: Tuple[str, ...] = ("AWB_NO", "awb_no", "shipment_id", "SHIPMENT_ID")
TEXT_COLUMNS_FALLBACK: Tuple[str, ...] = ("item_desc", "customer_note")
MAX_SEGMENTS = 5_000
SEGMENT_TOKENS = 120
SEGMENT_OVERLAP = 30
STOP = "STOP"
WARN = "WARN"
PASS = "PASS"

FLAG_TRUE_VALUES = {"1", "true", "yes", "on", "t", "y"}
ADDRESS_SPLIT_RE = re.compile(r"[,\n;|]+|\s+_\s+|\s+-\s+|\s+/\s+")
SENDER_ADDRESS_KEYS: Tuple[str, ...] = ("sender address", "shipper address", "pickup address", "origin address")
RECEIVER_ADDRESS_KEYS: Tuple[str, ...] = ("receiver address", "delivery address", "consignee address", "destination address")
SENDER_PHONE_KEYS: Tuple[str, ...] = ("sender phone", "shipper phone", "pickup phone", "sender contact")
RECEIVER_PHONE_KEYS: Tuple[str, ...] = ("receiver phone", "delivery phone", "consignee phone", "receiver contact")
CITY_SENDER_KEYS: Tuple[str, ...] = ("origin", "sender city", "origin city")
CITY_RECEIVER_KEYS: Tuple[str, ...] = ("destination", "receiver city", "delivery city")


def _is_flag_enabled(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip().lower() in FLAG_TRUE_VALUES)


LLM_RULES_SCHEMA = {
    "rule_id": pl.Utf8,
    "partner_id": pl.Utf8,
    "metric": pl.Utf8,
    "operator": pl.Utf8,
    "value": pl.Utf8,
    "unit": pl.Utf8,
    "scope": pl.Utf8,
    "valid_from": pl.Utf8,
    "valid_to": pl.Utf8,
    "source_doc_id": pl.Utf8,
    "citation_segment_ids": pl.List(pl.Int64),
}

LLM_SOPS_SCHEMA = {
    "sop_id": pl.Utf8,
    "step_no": pl.Int64,
    "actor": pl.Utf8,
    "action": pl.Utf8,
    "condition": pl.Utf8,
    "expected_output": pl.Utf8,
    "source_doc_id": pl.Utf8,
    "citation_segment_ids": pl.List(pl.Int64),
}

LLM_PROFILE_SCHEMA = {
    "services": pl.List(pl.Utf8),
    "cities": pl.List(pl.Utf8),
    "working_hours": pl.Utf8,
    "cod_policy": pl.Utf8,
    "notes": pl.Utf8,
    "citations": pl.List(pl.Int64),
}

LLM_CONTACTS_SCHEMA = {
    "person_name": pl.Utf8,
    "role": pl.Utf8,
    "contact": pl.Utf8,
    "channel": pl.Utf8,
    "availability_window": pl.Utf8,
    "citations": pl.List(pl.Int64),
}


def _ensure_frame(data: Any, schema: Dict[str, Any]) -> pl.DataFrame:
    """
    Ensures data is a Polars DataFrame with the given schema.
    If data is None or empty, returns an empty DataFrame with the schema.
    """
    if data is None:
        return pl.DataFrame(schema=schema)
    if isinstance(data, pl.DataFrame):
        return data
    if isinstance(data, list):
        if not data:
            return pl.DataFrame(schema=schema)
        return pl.DataFrame(data, schema=schema)
    if isinstance(data, dict):
        return pl.DataFrame([data], schema=schema)
    return pl.DataFrame(schema=schema)


def _match_column(columns: Sequence[str], keywords: Sequence[str]) -> Optional[str]:
    lowered = {col.lower(): col for col in columns}
    for lowered_name, original in lowered.items():
        normalized = lowered_name.replace("_", " ")
        for keyword in keywords:
            if keyword in lowered_name or keyword in normalized:
                return original
    return None


def _address_components(value: Any) -> List[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = ADDRESS_SPLIT_RE.split(text)
    return [part.strip() for part in parts if part and part.strip()]


def _sanitize_phone(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if text.startswith("+"):
        return f"+{digits}"
    return digits


def _build_structured_fields(frame: pl.DataFrame, join_key: str) -> Optional[pl.DataFrame]:
    sender_addr_col = _match_column(frame.columns, SENDER_ADDRESS_KEYS)
    receiver_addr_col = _match_column(frame.columns, RECEIVER_ADDRESS_KEYS)
    sender_phone_col = _match_column(frame.columns, SENDER_PHONE_KEYS)
    receiver_phone_col = _match_column(frame.columns, RECEIVER_PHONE_KEYS)
    sender_city_col = _match_column(frame.columns, CITY_SENDER_KEYS)
    receiver_city_col = _match_column(frame.columns, CITY_RECEIVER_KEYS)

    structured_cols: Dict[str, pl.Series] = {join_key: frame[join_key]}
    has_structured = False

    if sender_addr_col:
        structured_cols["sender_address_components"] = frame[sender_addr_col].map_elements(
            lambda value: json.dumps(_address_components(value), ensure_ascii=False)
        )
        has_structured = True
    if receiver_addr_col:
        structured_cols["receiver_address_components"] = frame[receiver_addr_col].map_elements(
            lambda value: json.dumps(_address_components(value), ensure_ascii=False)
        )
        has_structured = True
    if sender_phone_col:
        structured_cols["sender_phone_structured"] = frame[sender_phone_col].map_elements(_sanitize_phone)
        has_structured = True
    if receiver_phone_col:
        structured_cols["receiver_phone_structured"] = frame[receiver_phone_col].map_elements(_sanitize_phone)
        has_structured = True
    if sender_city_col:
        structured_cols["sender_city_hint"] = frame[sender_city_col]
        has_structured = True
    if receiver_city_col:
        structured_cols["receiver_city_hint"] = frame[receiver_city_col]
        has_structured = True

    if not has_structured:
        return None
    return pl.DataFrame(structured_cols)


def _apply_env_entries(entries: Mapping[str, Any]) -> None:
    for key, value in entries.items():
        if not value:
            continue
        if any(key.startswith(prefix) for prefix in ENV_KEY_PREFIXES):
            os.environ.setdefault(key, str(value))


def _load_env_credentials(cfg: TextOpsConfig) -> None:
    candidates: List[Path] = []
    if cfg.llm.credentials_file:
        candidates.append(Path(cfg.llm.credentials_file).expanduser())
    override = os.getenv("MINDQ_LLM_CREDENTIALS_FILE")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.extend(
        [
            BACKEND_ROOT / "llm.env",
            BACKEND_ROOT / ".env",
            PROJECT_ROOT / "llm.env",
            PROJECT_ROOT / ".env",
            Path.cwd() / ".env",
        ]
    )

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        try:
            load_dotenv(resolved, override=False)
            entries = dotenv_values(resolved)
        except Exception:
            continue
        _apply_env_entries(entries)


def _resolve_config(config: Mapping[str, Any]) -> TextOpsConfig:
    config_path = Path(config.get("config_path", DEFAULT_CONFIG_PATH)).expanduser()
    overrides = {key: value for key, value in config.items() if key != "config_path"}
    return load_config(config_path, overrides if overrides else None)


def _resolve_artifacts_root(config: Mapping[str, Any]) -> Path:
    root = config.get("artifacts_root", "artifacts")
    return Path(root).expanduser().resolve()


def _pick_join_key(frame: pl.DataFrame) -> str:
    for candidate in JOIN_KEY_CANDIDATES:
        if candidate in frame.columns:
            return candidate
    raise ContractError("No join key column detected (expected AWB_NO or shipment_id)")


def _format_path(template: str, run_id: str) -> str:
    return template.format(run_id=run_id)


def _load_json_safe(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _text_columns(catalog: Mapping[str, Any]) -> List[str]:
    if not catalog:
        return list(TEXT_COLUMNS_FALLBACK)
    if "text_columns" in catalog and isinstance(catalog["text_columns"], Sequence):
        return [str(col) for col in catalog["text_columns"]]
    if "columns" in catalog and isinstance(catalog["columns"], Mapping):
        return [
            str(col)
            for col, meta in catalog["columns"].items()
            if isinstance(meta, Mapping) and meta.get("type") in {"text", "string"}
        ]
    return list(TEXT_COLUMNS_FALLBACK)


def _stopwords(domain_dict: Mapping[str, Any], key: str) -> List[str]:
    values = domain_dict.get(key)
    if isinstance(values, Sequence):
        return [str(item).lower() for item in values]
    return []


def _normalize_column(series: pl.Series, *, config: TextOpsConfig) -> pl.Series:
    return series.cast(pl.Utf8, strict=False).fill_null("").map_elements(
        lambda value: mask_pii(
            normalize_ar_en(
                value,
                unescape_html=config.normalize.unescape_html,
                unify_alef_ya_ta=config.normalize.unify_alef_ya_ta,
                strip_diacritics=config.normalize.strip_diacritics,
                unify_digits=config.normalize.unify_digits,
            )
        ),
        return_dtype=pl.Utf8,
    )


def _detect_lang(text: str) -> str:
    if not text:
        return "unknown"
    has_ar = any("؀" <= ch <= "ۿ" for ch in text)
    has_en = any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)
    if has_ar and not has_en:
        return "ar"
    if has_en and not has_ar:
        return "en"
    if has_ar and has_en:
        return "mix"
    return "unknown"


def _lang_stats(lang_codes: Sequence[str]) -> Dict[str, float]:
    counter = Counter(lang_codes)
    total = sum(counter.values()) or 1
    return {lang: round(count / total, 4) for lang, count in counter.items()}


def _coverage(non_empty: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(non_empty / total * 100, 2)


def _versions() -> Dict[str, str]:
    packages = ("polars", "numpy", "scikit-learn", "ftfy", "regex")
    payload: Dict[str, str] = {}
    for package in packages:
        try:
            payload[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            continue
    return payload


def _prepare_timestamps(series: pl.Series, timezone: str) -> Optional[pl.Series]:
    ts = series
    if ts.dtype == pl.Utf8:
        ts = ts.str.strptime(pl.Datetime, strict=False)
    dtype = ts.dtype
    if isinstance(dtype, PlDatetime):
        if dtype.time_zone:
            ts = ts.dt.convert_time_zone(timezone)
        else:
            ts = ts.dt.replace_time_zone(timezone)
        return ts
    return None


def _chunk_tokens(text: str, max_tokens: int = SEGMENT_TOKENS, overlap: int = SEGMENT_OVERLAP) -> List[str]:
    words = text.split()
    if not words:
        return []
    parts: List[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_tokens)
        snippet = " ".join(words[start:end]).strip()
        if snippet:
            parts.append(snippet)
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return parts


def _iter_sources(
    run_id: str,
    cfg: TextOpsConfig,
    artifacts_root: Path,
    join_key: str,
    shipments_df: pl.DataFrame,
    combined_texts: List[str],
) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    for key, text in zip(shipments_df[join_key], combined_texts):
        trimmed = text.strip()
        if not trimmed:
            continue
        sources.append({"source": "shipment", "source_key": str(key), "text": trimmed})

    docs_path = cfg.inputs.docs_path
    if docs_path:
        doc_template = _format_path(docs_path, run_id)
        candidate = Path(doc_template)
        if not candidate.is_absolute():
            candidate = (artifacts_root / doc_template).resolve()
        if candidate.exists():
            for path in candidate.rglob("*.txt"):
                try:
                    raw = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                normalised = normalize_ar_en(raw, unescape_html=True)
                masked = mask_pii(normalised)
                if masked.strip():
                    sources.append({"source": "doc", "source_key": path.name, "text": masked})
    return sources


def _build_rag_bundle(
    run_id: str,
    cfg: TextOpsConfig,
    artifacts_root: Path,
    out_dir: Path,
    join_key: str,
    shipments_df: pl.DataFrame,
    combined_texts: List[str],
) -> Tuple[Optional[RagBundle], Dict[str, Path], List[Dict[str, str]]]:
    warnings: List[Dict[str, str]] = []
    sources = _iter_sources(run_id, cfg, artifacts_root, join_key, shipments_df, combined_texts)
    if not sources:
        return None, {}, warnings

    segments: List[Dict[str, Any]] = []
    segment_id = 0
    seen = set()
    for entry in sources:
        for snippet in _chunk_tokens(entry["text"]):
            key = (entry["source"], entry["source_key"], snippet)
            if key in seen:
                continue
            seen.add(key)
            segments.append(
                {
                    "segment_id": segment_id,
                    "vector_id": segment_id,
                    "source": entry["source"],
                    "source_key": entry["source_key"],
                    "text": snippet,
                }
            )
            segment_id += 1
            if segment_id >= MAX_SEGMENTS:
                break
        if segment_id >= MAX_SEGMENTS:
            break

    if not segments:
        return None, {}, warnings

    segments_df = pl.DataFrame(segments)

    if cfg.embeddings.provider.lower() != "openai":
        raise RuntimeError(f"Embedding provider '{cfg.embeddings.provider}' is not supported")

    model_name = cfg.embeddings.model or "text-embedding-3-small"

    try:
        embeddings = embed_texts_openai(
            segments_df["text"].to_list(),
            model=model_name,
            dimensions=cfg.embeddings.dimensions,
            batch_size=cfg.embeddings.batch_size,
            max_retries=cfg.embeddings.max_retries,
            timeout_sec=cfg.embeddings.timeout_sec,
        )
    except OpenAIEmbeddingError as exc:
        raise RuntimeError(str(exc))

    if embeddings.size == 0:
        return None, {}, warnings

    embeddings = embeddings.astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    segments_path = out_dir / "doc_segments.parquet"
    map_path = out_dir / "embeddings.map.parquet"
    index_path = out_dir / "embeddings.faiss"

    segments_df.write_parquet(segments_path.as_posix())
    map_df = pl.DataFrame({"vector_id": segments_df["vector_id"], "segment_id": segments_df["segment_id"]})
    map_df.write_parquet(map_path.as_posix())

    try:  # pragma: no cover - optional dependency
        import faiss  # type: ignore

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        faiss.write_index(index, index_path.as_posix())
    except Exception:
        index_path.write_bytes(b"")

    if cfg.vector_store.type.lower() == "qdrant":
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            collection = cfg.vector_store.qdrant.collection.format(run_id=run_id)
            client = QdrantClient(url=cfg.vector_store.qdrant.host, port=cfg.vector_store.qdrant.port)
            client.recreate_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=embeddings.shape[1], distance=Distance.COSINE),
            )
            payload = []
            for idx, row in enumerate(segments_df.to_dicts()):
                payload.append(
                    {
                        "id": int(row["vector_id"]),
                        "vector": embeddings[idx].tolist(),
                        "payload": {
                            "segment_id": int(row["segment_id"]),
                            "source": row["source"],
                            "source_key": row["source_key"],
                        },
                    }
                )
            if cfg.vector_store.qdrant.prefer_batch:
                client.upload_points(collection_name=collection, points=payload)
            else:
                for point in payload:
                    client.upsert(collection_name=collection, points=[point])
        except Exception as exc:  # pragma: no cover - optional dependency
            warnings.append({"code": "vector_store_error", "message": str(exc)})

    bundle = RagBundle(
        segments=segments_df,
        embeddings=embeddings,
        vector_ids=np.arange(len(segments_df)),
        embed_fn=lambda texts: embed_texts_openai(
            list(texts),
            model=model_name,
            dimensions=cfg.embeddings.dimensions,
            batch_size=cfg.embeddings.batch_size,
            max_retries=cfg.embeddings.max_retries,
            timeout_sec=cfg.embeddings.timeout_sec,
        ),
        top_k=cfg.rag.top_k,
        max_context_chars=cfg.rag.max_ctx_tokens,
    )
    return bundle, {"segments": segments_path, "map": map_path, "index": index_path}, warnings






def _maybe_extract_document_fields(
    run_id: str,
    cfg: TextOpsConfig,
    artifacts_root: Path,
    out_dir: Path,
) -> Tuple[Optional[Path], List[Dict[str, str]], int]:
    if not _is_flag_enabled("USE_EXT_DOCUMENT_FIELD_EXTRACTION"):
        return None, [], 0

    docs_path = cfg.inputs.docs_path
    if not docs_path:
        return None, [], 0

    doc_template = _format_path(docs_path, run_id)
    doc_root = Path(doc_template)
    if not doc_root.is_absolute():
        doc_root = (artifacts_root / doc_template).resolve()
    if not doc_root.exists():
        return None, [], 0

    try:
        from backend.adapters.docs_textqa_baseline import extract_fields_from_directory  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        return None, [
            {
                "code": "document_extraction_import_error",
                "message": str(exc),
            }
        ], 0

    try:
        payload, adapter_warnings = extract_fields_from_directory(doc_root)
    except Exception as exc:
        return None, [
            {
                "code": "document_extraction_failed",
                "message": str(exc),
            }
        ], 0

    warnings: List[Dict[str, str]] = []
    for warn in adapter_warnings:
        warnings.append({"code": "document_extraction_warning", "message": warn})

    documents = payload.get("documents") or []
    if not documents:
        return None, warnings, 0

    payload["run_id"] = run_id
    payload["generated_at"] = utcnow_iso(cfg.timezone)
    output_path = out_dir / "document_field_predictions.json"
    write_json(output_path, payload)
    return output_path, warnings, len(documents)


def run(run_id: str, inputs: Mapping[str, Any], config: Mapping[str, Any]) -> Dict[str, Any]:
    cfg = _resolve_config(config)
    _load_env_credentials(cfg)
    openai_key = os.environ.get("OPENAI_API_KEY")
    if cfg.embeddings.provider.lower() == "openai":
        if cfg.embeddings.api_key:
            openai_key = cfg.embeddings.api_key
            os.environ["OPENAI_API_KEY"] = openai_key
    artifacts_root = _resolve_artifacts_root(config)
    out_dir = artifacts_root / run_id / "stage_03_5_textops"
    out_dir.mkdir(parents=True, exist_ok=True)
    logs: List[Dict[str, Any]] = []
    started_at = utcnow_iso(cfg.timezone)
    append_log(logs, "phase_start", run_id=run_id)
    random.seed(cfg.seed)
    np.random.seed(cfg.seed)

    shipments_pattern = str(inputs.get("shipments") or _format_path(cfg.inputs.shipments_path, run_id))
    domain_dict_path = Path(inputs.get("domain_dict") or _format_path(cfg.sources.domain_dict, run_id)).expanduser()
    text_catalog_path = Path(inputs.get("text_catalog") or _format_path(cfg.sources.text_catalog, run_id)).expanduser()
    kpi_map_path = Path(inputs.get("kpi_map") or _format_path(cfg.sources.kpi_map, run_id)).expanduser()

    try:
        shipments_df = pl.scan_parquet(shipments_pattern).collect()
    except Exception as exc:  # pragma: no cover - IO guard
        raise RuntimeError(f"Failed to read shipments parquet: {exc}") from exc

    if shipments_df.is_empty():
        raise RuntimeError("Shipments dataset is empty; nothing to process")

    join_key = _pick_join_key(shipments_df)
    append_log(logs, "join_key_detected", join_key=join_key)

    text_catalog = _load_json_safe(text_catalog_path)
    text_columns = [col for col in _text_columns(text_catalog) if col in shipments_df.columns]
    
    if not text_columns:
        normalization_report_path = artifacts_root / run_id / "stage_03_schema" / "semantic" / "normalized" / "normalization_report.json"
        normalization_report = _load_json_safe(normalization_report_path)
        if normalization_report and "columns" in normalization_report:
            text_columns = [
                col["column"]
                for col in normalization_report["columns"]
                if col.get("selected_for_terminology") and col.get("detected_kind") == "text" and col["column"] in shipments_df.columns
            ]
            append_log(logs, "text_columns_from_normalization", count=len(text_columns))
    
    if not text_columns:
        fallback = [col for col in TEXT_COLUMNS_FALLBACK if col in shipments_df.columns]
        text_columns = fallback
    
    if not text_columns:
        raise RuntimeError("No textual columns available for Phase 3.5 processing")

    shipments_df = shipments_df.with_columns(
        [_normalize_column(pl.col(col), config=cfg).alias(f"{col}__clean") for col in text_columns]
    )
    clean_columns = [f"{col}__clean" for col in text_columns]

    combined = shipments_df.select(
        pl.concat_str([pl.col(col) for col in clean_columns], separator=" ").alias("__text_concat")
    )
    texts = combined["__text_concat"].to_list()
    lang_codes = [_detect_lang(text) for text in texts]

    density = make_density_features(texts)
    sentiments = sentiment_lite(texts)

    timestamps = None
    if "created_at" in shipments_df.columns:
        timestamps = _prepare_timestamps(shipments_df["created_at"], cfg.timezone)

    structured_fields_path: Optional[Path] = None
    structured_frame = _build_structured_fields(shipments_df, join_key)
    if structured_frame is not None and structured_frame.height > 0:
        structured_fields_path = out_dir / "structured_fields.parquet"
        structured_frame.write_parquet(structured_fields_path.as_posix())
        append_log(
            logs,
            "structured_fields_generated",
            columns=[col for col in structured_frame.columns if col != join_key],
        )
    else:
        append_log(logs, "structured_fields_skipped", reason="no_candidate_columns")

    sentiment_payload: Dict[str, Any] = {
        join_key: shipments_df[join_key],
        "sentiment_score": sentiments,
        "len_char": density["len_char"],
        "len_tok": density["len_tok"],
        "has_emoji": density["has_emoji"],
        "lang_code": lang_codes,
    }
    if timestamps is not None:
        sentiment_payload["ts_local"] = timestamps
    sentiment_df = pl.DataFrame(sentiment_payload)

    validate_row_keys(sentiment_df, [join_key])

    svd_components = cfg.vectorization.svd_components
    est_memory = len(texts) * max(1, svd_components) * 4.0
    if est_memory > 4 * 1024 * 1024 * 1024:
        svd_components = max(32, svd_components // 2)

    reduced, vector_meta = vectors_hash_svd(texts, cfg.vectorization.hash_n_features, svd_components, cfg.seed)

    vector_cols: Dict[str, Any] = {join_key: shipments_df[join_key]}
    for idx in range(reduced.shape[1]):
        vector_cols[f"txt_svd_{idx}"] = reduced[:, idx]
    vectors_df = pl.DataFrame(vector_cols)
    validate_row_keys(vectors_df, [join_key])

    domain_dict = _load_json_safe(domain_dict_path)
    kpi_map = _load_json_safe(kpi_map_path)
    stopwords_ar = _stopwords(domain_dict, "stopwords_ar")
    stopwords_en = _stopwords(domain_dict, "stopwords_en")
    top_terms, keyphrases = top_terms_keyphrases(texts, stopwords_ar, stopwords_en)

    non_empty = sum(1 for text in texts if text.strip())
    coverage_pct = _coverage(non_empty, len(texts))
    unreadable_pct = round(100 - coverage_pct, 2)

    lang_primary = [code for code in lang_codes if code in {"ar", "en"}]
    lang_stats = _lang_stats(lang_primary)
    missing_openai_key = cfg.embeddings.provider.lower() == "openai" and not openai_key
    warnings: List[Dict[str, str]] = []
    if missing_openai_key:
        warnings.append({"code": "embeddings_credentials_missing", "message": "OPENAI_API_KEY not detected; embeddings/LLM features disabled."})
    errors: List[Dict[str, str]] = []
    status = PASS

    if unreadable_pct > cfg.thresholds.stop_unreadable_docs_pct:
        status = STOP
        errors.append(
            {
                "code": "unreadable_docs",
                "message": f"Unreadable documents {unreadable_pct:.2f}% exceeded stop threshold",
            }
        )

    conflict_pct = 0.0
    if lang_stats:
        top_ratio = max(lang_stats.values()) * 100
        conflict_pct = round(100 - top_ratio, 2)
        if conflict_pct > cfg.thresholds.warn_lang_conflict_pct and status != STOP:
            status = WARN
            warnings.append(
                {
                    "code": "lang_conflict",
                    "message": f"Language conflict {conflict_pct:.2f}% exceeds warn threshold",
                }
            )

    explained = float(vector_meta.get("explained_variance_ratio", 0.0))
    if explained < cfg.thresholds.svd_min_explained_var_pct:
        if status == PASS:
            status = WARN
        warnings.append(
            {
                "code": "svd_low_variance",
                "message": f"Explained variance {explained:.4f} below {cfg.thresholds.svd_min_explained_var_pct}",
            }
        )

    sparse_pct = round(100 - coverage_pct, 2)
    if sparse_pct > cfg.thresholds.warn_sparse_coverage_pct and status == PASS:
        status = WARN
        warnings.append({"code": "sparse_text", "message": f"Sparse coverage {sparse_pct:.2f}%"})

    columns_payload: Dict[str, Dict[str, Any]] = {}
    for col in text_columns:
        cleaned_col = f"{col}__clean"
        sample_texts = shipments_df[cleaned_col].head(200).to_list()
        column_top, column_phrases = top_terms_keyphrases(sample_texts, stopwords_ar, stopwords_en, top_k=15)
        columns_payload[col] = {
            "top_tokens": [{"token": token, "score": idx + 1} for idx, token in enumerate(column_top[:10])],
            "keyphrases": column_phrases[:10],
        }

    example_rows = shipments_df.select([join_key, clean_columns[0]]).to_dicts()
    examples = build_examples(example_rows, join_key, clean_columns[0])

    finished_at = utcnow_iso(cfg.timezone)
    text_profile = build_text_profile(
        run_id=run_id,
        tz=cfg.timezone,
        lang_stats=lang_stats,
        doc_counts={"rows": len(texts), "non_empty_rows": non_empty},
        top_terms=top_terms,
        keyphrases=keyphrases,
        topic_tags=top_terms[:10],
        examples=examples,
        flags={"pii": False, "html": False, "encoding": True},
        provenance={
            "source_uri": shipments_pattern,
            "extraction_method": "hash+svd",
            "hash_sha256": "",
        },
        runtime={
            "versions": _versions(),
            "seed": cfg.seed,
            "started_at": started_at,
            "finished_at": finished_at,
        },
        columns=columns_payload,
    )

    # PII privacy check disabled per user request
    # enforce_privacy_on_evidence(text_profile)

    rag_bundle: Optional[RagBundle] = None
    rag_paths: Dict[str, Path] = {}
    rag_enabled = cfg.rag.enabled and not missing_openai_key
    if rag_enabled:
        try:
            rag_bundle, rag_paths, rag_warnings = _build_rag_bundle(
                run_id,
                cfg,
                artifacts_root,
                out_dir,
                join_key,
                shipments_df,
                texts,
            )
            warnings.extend(rag_warnings)
            if rag_bundle:
                append_log(logs, "rag_assets_created", segments=rag_bundle.segments.height)
            else:
                warnings.append({"code": "rag_empty", "message": "No segments available for RAG."})
        except Exception as exc:
            warnings.append({"code": "rag_error", "message": str(exc)})
            rag_bundle = None
            rag_paths = {}

    llm_tables: Dict[str, pl.DataFrame] = {}
    llm_traces: List[Dict[str, Any]] = []
    llm_enabled = cfg.llm.enabled and not missing_openai_key
    if llm_enabled:
        try:
            llm_tables, llm_traces, llm_warnings = run_llm_tasks(run_id, cfg, rag_bundle, domain_dict)
            warnings.extend(llm_warnings)
        except Exception as exc:
            warnings.append({"code": "llm_error", "message": str(exc)})
            llm_tables = {}
            llm_traces = []
    doc_fields_path: Optional[Path] = None
    doc_fields_count = 0
    try:
        doc_fields_path, doc_field_warnings, doc_fields_count = _maybe_extract_document_fields(
            run_id, cfg, artifacts_root, out_dir
        )
        warnings.extend(doc_field_warnings)
        if doc_fields_path:
            append_log(
                logs,
                "document_fields_extracted",
                documents=doc_fields_count,
                output=doc_fields_path.as_posix(),
            )
    except Exception as exc:
        warnings.append({"code": "document_extraction_error", "message": str(exc)})
        doc_fields_path = None
        doc_fields_count = 0

    if warnings and status == PASS:        status = WARN

    sentiment_path = out_dir / "sentiment_features.parquet"
    vectors_path = out_dir / "svd_components.parquet"
    tfidf_info_path = out_dir / "tfidf_info.json"
    profile_path = out_dir / "text_profile.json"
    report_path = out_dir / "textops_report.json"
    findings_path = out_dir / "quality_findings.json"
    ready_flag_path = out_dir / "_READY.OK"
    manifest_path = out_dir / "manifest.json"
    log_path = out_dir / "logs" / "run.log"

    sentiment_df.write_parquet(sentiment_path.as_posix())
    vectors_df.write_parquet(vectors_path.as_posix())
    text_profile["provenance"]["hash_sha256"] = sha256_file(sentiment_path)
    write_json(
        tfidf_info_path,
        {
            "mode": "hash",
            "hash_n_features": cfg.vectorization.hash_n_features,
            "svd_components": vector_meta.get("svd_components", 0),
            "explained_variance_ratio": explained,
        },
    )
    write_json(profile_path, text_profile)
    write_json(
        report_path,
        {
            "run_id": run_id,
            "n_rows": len(texts),
            "coverage_pct": coverage_pct,
            "unreadable_pct": unreadable_pct,
            "lang_conflict_pct": conflict_pct,
            "svd_explained_variance": explained,
        },
    )
    write_json(findings_path, {"warnings": warnings, "errors": errors})
    write_jsonl(log_path, logs)
    if cfg.handoff.ready_flag:
        ready_flag_path.touch()

    artefacts = [
        {"path": sentiment_path.as_posix(), "sha256": sha256_file(sentiment_path)},
        {"path": vectors_path.as_posix(), "sha256": sha256_file(vectors_path)},
        {"path": tfidf_info_path.as_posix(), "sha256": sha256_file(tfidf_info_path)},
        {"path": profile_path.as_posix(), "sha256": sha256_file(profile_path)},
        {"path": report_path.as_posix(), "sha256": sha256_file(report_path)},
        {"path": findings_path.as_posix(), "sha256": sha256_file(findings_path)},
    ]
    if doc_fields_path:
        artefacts.append({"path": doc_fields_path.as_posix(), "sha256": sha256_file(doc_fields_path)})
    if structured_fields_path:
        artefacts.append({"path": structured_fields_path.as_posix(), "sha256": sha256_file(structured_fields_path)})

    outputs: Dict[str, str] = {
        "sentiment_features": sentiment_path.as_posix(),
        "svd_components": vectors_path.as_posix(),
        "tfidf_info": tfidf_info_path.as_posix(),
        "text_profile": profile_path.as_posix(),
        "report": report_path.as_posix(),
        "quality_findings": findings_path.as_posix(),
        "manifest": manifest_path.as_posix(),
        "log": log_path.as_posix(),
    }
    if doc_fields_path:
        outputs["document_field_predictions"] = doc_fields_path.as_posix()
    if structured_fields_path:
        outputs["structured_fields"] = structured_fields_path.as_posix()

    for key, path in rag_paths.items():
        if path.exists():
            artefacts.append({"path": path.as_posix(), "sha256": sha256_file(path)})
            if key == "segments":
                outputs["doc_segments"] = path.as_posix()
            elif key == "map":
                outputs["embeddings_map"] = path.as_posix()
            elif key == "index":
                outputs["embeddings_index"] = path.as_posix()

    if llm_tables:
        rules_path = out_dir / "rules_sla_llm.parquet"
        sops_path = out_dir / "sop_steps_llm.parquet"
        profile_llm_path = out_dir / "company_profile_llm.parquet"
        contacts_path = out_dir / "contacts_llm.parquet"
        trace_path = out_dir / "llm_trace.jsonl"

        rules_df = _ensure_frame(llm_tables.get("rules"), LLM_RULES_SCHEMA)
        sops_df = _ensure_frame(llm_tables.get("sops"), LLM_SOPS_SCHEMA)
        profile_llm_df = _ensure_frame(llm_tables.get("profile"), LLM_PROFILE_SCHEMA)
        contacts_df = _ensure_frame(llm_tables.get("contacts"), LLM_CONTACTS_SCHEMA)

        rules_df.write_parquet(rules_path.as_posix())
        sops_df.write_parquet(sops_path.as_posix())
        profile_llm_df.write_parquet(profile_llm_path.as_posix())
        contacts_df.write_parquet(contacts_path.as_posix())
        write_jsonl(trace_path, llm_traces)

        kpi_links_df = build_kpi_links(rules_df, kpi_map)
        kpi_links_path = out_dir / "kpi_links.parquet"
        kpi_links_df.write_parquet(kpi_links_path.as_posix())

        for candidate in [rules_path, sops_path, profile_llm_path, contacts_path, trace_path, kpi_links_path]:
            if candidate.exists():
                artefacts.append({"path": candidate.as_posix(), "sha256": sha256_file(candidate)})

        outputs.update(
            {
                "rules_sla_llm": rules_path.as_posix(),
                "sop_steps_llm": sops_path.as_posix(),
                "company_profile_llm": profile_llm_path.as_posix(),
                "contacts_llm": contacts_path.as_posix(),
                "llm_trace": trace_path.as_posix(),
                "kpi_links": kpi_links_path.as_posix(),
            }
        )

    if cfg.handoff.write_manifest:
        write_json(manifest_path, artefact_manifest(artefacts))

    return {
        "run_id": run_id,
        "status": status,
        "outputs": outputs,
        "metrics": {
            "n_rows": len(texts),
            "coverage_pct": coverage_pct,
            "lang_conflict_pct": conflict_pct,
            "svd_explained_variance": explained,
            "document_fields_extracted": doc_fields_count,
        },
        "logs_uri": log_path.as_posix(),
    }


__all__ = ["run"]
