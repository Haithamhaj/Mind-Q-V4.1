from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class Stage06Paths:
    """Canonical locations for Stage 06 outputs used by downstream phases."""

    run_root: Path
    stage05_dir: Path
    stage06_standardize_dir: Path
    stage06_feature_dir: Path
    features: Path
    curated_features: Path
    layer1_dataset: Path
    layer1_schema: Path
    feature_spec: Path
    imputed_primary: Path
    imputed_fallback: Path
    raw: Path

    def resolved_imputed(self) -> Path:
        """Return the first available imputed dataset (clean -> legacy -> raw)."""
        for candidate in (self.imputed_primary, self.imputed_fallback, self.raw):
            if candidate.exists():
                return candidate
        return self.imputed_primary

    def resolved_features(self) -> Path:
        return self.features

    def resolved_curated(self) -> Path:
        if self.curated_features.exists():
            return self.curated_features
        return self.features

    def layer1_assets(self) -> Tuple[Path, Path]:
        return self.layer1_dataset, self.layer1_schema


def resolve_stage06_paths(run_id: str, artifacts_root: Path) -> Stage06Paths:
    base = Path(artifacts_root).expanduser().resolve() / run_id
    stage05_dir = base / "stage_05_missing"
    stage06_standardize_dir = base / "stage_06_standardize"
    stage06_feature_dir = base / "stage_06_feature_eng"
    return Stage06Paths(
        run_root=base,
        stage05_dir=stage05_dir,
        stage06_standardize_dir=stage06_standardize_dir,
        stage06_feature_dir=stage06_feature_dir,
        features=stage06_feature_dir / "features.parquet",
        curated_features=stage06_feature_dir / "features.curated.parquet",
        layer1_dataset=stage06_feature_dir / "layer1_dataset.parquet",
        layer1_schema=stage06_feature_dir / "layer1_schema.json",
        feature_spec=stage06_feature_dir / "feature_spec.json",
        imputed_primary=stage05_dir / "clean_imputed.parquet",
        imputed_fallback=stage05_dir / "imputed.parquet",
        raw=base / "stage_01_ingestion" / "raw.parquet",
    )


__all__ = ["Stage06Paths", "resolve_stage06_paths"]
