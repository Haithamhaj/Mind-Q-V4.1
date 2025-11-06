from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SECTOR_PROTECT: Set[str] = {
    "cod_amount",
    "rto_flag",
    "rto_rate",
    "sla_target",
    "sla_achieved",
    "zone",
    "area",
    "carrier",
    "service_level",
    "weight_kg",
    "volumetric_weight",
    "dimensions",
    "payment_type",
    "weekday",
    "month",
    "pickup_window",
    "delivery_slot",
    "return_reason",
}

REASON_PRIORITY = {"leakage": 0, "correlation": 1, "nzv": 2}


def _emit_json(payload: Dict[str, object]) -> None:
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run final decider after readiness")
    parser.add_argument("--run-id", required=True, help="Pipeline run identifier")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Root directory for pipeline artifacts (default: artifacts)",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Required artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_feature_manifest(feature_dir: Path) -> List[str]:
    manifest_path = feature_dir / "feature_manifest.json"
    if manifest_path.exists():
        data = _read_json(manifest_path)
        columns = data.get("columns")
        if isinstance(columns, list):
            return [str(col) for col in columns]
    features_path = feature_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"Unable to determine features; missing {manifest_path} and {features_path}")
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pandas is required to inspect features for the decider") from exc
    df = pd.read_parquet(features_path)
    return [str(col) for col in df.columns]


def _score_feature(name: str) -> Tuple[int, int]:
    lname = name.lower()
    if "leakage" in lname:
        return (0, len(name))
    if "raw" in lname:
        return (1, len(name))
    if "standard" in lname or "std" in lname:
        return (2, len(name))
    if "simple" in lname or "base" in lname or "derived" in lname:
        return (3, len(name))
    if "bucket" in lname or "bin" in lname:
        return (4, len(name))
    return (5, len(name))


def _build_corr_clusters(pairs: Iterable[Dict[str, object]]) -> List[Set[str]]:
    graph: Dict[str, Set[str]] = defaultdict(set)
    for pair in pairs:
        f1 = pair.get("f1")
        f2 = pair.get("f2")
        if not isinstance(f1, str) or not isinstance(f2, str):
            continue
        graph[f1].add(f2)
        graph[f2].add(f1)

    visited: Set[str] = set()
    clusters: List[Set[str]] = []

    for node in graph:
        if node in visited:
            continue
        queue: deque[str] = deque([node])
        component: Set[str] = set()
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in graph[current]:
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) > 1:
            clusters.append(component)
    return clusters


def _assign_reason(
    target_set: Set[str],
    column: str,
    reason: str,
    priority_map: Dict[str, int],
    feature_reasons: Dict[str, str],
):
    current = feature_reasons.get(column)
    if current is None or priority_map[reason] < priority_map.get(current, 99):
        feature_reasons[column] = reason
    target_set.add(column)


def main() -> int:
    args = parse_args()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    readiness_dir = artifacts_root / args.run_id / "stage_07_readiness"
    feature_dir = artifacts_root / args.run_id / "stage_06_feature_eng"

    readiness_report = _read_json(readiness_dir / "readiness_report.json")
    redundancy = _read_json(readiness_dir / "redundancy.json")
    leakage_scan = _read_json(readiness_dir / "leakage_scan.json")
    stability = _read_json(readiness_dir / "stability.json")

    all_features = set(_load_feature_manifest(feature_dir))
    total_features = len(all_features)
    if total_features == 0:
        raise RuntimeError("No features detected for decider evaluation")

    nzv_features = {
        str(entry.get("feature"))
        for entry in redundancy.get("near_zero_variance", [])
        if isinstance(entry, dict) and entry.get("feature")
    }
    high_corr_pairs = [
        entry
        for entry in redundancy.get("high_corr_pairs", [])
        if isinstance(entry, dict)
    ]
    leakage_id_like = {
        str(item) for item in leakage_scan.get("id_like", []) if isinstance(item, str)
    }
    leakage_after_event = {
        str(entry.get("feature"))
        for entry in leakage_scan.get("after_event_like", [])
        if isinstance(entry, dict) and entry.get("feature")
    }
    psi_entries = stability.get("psi", []) if isinstance(stability, dict) else []
    psi_stop = {
        str(entry.get("feature"))
        for entry in psi_entries
        if isinstance(entry, dict) and entry.get("status") == "STOP" and entry.get("feature")
    }

    drop_set: Set[str] = set()
    review_set: Set[str] = set()
    feature_reasons: Dict[str, str] = {}

    # Leakage has highest priority
    for feature in leakage_id_like | leakage_after_event:
        if feature not in all_features:
            continue
        if feature.lower() in SECTOR_PROTECT:
            review_set.add(feature)
        else:
            _assign_reason(drop_set, feature, "leakage", REASON_PRIORITY, feature_reasons)

    # High correlation clusters
    clusters = _build_corr_clusters(high_corr_pairs)
    for cluster in clusters:
        ranked = sorted(cluster, key=_score_feature)
        representative = ranked[0]
        for feature in cluster:
            if feature == representative:
                continue
            if feature.lower() in SECTOR_PROTECT:
                review_set.add(feature)
            else:
                _assign_reason(drop_set, feature, "correlation", REASON_PRIORITY, feature_reasons)

    # Near-zero variance
    for feature in nzv_features:
        if feature not in all_features:
            continue
        if feature in drop_set:
            continue
        if feature.lower() in SECTOR_PROTECT:
            review_set.add(feature)
        else:
            _assign_reason(drop_set, feature, "nzv", REASON_PRIORITY, feature_reasons)

    # PSI STOP -> review
    for feature in psi_stop:
        if feature not in all_features:
            continue
        review_set.add(feature)

    drop_only = sorted(drop_set)
    review_only = sorted(review_set - drop_set)
    keep_set = sorted(all_features - drop_set - review_set)

    keep = len(keep_set)
    drop = len(drop_only)
    review = len(review_only)
    drop_ratio = float(drop) / float(total_features) if total_features else 0.0

    if drop_ratio >= 0.9:
        sanity_payload = {
            "run_id": args.run_id,
            "reason": "mass_drop_threshold",
            "drop_ratio": drop_ratio,
            "keep": keep,
            "drop": drop,
            "review": review,
        }
        (readiness_dir / "decision_sanity.json").write_text(json.dumps(sanity_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DECISION] KEEP={keep} DROP={drop} REVIEW={review}")
    sys.stdout.flush()

    decision = {
        "run_id": args.run_id,
        "keep": keep,
        "drop": drop,
        "review": review,
        "drop_ratio": drop_ratio,
        "keep_features": keep_set,
        "drop_features": drop_only,
        "review_features": review_only,
        "feature_reasons": feature_reasons,
        "gate_status": readiness_report.get("gate", {}).get("status"),
    }
    _emit_json(decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
