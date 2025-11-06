from __future__ import annotations

import numpy as np
import pytest

try:  # pragma: no cover - optional dependency under test
    from pyod.models.iforest import IForest  # type: ignore
except Exception:  # pragma: no cover - dependency guard
    IForest = None  # type: ignore


@pytest.mark.skipif(IForest is None, reason="PyOD is not installed")
def test_iforest_scores_are_normalised() -> None:
    rng = np.random.default_rng(42)
    baseline = rng.normal(loc=0.0, scale=1.0, size=(256, 3))
    anomalies = rng.normal(loc=8.0, scale=0.3, size=(6, 3))
    data = np.vstack([baseline, anomalies])

    model = IForest(contamination=0.02, random_state=42)
    model.fit(data)

    proba = model.predict_proba(data)[:, 1]
    assert float(proba.min()) >= 0.0
    assert float(proba.max()) <= 1.0

    labels = model.predict(data)
    assert labels.sum() >= anomalies.shape[0]
    assert proba[-anomalies.shape[0]:].mean() > proba[:-anomalies.shape[0]].mean()