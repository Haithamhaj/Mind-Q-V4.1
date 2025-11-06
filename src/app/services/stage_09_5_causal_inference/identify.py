from __future__ import annotations

from typing import List, Tuple

import pandas as pd  # type: ignore

from .config_loader import CausalConfig

try:  # pragma: no cover - optional dependency
    from dowwhy import CausalModel  # type: ignore
except Exception:  # pragma: no cover - defensive
    CausalModel = None  # type: ignore[misc]


def identify_estimand(data: pd.DataFrame, config: CausalConfig) -> Tuple["CausalModel", object, List[str]]:
    """Construct a DoWhy causal model and identify the target estimand."""
    if CausalModel is None:  # pragma: no cover - executed when dowhy missing
        raise ImportError("dowhy>=0.11 is required for causal identification")

    model = CausalModel(
        data=data,
        treatment=config.treatment,
        outcome=config.outcome,
        common_causes=config.common_causes or None,
        instruments=config.instrumental_variables or None,
        frontdoor_variables=config.frontdoor_variables or None,
        effect_modifiers=config.effect_modifiers or None,
    )

    estimand = model.identify_effect(proceed_when_unidentifiable=True)

    assumptions: List[str] = ["overlap"]
    if config.instrumental_variables:
        assumptions.append("instrument_validity")
    elif config.frontdoor_variables:
        assumptions.append("frontdoor")
    else:
        assumptions.append("backdoor")
    if config.common_causes:
        assumptions.append("no_unmeasured_confounding")
    if config.effect_modifiers:
        assumptions.append("conditional_effects")

    return model, estimand, assumptions
