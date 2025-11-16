from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "backend" / "src" / "app" / "services" / "nzv_policy.py"
spec = importlib.util.spec_from_file_location("nzv_policy_module", MODULE_PATH.as_posix())
assert spec and spec.loader
nzv_policy = importlib.util.module_from_spec(spec)
sys.modules.setdefault("nzv_policy_module", nzv_policy)
spec.loader.exec_module(nzv_policy)


def test_policy_defaults_loaded_from_file() -> None:
    nzv_policy.clear_policy_cache()
    policy = nzv_policy.load_policy()

    assert policy.dominant_constant_like == pytest.approx(0.98)
    assert policy.dominant_nzv == pytest.approx(0.95)
    assert policy.dominant_high_imbalance == pytest.approx(0.90)
    assert policy.max_unique_for_nzv == 5
    assert policy.min_rows_required == 50
    assert policy.enable_readiness_adjustment is True
    assert policy.max_nzv_ratio_for_pass == pytest.approx(0.35)
    assert policy.force_nzv == frozenset()
    assert policy.force_not_nzv == frozenset()


@pytest.mark.parametrize(
    "dominant_pct,expected_category",
    [
        (0.899, "normal"),
        (0.90, "high_imbalance"),
        (0.949, "high_imbalance"),
        (0.95, "near_zero_variance"),
        (0.979, "near_zero_variance"),
        (0.98, "constant_like"),
    ],
)
def test_classify_column_thresholds(dominant_pct: float, expected_category: str) -> None:
    policy = nzv_policy.NZVPolicy(
        dominant_constant_like=0.98,
        dominant_nzv=0.95,
        dominant_high_imbalance=0.90,
        max_unique_for_nzv=5,
        min_rows_required=0,
    )
    result = nzv_policy.classify_column(
        {"name": "STATUS", "dominant_pct": dominant_pct, "unique_count": 3, "n_rows": 100},
        policy=policy,
    )
    assert result["nzv_category"] == expected_category
    if expected_category in {"constant_like", "near_zero_variance"}:
        assert result["is_nzv"] is True
    else:
        assert result["is_nzv"] is False
    reason = result["reason"]
    assert isinstance(reason, str)
    if expected_category == "constant_like":
        assert "0.98" in reason
    elif expected_category == "near_zero_variance":
        assert "0.95" in reason
    elif expected_category == "high_imbalance":
        assert reason.startswith("dominant_pct>=")


def test_force_overrides_take_priority() -> None:
    policy = nzv_policy.NZVPolicy(
        force_nzv=frozenset({"FORCED_NZV"}),
        force_not_nzv=frozenset({"FORCED_NORMAL"}),
    )

    force_not = nzv_policy.classify_column(
        {"name": "FORCED_NORMAL", "dominant_pct": 0.99, "unique_count": 1, "n_rows": 200},
        policy=policy,
    )
    assert force_not["nzv_category"] == "normal"
    assert force_not["is_nzv"] is False
    assert force_not["reason"] == "force_not_nzv"

    force_yes = nzv_policy.classify_column(
        {"name": "FORCED_NZV", "dominant_pct": 0.50, "unique_count": 10, "n_rows": 200},
        policy=policy,
    )
    assert force_yes["nzv_category"] == "near_zero_variance"
    assert force_yes["is_nzv"] is True
    assert force_yes["reason"] == "force_nzv"

    stats_override = nzv_policy.classify_column({"name": "TEMP", "force_not_nzv": True, "n_rows": 10}, policy=policy)
    assert stats_override["reason"] == "force_not_nzv"
