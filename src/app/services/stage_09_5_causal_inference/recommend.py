from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .config_loader import CausalConfig


def _priority_from_effect(effect: float) -> str:
    magnitude = abs(effect)
    if magnitude >= 0.25:
        return "HIGH"
    if magnitude >= 0.12:
        return "MEDIUM"
    return "LOW"


def _cost_hint(modifier: str) -> str:
    keyword = modifier.lower()
    if "training" in keyword or "experience" in keyword:
        return "med"
    if "pricing" in keyword or "discount" in keyword:
        return "high"
    return "low"


def build_recommendations(
    config: CausalConfig,
    cate_segments: Iterable[Dict[str, Any]],
    ate: Optional[float],
    cate_mean: Optional[float],
) -> Dict[str, Any]:
    structured: List[Dict[str, Any]] = []
    textual: List[str] = []

    segments = list(cate_segments)[:5]
    for segment_info in segments:
        segment = segment_info.get("segment", "")
        effect = float(segment_info.get("effect", 0.0) or 0.0)
        n = int(segment_info.get("n", 0) or 0)
        priority = _priority_from_effect(effect)
        modifier = segment.split("=")[0] if "=" in segment else segment
        structured.append(
            {
                "priority": priority,
                "segment": segment,
                "action": f"Adjust {config.treatment} strategy for {segment}",
                "expected_impact_text": f"Estimated effect under assumptions: Δ{config.outcome} ≈ {effect:+.3f}",
                "estimated_sample": n,
                "implementation_cost": _cost_hint(modifier or segment),
            }
        )
        textual.append(
            f"{priority} priority: Estimated effect under assumptions suggests focusing on {segment} could shift "
            f"{config.outcome} by ~{effect:+.3f} (n={n})."
        )

    if not textual:
        overall_effect = ate if ate is not None else cate_mean
        if overall_effect is not None:
            textual.append(
                f"Estimated effect under assumptions indicates average Δ{config.outcome} ≈ {overall_effect:+.3f}. "
                f"Monitor {config.treatment} across key segments before operational rollout."
            )
        else:
            textual.append(
                "Estimated effect under assumptions is inconclusive with current data. "
                "Consider collecting more observations before acting."
            )

    return {"structured": structured, "text": textual}
