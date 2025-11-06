from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from typing import Any, Callable, Dict, List, Tuple, cast

pytest.importorskip("dowhy")

from backend.src.app.services.stage_09_5_causal_inference.config_loader import CausalConfig
from backend.src.app.services.stage_09_5_causal_inference.estimate import (
    EstimationOutputs,
    estimate_propensity,
    run_estimators,
)
import backend.src.app.services.stage_09_5_causal_inference.identify as identify_module
from backend.src.app.services.stage_09_5_causal_inference.impl import build_root_cause_hints_payload
import backend.src.app.services.stage_09_5_causal_inference.impl as stage09_impl


def _synthetic_frame(seed: int = 42, n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    common = rng.normal(loc=0.0, scale=1.0, size=n)
    treatment_noise = rng.normal(loc=0.0, scale=0.5, size=n)
    treatment = (common + treatment_noise > 0).astype(int)
    outcome_noise = rng.normal(loc=0.0, scale=0.3, size=n)
    outcome = 2.5 * treatment + 0.8 * common + outcome_noise
    segments = np.where(common > 0, "A", "B")
    return pd.DataFrame(
        {
            "treatment": treatment,
            "outcome": outcome,
            "common": common,
            "segment": segments,
        }
    )


def _test_config() -> CausalConfig:
    return CausalConfig(
        problem_name="synthetic_case",
        description="synthetic test",
        treatment="treatment",
        outcome="outcome",
        common_causes=["common"],
        effect_modifiers=["segment"],
        instrumental_variables=[],
        frontdoor_variables=[],
        min_sample_size=100,
        confidence_level=0.95,
        test_size=0.2,
        estimation_methods=["backdoor.psm"],
        refutation_tests=["random_common_cause"],
        bi_publish_rule="SUPPORTED_ONLY",
    )


def test_root_cause_hints_payload_uses_adapter_metadata() -> None:
    df = _synthetic_frame()
    config = _test_config()

    identify_any = getattr(identify_module, "identify_estimand")
    identify = cast(
        Callable[[pd.DataFrame, CausalConfig], Tuple[Any, Any, List[str]]],
        identify_any,
    )
    model_any, estimand, assumptions = identify(df, config)
    estimation: EstimationOutputs = run_estimators(model_any, estimand, df, config)

    propensity = estimate_propensity(df, config.treatment, config.common_causes)
    overlap_gate = getattr(stage09_impl, "_overlap_gate")
    overlap_info = cast(Dict[str, Any], overlap_gate(propensity))

    payload = build_root_cause_hints_payload(
        run_id="testrun",
        config=config,
        estimation=estimation,
        assumptions=assumptions,
        overlap_ok=overlap_info["overlap"],
    )

    assert payload["method"] == "adapter"
    assert payload["run_id"] == "testrun"
    assert payload["problem_name"] == config.problem_name
    assert "segments" in payload and isinstance(payload["segments"], list)
    assert payload["baseline_method"] == estimation.method_baseline

