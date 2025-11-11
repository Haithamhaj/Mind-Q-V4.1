"""Smoke-tests the canonical pipeline import surface to avoid regressions."""

def test_pipeline_imports_no_cycle():
    import backend.src.app.pipeline_api as backend_pipeline
    import src.app.services.pipeline_api as src_pipeline

    assert hasattr(backend_pipeline, "app") and hasattr(src_pipeline, "app")
