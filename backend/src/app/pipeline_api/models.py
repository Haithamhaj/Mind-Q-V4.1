"""Pipeline API data models canonicalised under backend."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator


class PipelineRequest(BaseModel):
    """Inputs accepted by the pipeline FastAPI surface and runners."""

    data_files: List[str] = Field(..., description="Raw data files for Stage 01 ingestion.")
    sla_files: Optional[List[str]] = Field(default=None, description="Optional SLA documents passed to Stage 01.")
    artifacts_root: Optional[str] = Field(default=None, description="Artifacts root override.")
    stop_on_error: bool = Field(default=True, description="Whether to abort on the first phase failure.")
    llm_credentials_file: Optional[str] = Field(
        default=None,
        description="Optional .env-style file containing LLM API keys to apply across all phases.",
    )
    llm_summary: bool = Field(
        default=False,
        description="If true, Stage 07.6 LLM summary will be attempted (requires LLM credentials).",
    )
    run_textops: bool = Field(
        default=True,
        description="Toggle Stage 03.5 TextOps execution during the flow.",
    )
    run_stage07_analytics: bool = Field(
        default=False,
        description="Enable the Python-based Stage 07 analytics suite.",
    )
    run_stage07_timeseries: bool = Field(
        default=False,
        description="Enable Stage 07 timeseries forecast templates (requires timeseries_inputs).",
    )
    run_causal: bool = Field(
        default=False,
        description="Enable the optional Stage 09.5 causal advisory run.",
    )
    run_routing: bool = Field(
        default=False,
        description="Enable the optional Stage 12 routing optimization run.",
    )
    timeseries_inputs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Explicit inputs for Stage 07 timeseries (e.g., timeseries_path, column overrides).",
    )
    routing_inputs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Explicit scenario payload for Stage 12 routing.",
    )
    causal_problem_name: Optional[str] = Field(
        default=None,
        description="Name of the causal problem to run during Stage 09.5.",
    )
    use_defaults: bool = Field(
        default=True,
        description="Whether to auto-resolve canonical inputs from prior stages when not provided explicitly.",
    )

    @root_validator(skip_on_failure=True)
    def _validate_optional_flags(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        timeseries_inputs = values.get("timeseries_inputs")
        if timeseries_inputs and not values.get("run_stage07_timeseries"):
            values["run_stage07_timeseries"] = True
        if values.get("run_stage07_timeseries") and not timeseries_inputs:
            raise ValueError("Stage 07 timeseries requires timeseries_inputs when enabled.")

        routing_inputs = values.get("routing_inputs")
        if routing_inputs and not values.get("run_routing"):
            values["run_routing"] = True
        if values.get("run_routing") and not routing_inputs:
            raise ValueError("Stage 12 routing requires routing_inputs when enabled.")

        causal_problem = values.get("causal_problem_name")
        if causal_problem and not values.get("run_causal"):
            values["run_causal"] = True
        if values.get("run_causal") and not causal_problem:
            raise ValueError("Stage 09.5 causal advisory requires causal_problem_name when enabled.")
        return values


class PipelineResponse(BaseModel):
    run_id: str
    phases: List[Dict[str, Any]]


__all__ = ["PipelineRequest", "PipelineResponse"]