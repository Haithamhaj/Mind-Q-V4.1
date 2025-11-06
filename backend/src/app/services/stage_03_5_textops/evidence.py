from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import regex as re  # type: ignore

_TOKEN_RE = re.compile(r"\p{L}[\p{L}\p{N}_]+", re.UNICODE)


def _ngram_tokens(tokens: Sequence[str], n: int) -> Iterable[str]:
    for idx in range(len(tokens) - n + 1):
        yield " ".join(tokens[idx : idx + n])


def _tokenize(text: str, stopwords: Sequence[str]) -> List[str]:
    lowered_stop = {token.lower() for token in stopwords}
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in tokens if token not in lowered_stop and len(token) > 1]


def top_terms_keyphrases(
    texts: Sequence[str],
    stopwords_ar: Sequence[str],
    stopwords_en: Sequence[str],
    *,
    top_k: int = 30,
) -> Tuple[List[str], List[str]]:
    combined_stop = list(stopwords_ar) + [word.lower() for word in stopwords_en]
    tokens: List[str] = []
    bigrams: List[str] = []
    for text in texts:
        if not text:
            continue
        filtered = _tokenize(text, combined_stop)
        tokens.extend(filtered)
        bigrams.extend(list(_ngram_tokens(filtered, 2)))
    token_counts = Counter(tokens)
    bigram_counts = Counter(bigrams)
    top_terms = [term for term, _ in token_counts.most_common(top_k)]
    keyphrases = [phrase for phrase, _ in bigram_counts.most_common(max(10, top_k // 2))]
    return top_terms, keyphrases


def build_text_profile(
    *,
    run_id: str,
    tz: str,
    lang_stats: Mapping[str, float],
    doc_counts: Mapping[str, int],
    top_terms: Sequence[str],
    keyphrases: Sequence[str],
    topic_tags: Sequence[str],
    examples: Sequence[Mapping[str, object]],
    flags: Mapping[str, object],
    provenance: Mapping[str, object],
    runtime: Mapping[str, object],
    columns: Mapping[str, Mapping[str, object]],
) -> Dict[str, object]:
    return {
        "run_id": run_id,
        "tz": tz,
        "lang_stats": dict(lang_stats),
        "doc_counts": dict(doc_counts),
        "top_terms": list(top_terms),
        "keyphrases": list(keyphrases),
        "topic_tags": list(topic_tags),
        "examples": [dict(example) for example in examples],
        "flags": dict(flags),
        "provenance": dict(provenance),
        "runtime": dict(runtime),
        "columns": {key: dict(value) for key, value in columns.items()},
        "global": {
            "top_tokens": [
                {"token": term, "score": idx + 1}
                for idx, term in enumerate(top_terms[:20])
            ],
            "keyphrases": list(keyphrases[:20]),
        },
    }


def build_examples(
    rows: Sequence[Mapping[str, object]],
    join_key: str,
    text_field: str,
    *,
    max_examples: int = 5,
    max_len: int = 240,
) -> List[Dict[str, object]]:
    examples: List[Dict[str, object]] = []
    for row in rows:
        text = row.get(text_field)
        key = row.get(join_key)
        if not text or text in (None, "") or key in (None, ""):
            continue
        excerpt = str(text)
        if len(excerpt) > max_len:
            excerpt = excerpt[: max_len - 3] + "..."
        examples.append({
            "key": str(key),
            "excerpt": excerpt,
            "masked": True,
        })
        if len(examples) >= max_examples:
            break
    return examples


__all__ = ["top_terms_keyphrases", "build_text_profile", "build_examples"]
