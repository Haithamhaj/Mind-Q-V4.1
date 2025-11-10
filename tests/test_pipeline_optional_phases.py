from backend.src.app.pipeline_api import PipelineRequest
from backend.src.app.services.pipeline_api.app import _build_active_phases


def _request(**overrides):
    payload = {
        "data_files": ["/tmp/data.csv"],
        "llm_summary": False,
    }
    payload.update(overrides)
    return PipelineRequest(**payload)


def test_build_active_phases_defaults():
    request = _request()
    phases = _build_active_phases(request)
    assert "07_analytics" not in phases
    assert "07_timeseries" not in phases
    assert "09_5_causal" not in phases
    assert "12_routing" not in phases


def test_build_active_phases_with_optionals():
    request = _request(
        run_stage07_analytics=True,
        run_stage07_timeseries=True,
        run_causal=True,
        causal_problem_name="test-problem",
        run_routing=True,
    )
    phases = _build_active_phases(request)
    assert phases.index("07_analytics") > phases.index("07_7_business_correlations")
    assert phases.index("07_timeseries") > phases.index("07_analytics")
    assert phases.index("09_5_causal") > phases.index("09_business_validation")
    assert phases.index("12_routing") > phases.index("10_bi")
