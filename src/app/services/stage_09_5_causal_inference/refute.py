from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _refute_single(model: Any, estimate: Any, method_name: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": method_name}
    try:
        result = model.refute_estimate(estimate, method_name=method_name)
    except Exception as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
        return payload

    result_text = getattr(result, "refutation_result", "")
    p_value = getattr(result, "p_value", None)
    new_effect = getattr(result, "new_effect", None)
    payload["status"] = "PASSED" if isinstance(result_text, str) and "Not refuted" in result_text else "FAILED"
    payload["result_text"] = str(result_text)
    if p_value is not None:
        payload["p_value"] = p_value
    if new_effect is not None:
        payload["new_effect"] = new_effect
    return payload


def run_refuters(model: Any, estimate: Any, methods: Iterable[str]) -> Dict[str, Any]:
    """Execute configured DoWhy refutation tests."""
    if estimate is None:
        return {"tests": [], "passed_count": 0, "supported": False}

    results: List[Dict[str, Any]] = []
    passed = 0
    for method in methods:
        clean_method = method.strip()
        if not clean_method:
            continue
        outcome = _refute_single(model, estimate, clean_method)
        if outcome.get("status") == "PASSED":
            passed += 1
        results.append(outcome)
    return {"tests": results, "passed_count": passed, "supported": passed >= 3}
