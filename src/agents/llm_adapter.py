from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Dict, Tuple

import httpx  # type: ignore

MODEL_RATES: Dict[Tuple[str, str], Tuple[float, float]] = {
    ("openai", "gpt-4-turbo"): (0.01, 0.03),
    ("openai", "gpt-4o-mini"): (0.00015, 0.0006),
    ("anthropic", "claude-3-5-sonnet"): (0.003, 0.015),
    ("gemini", "gemini-2.0-flash"): (0.00035, 0.00105),
    ("gemini", "gemini-2.0-flash-lite"): (0.00015, 0.00045),
    ("gemini", "gemini-1.5-pro"): (0.00125, 0.005),
    ("gemini", "gemini-1.5-flash"): (0.00035, 0.00105),
}


def _normalize_model(provider: str, model: str) -> str:
    if provider == "gemini":
        alias = model.lower()
        alias_map = {
            "gemini-2.5-flash": "gemini-2.0-flash",
            "gemini-2.5-flash-lite": "gemini-2.0-flash-lite",
            "2.5-flash": "gemini-2.0-flash",
            "2.5-flash-lite": "gemini-2.0-flash-lite",
            "1.5-flash": "gemini-1.5-flash",
            "1.5-pro": "gemini-1.5-pro",
        }
        return alias_map.get(alias, model)
    return model


@dataclass
class LLMResponse:
    provider: str
    model: str
    content: str
    tokens_in: int
    tokens_out: int
    cost_estimate: float
    duration_s: float


def _estimate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    rates = MODEL_RATES.get((provider, model))
    if not rates:
        # Allow models without explicit pricing to proceed; treat cost as zero.
        return 0.0
    in_rate, out_rate = rates
    return in_rate * (tokens_in / 1000.0) + out_rate * (tokens_out / 1000.0)


def _invoke_openai(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,  # ✅ يُمرر من invoke_model (300 ثانية افتراضياً)
) -> LLMResponse:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required for OpenAI provider")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    start = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        response = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
    elapsed = time.perf_counter() - start
    data = response.json()
    choice = data["choices"][0]
    content = choice["message"]["content"]
    usage = data.get("usage", {})
    tokens_in = int(usage.get("prompt_tokens", 0))
    tokens_out = int(usage.get("completion_tokens", 0))
    cost_estimate = _estimate_cost("openai", model, tokens_in, tokens_out)
    return LLMResponse("openai", model, content, tokens_in, tokens_out, cost_estimate, elapsed)


def _invoke_gemini(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,  # ✅ يُمرر من invoke_model (300 ثانية افتراضياً)
) -> LLMResponse:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is required for Gemini provider")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": api_key}
    headers = {"Content-Type": "application/json"}
    generation_cfg = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
        "responseMimeType": "application/json",
    }
    if top_p > 0:
        generation_cfg["topP"] = top_p

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {"role": "user", "parts": [{"text": user_prompt}]},
        ],
        "generationConfig": generation_cfg,
    }

    start = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, params=params, headers=headers, json=payload)
        response.raise_for_status()
    elapsed = time.perf_counter() - start
    data = response.json()
    candidates = data.get("candidates")
    if not candidates:
        raise RuntimeError("Gemini response missing candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini response missing content parts")
    content = parts[0].get("text", "")

    usage = data.get("usageMetadata", {})
    tokens_in = int(usage.get("promptTokenCount", 0))
    tokens_out = int(usage.get("candidatesTokenCount", 0))
    if tokens_in == 0 and tokens_out == 0:
        approx = len(user_prompt) + len(system_prompt)
        tokens_in = max(1, approx // 4)
        tokens_out = max(1, len(content) // 4)
    cost_estimate = _estimate_cost("gemini", model, tokens_in, tokens_out)

    return LLMResponse("gemini", model, content, tokens_in, tokens_out, cost_estimate, elapsed)


def invoke_model(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int = 300,  # ✅ زيادة timeout إلى 5 دقائق (كان 60 ثانية)
) -> LLMResponse:
    canonical_model = _normalize_model(provider, model)
    if provider == "openai":
        return _invoke_openai(canonical_model, system_prompt, user_prompt, max_tokens, temperature, top_p, timeout)
    if provider == "gemini":
        return _invoke_gemini(canonical_model, system_prompt, user_prompt, max_tokens, temperature, top_p, timeout)
    raise RuntimeError(f"Provider '{provider}' is not currently supported")


__all__ = ["LLMResponse", "invoke_model"]
